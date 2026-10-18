from fastapi import APIRouter, HTTPException
import os
import sys
import pandas as pd
import wntr
from schemas import AnalysisResponse, PredictionResult, NodeMetric, FlowMetric

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../ml_pipeline")))
from detector import AnomalyDetector
from localizer import Localizer

router = APIRouter()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "../../data/raw_simulations"))
NETWORK_FILE = os.path.abspath(os.path.join(BASE_DIR, "../../data/networks/Net3.inp"))
FLOW_WEIGHT = 50.0


def _link_directions(wn):
    mapping = {}
    for node_name in wn.node_name_list:
        mapping[str(node_name)] = [
            (str(link_name), 1.0 if wn.get_link(link_name).end_node_name == node_name else -1.0)
            for link_name in wn.get_links_for_node(node_name)
        ]
    return mapping


@router.get("/analyze/{scenario_name}", response_model=AnalysisResponse)
def analyze_scenario(scenario_name: str):
    # Restrict names to simple file stems; scenarios are generated locally.
    if not scenario_name.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid scenario name")
    baseline_path = os.path.join(DATA_DIR, "baseline_pressures.csv")
    test_path = os.path.join(DATA_DIR, f"{scenario_name}_pressures.csv")
    if not os.path.isfile(baseline_path) or not os.path.isfile(test_path):
        raise HTTPException(status_code=404, detail=f"Scenario data not found: {scenario_name}")

    baseline = pd.read_csv(baseline_path, index_col=0)
    test = pd.read_csv(test_path, index_col=0)
    common_nodes = [n for n in baseline.columns if n in test.columns]
    common_times = baseline.index.intersection(test.index)
    if not common_nodes or len(common_times) == 0:
        raise HTTPException(status_code=422, detail="Scenario and baseline have no matching nodes/times")
    baseline, test = baseline.loc[common_times, common_nodes], test.loc[common_times, common_nodes]

    baseline_flow_path = os.path.join(DATA_DIR, "baseline_flows.csv")
    test_flow_path = os.path.join(DATA_DIR, f"{scenario_name}_flows.csv")
    baseline_flow = pd.read_csv(baseline_flow_path, index_col=0) if os.path.isfile(baseline_flow_path) else None
    test_flow = pd.read_csv(test_flow_path, index_col=0) if os.path.isfile(test_flow_path) else None
    wn = wntr.network.WaterNetworkModel(NETWORK_FILE) if os.path.isfile(NETWORK_FILE) else None
    link_dirs = _link_directions(wn) if wn else {}

    residuals = baseline - test
    detector = AnomalyDetector()
    detector.fit(baseline)
    anomalies = detector.detect(test)
    has_anomaly = bool(anomalies.to_numpy().any())
    peak_node = str(residuals.max().idxmax())
    peak_time = str(residuals[peak_node].idxmax())
    peak_drop = float(residuals[peak_node].max())
    event_assessment = "anomaly detected; cause not classified" if has_anomaly else "no pressure anomaly detected"

    explanation = []
    if has_anomaly:
        explanation.append(f"Pressure residual exceeded the {detector.threshold_drop:.2f} m threshold.")
        explanation.append(f"Largest pressure drop was {peak_drop:.2f} m at node {peak_node}, time index {peak_time}.")
        explanation.append("The cause is not classified by the current detector; demand or equipment changes may also cause pressure drops.")
    else:
        explanation.append(f"No node exceeded the {detector.threshold_drop:.2f} m pressure-drop threshold.")

    predictions = []
    ranked = pd.Series(dtype=float)
    node_divergence = {}
    if has_anomaly:
        localizer = Localizer(flow_weight=FLOW_WEIGHT)
        localizer.fit(baseline, baseline_flow)
        ranked = localizer.localize(test, test_flow, link_dirs)
        if wn:
            ranked = ranked[ranked.index.astype(str).isin(set(map(str, wn.junction_name_list)))]
        for node_id, score in ranked.head(5).items():
            s = str(node_id)
            div = 0.0
            if baseline_flow is not None and test_flow is not None and s in link_dirs:
                common_links = [p for p, _ in link_dirs[s] if p in baseline_flow and p in test_flow]
                if common_links:
                    series = pd.Series(0.0, index=common_times)
                    for link, sign in link_dirs[s]:
                        if link in common_links:
                            series += (test_flow.loc[common_times, link] - baseline_flow.loc[common_times, link]) * sign
                    div = max(0.0, float(series.max()))
            predictions.append(PredictionResult(node_id=s, confidence_score=float(score),
                                                 pressure_drop=float(residuals[s].max()), flow_divergence=div))
        if predictions:
            explanation.append(f"Candidate ranking combines maximum pressure drop with positive connected-link flow divergence (weight {FLOW_WEIGHT:g}).")
            explanation.append("The ranking is a heuristic score, not a calibrated probability or proof of a leak.")

    top_ids = {p.node_id for p in predictions}
    node_metrics = {}
    for col in common_nodes:
        node = str(col)
        drop_series = residuals[col]
        drop = float(drop_series.max())
        div = next((p.flow_divergence for p in predictions if p.node_id == node), 0.0)
        node_type, elevation, connected = "Junction", 0.0, []
        if wn and node in wn.node_name_list:
            obj = wn.get_node(node)
            node_type = str(obj.node_type)
            elevation = float(getattr(obj, "elevation", 0.0) or 0.0)
            connected = [str(x) for x in wn.get_links_for_node(node)]
        status = "Top leak candidate" if node in top_ids else ("Pressure drop" if drop > detector.threshold_drop else "Normal")
        node_metrics[node] = NodeMetric(
            node_id=node, node_type=node_type, elevation=elevation,
            baseline_pressure=round(float(baseline[col].mean()), 2),
            current_pressure=round(float(test[col].mean()), 2), pressure_drop=round(drop, 2),
            flow_divergence=round(div, 4), composite_score=round(float(ranked.get(node, drop)), 2),
            status=status, connected_pipes=connected,
            baseline_series=[round(float(x), 2) for x in baseline[col]],
            current_series=[round(float(x), 2) for x in test[col]],
        )

    flow_metrics = {}
    if baseline_flow is not None and test_flow is not None:
        common_links = [x for x in baseline_flow.columns if x in test_flow.columns]
        common_flow_times = baseline_flow.index.intersection(test_flow.index)
        for col in common_links:
            b = baseline_flow.loc[common_flow_times, col]
            c = test_flow.loc[common_flow_times, col]
            flow_metrics[str(col)] = FlowMetric(link_id=str(col), baseline_flow=round(float(b.mean()), 4),
                current_flow=round(float(c.mean()), 4), flow_change=round(float((c-b).mean()), 4))

    scenario_truth = {}
    manifest = os.path.join(DATA_DIR, "scenarios.csv")
    if os.path.isfile(manifest):
        rows = pd.read_csv(manifest).fillna("")
        match = rows[rows["scenario_id"].astype(str) == scenario_name]
        if not match.empty:
            truth = match.iloc[0]
            scenario_truth = {k: str(truth[k]) for k in ("type", "node", "pump", "factor", "leak_area", "start_hour")
                              if k in truth and str(truth[k]) != ""}

    return AnalysisResponse(has_anomaly=has_anomaly, event_assessment=event_assessment,
        scenario_truth=scenario_truth,
        explanation=explanation, peak_time=peak_time, max_pressure_drop=round(peak_drop, 2),
        predicted_leaks=predictions, node_metrics=node_metrics, flow_metrics=flow_metrics)
