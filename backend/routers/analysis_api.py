import json
import os
import re
import sys

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

from schemas import AnalysisResponse, FlowMetric, NodeMetric, PredictionResult

ML_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../ml_pipeline"))
sys.path.append(ML_DIR)
import classifier  # noqa: E402
from catalog import describe  # noqa: E402
from dataset import RESULTS_DIR, available_networks  # noqa: E402
from detector import persistent_peak  # noqa: E402
from features import unaccounted_flow  # noqa: E402
from pipeline import analyze, get_context  # noqa: E402
from split import get_split  # noqa: E402

router = APIRouter()
_MODELS = {}


def _models():
    if "m" not in _MODELS:
        _MODELS["m"] = classifier.load()
    return _MODELS["m"]


def _split(scenario_name):
    """'net3_leak_15' -> ('net3', 'net3_leak_15'); 'net3_baseline' -> ('net3', 'baseline')."""
    network = scenario_name.split("_")[0]
    return network, ("baseline" if scenario_name == f"{network}_baseline" else scenario_name)


@router.get("/analyze/{scenario_name}", response_model=AnalysisResponse)
def analyze_scenario(scenario_name: str, use_demand_meters: bool = True):
    # ids look like net3_reservoir_head_Lake_+5m: letters, digits and _ . + - only (no path characters)
    if not re.fullmatch(r"[A-Za-z0-9_.+-]+", scenario_name):
        raise HTTPException(status_code=400, detail="Invalid scenario name")
    network, file_id = _split(scenario_name)
    if network not in available_networks():
        raise HTTPException(status_code=404, detail=f"Unknown network in scenario: {scenario_name}")
    ctx = get_context(network)
    nd, ref = ctx.nd, ctx.ref
    spec = None if file_id == "baseline" else nd.scenario(file_id)
    if file_id != "baseline" and spec is None:
        raise HTTPException(status_code=404, detail=f"Scenario not found: {scenario_name}")
    test = nd.load(file_id)
    base = nd.baseline

    models = _models()
    result = analyze(ctx, test, models, use_demand_meters)
    event_class = result["event_class"]
    probabilities = result["probabilities"]
    label = classifier.LABELS.get(event_class, event_class)
    thr = ctx.ref.p_threshold
    ranking = result["ranking"]
    drop, unacc = result["drop"], result["unacc"]

    is_leak = event_class == "leak"
    has_anomaly = bool(event_class != "normal") if event_class else result["has_anomaly"]

    # unaccounted flow in m3/s at every node (peak, persistent)
    u_series = unaccounted_flow(nd, base, test, nd.nodes, use_demand_meters)
    u_peak = persistent_peak(u_series, 2).clip(lower=0)

    predictions = []
    region = []
    if is_leak:
        for node_id, score in ranking.head(5).items():
            predictions.append(PredictionResult(node_id=str(node_id), confidence_score=round(float(score), 3),
                                                pressure_drop=round(float(drop.get(node_id, 0.0) * thr), 3),
                                                flow_divergence=round(float(u_peak.get(node_id, 0.0)), 5)))
        top = predictions[0].node_id
        region = sorted([top] + [n for n in nd.graph.neighbors(top) if n in set(nd.nodes)])

    affected = sorted(str(n) for n in drop.index[drop > 1.0])
    truth = {}
    error_hops = None
    if spec:
        truth = {"event_class": spec["event_class"], "group": spec["group"], "description": describe(spec)}
        if spec.get("truth_nodes"):
            truth["leak_nodes"] = ", ".join(spec["truth_nodes"])
            if predictions:
                error_hops = nd.hops(predictions[0].node_id, spec["truth_nodes"][0])
                error_hops = int(error_hops) if error_hops == error_hops else None
    else:
        truth = {"event_class": "normal", "description": "Baseline (no event)"}

    feats = result["features"]
    split = "reference" if file_id == "baseline" else get_split().get(file_id, "train")
    explanation = []
    if event_class is None:
        explanation.append("Classifier model not found. Run ml_pipeline/train.py.")
    else:
        top_prob = max(probabilities.values()) if probabilities else 0.0
        explanation.append(f"Predicted cause: {label} (model confidence {top_prob * 100:.0f}%).")
    if feats["frac_hit"] > 0:
        explanation.append(f"{feats['frac_hit'] * 100:.0f}% of junctions show a pressure drop above the "
                           f"{thr:.2f} m noise threshold; the worst is {float(drop.max()) * thr:.2f} m.")
    else:
        explanation.append(f"No junction shows a persistent pressure drop above the {thr:.2f} m noise threshold.")
    if use_demand_meters:
        if feats["unacc_ratio"] >= 1:
            explanation.append("Water is leaving a node without being metered (unaccounted flow), which only a leak causes.")
        elif feats["demand_frac"] > 0:
            explanation.append("The extra flow is explained by metered demand, so it is a demand change, not a leak.")
    if feats["pump_drop"] > 0.5:
        explanation.append("A pump has lost most of its flow.")
    if feats["rise_ratio"] > 5 and feats["frac_rise"] > 0:
        explanation.append("Some junctions show a pressure rise as well as drops, as when a pipe is blocked or a tank/source changes.")
    if is_leak and predictions:
        explanation.append("Ranking = unaccounted flow plus pressure drop per node. It is a heuristic score, not a probability.")
    if not use_demand_meters:
        explanation.append("Running without demand meters: demand changes are harder to separate from leaks.")

    node_metrics = {}
    top_ids = {p.node_id for p in predictions}
    common = [c for c in base.P.columns if c in test.P.columns]
    residual_all = base.P[common] - test.P[common]
    for col in common:
        node = str(col)
        peak_drop = float(max(residual_all[col].max(), 0.0))
        obj = nd.wn.get_node(node)
        status = "Top leak candidate" if node in top_ids else ("Pressure drop" if node in affected else "Normal")
        node_metrics[node] = NodeMetric(
            node_id=node, node_type=str(obj.node_type), elevation=float(getattr(obj, "elevation", 0.0) or 0.0),
            baseline_pressure=round(float(base.P[col].mean()), 2), current_pressure=round(float(test.P[col].mean()), 2),
            pressure_drop=round(peak_drop, 2), flow_divergence=round(float(u_peak.get(node, 0.0)), 5),
            composite_score=round(float(ranking.get(node, drop.get(node, 0.0))), 3), status=status,
            connected_pipes=[str(x) for x in nd.wn.get_links_for_node(node)],
            baseline_series=[round(float(x), 2) for x in base.P[col]],
            current_series=[round(float(x), 2) for x in test.P[col]])

    flow_metrics = {}
    for col in [c for c in base.F.columns if c in test.F.columns]:
        b, c = base.F[col], test.F[col]
        flow_metrics[str(col)] = FlowMetric(link_id=str(col), baseline_flow=round(float(b.mean()), 4),
                                            current_flow=round(float(c.mean()), 4),
                                            flow_change=round(float((c - b).mean()), 4))

    max_drop = float(drop.max() * thr)
    return AnalysisResponse(
        network=network, split=split, event_class=event_class, event_label=label, probabilities=probabilities,
        features={k: round(float(v), 4) for k, v in feats.items()},
        detection={"pressure_threshold_m": round(thr, 3), "adaptive_detector_flag": float(result["has_anomaly"])},
        worst_node=str(drop.idxmax()) if float(drop.max()) > 0 else None,
        candidate_region=region, affected_nodes=affected, localization_error_hops=error_hops,
        has_anomaly=has_anomaly, event_assessment=label or "cause not classified", scenario_truth=truth,
        explanation=explanation, peak_time=None, max_pressure_drop=round(max_drop, 2),
        predicted_leaks=predictions, node_metrics=node_metrics, flow_metrics=flow_metrics)


@router.get("/evaluation")
def evaluation():
    path = os.path.join(RESULTS_DIR, "evaluation_summary.json")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Run ml_pipeline/evaluate.py first")
    with open(path, encoding="utf-8") as f:
        return json.load(f)
