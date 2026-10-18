"""Evaluate detection, cause classification and leak localization on HELD-OUT test scenarios.

Protocol: all scenarios are split about 80/20 (see split.py). The cause classifier and the noise
thresholds are fitted on the training scenarios only. Every number reported here is measured on the
test scenarios, which the system has never seen. Training-set numbers are reported only to show the gap.

Outputs (data/results/): evaluation_summary.json (read by the API and dashboard),
evaluation_scenarios.csv and evaluation_leaks.csv (one row per test scenario), features.csv, split.json.
All data are simulated, not from real sensors.
"""
import json
import os
import time
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

import classifier
from classifier import CLASSES
from dataset import RESULTS_DIR, available_networks
from features import FEATURES, quiet_mask
from localizer import LegacyLocalizer
from pipeline import analyze, get_context
from split import SEED, TEST_FRACTION, write_split
from train import feature_table

LEGACY_THRESHOLD_M = 0.5


def scenario_area(spec):
    if spec.get("type") == "leak":
        return spec.get("leak_area")
    for event in spec.get("events", []):
        if event.get("type") == "leak":
            return event.get("leak_area")
    return None


def prf(y_true, y_pred, labels):
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    return {lab: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])}
            for i, lab in enumerate(labels)}


def predict(model, frame):
    """Stage 1 (quiet gate) then stage 2 (classifier)."""
    pred = model.predict(frame[FEATURES])
    return np.where(quiet_mask(frame).to_numpy(), "normal", pred)


def classification_block(table, kind, note):
    """Fit on training scenarios, score on test scenarios; also leave-one-network-out."""
    train, test = table[table["split"] == "train"], table[table["split"] == "test"]
    model = classifier.make_model(kind).fit(train[FEATURES], train["event_class"])
    pred = predict(model, test)
    y = test["event_class"].to_numpy()
    labels = [c for c in CLASSES if c in set(y)]
    report = prf(y, pred, labels)
    block = {
        "accuracy": float((pred == y).mean()),
        "macro_f1": float(np.mean([v["f1"] for v in report.values()])),
        "train_accuracy": float((predict(model, train) == train["event_class"].to_numpy()).mean()),
        "n_train": int(len(train)), "n_test": int(len(test)),
        "per_class": report, "labels": labels,
        "confusion": confusion_matrix(y, pred, labels=labels).tolist(),
        "note": note,
    }
    loo = {}
    for held in sorted(table["network"].unique()):
        tr = table[(table["network"] != held) & (table["split"] == "train")]
        te = table[(table["network"] == held) & (table["split"] == "test")]
        m = classifier.make_model(kind).fit(tr[FEATURES], tr["event_class"])
        p = predict(m, te)
        truth_leak, pred_leak = (te["event_class"] == "leak").to_numpy(), p == "leak"
        tp = int((truth_leak & pred_leak).sum())
        loo[held] = {"accuracy": float((p == te["event_class"].to_numpy()).mean()), "n": int(len(te)),
                     "leak_recall": tp / max(int(truth_leak.sum()), 1),
                     "leak_precision": tp / max(int(pred_leak.sum()), 1)}
    block["leave_one_network_out"] = loo
    return block, model, pred, test


def detection_metrics(truth_event, flagged):
    truth_event, flagged = np.asarray(truth_event, bool), np.asarray(flagged, bool)
    tp, fp = int((truth_event & flagged).sum()), int((~truth_event & flagged).sum())
    fn, tn = int((truth_event & ~flagged).sum()), int((~truth_event & ~flagged).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1,
            "false_alarm_rate": fp / (fp + tn) if fp + tn else 0.0, "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def loc_metrics(rows):
    if not rows:
        return {"n": 0}
    rank = np.array([r["rank"] for r in rows], float)
    hops = np.array([r["hops"] for r in rows], float)
    metres = np.array([r["metres"] for r in rows], float)
    return {"n": len(rows), "top1": float(np.mean(rank == 1)), "top3": float(np.mean(rank <= 3)),
            "top5": float(np.mean(rank <= 5)), "mean_hops": float(np.nanmean(hops)),
            "median_hops": float(np.nanmedian(hops)), "within_1_hop": float(np.mean(hops <= 1)),
            "mean_error_m": float(np.nanmean(metres))}


def locate(ctx, ranking, truth):
    nodes = list(ranking.index)
    rank = nodes.index(truth) + 1 if truth in nodes else float("nan")
    top = nodes[0]
    return {"rank": rank, "hops": ctx.nd.hops(top, truth), "metres": ctx.nd.distance_m(top, truth), "top": top}


METHODS = {
    "legacy_pressure_plus_divergence": None,
    "proposed": dict(neighbor_weight=0.0, use_demand=True),
    "proposed_with_graph_smoothing": dict(neighbor_weight=0.3, use_demand=True),
    "proposed_no_demand_meters": dict(neighbor_weight=0.0, use_demand=False),
    "pressure_only": dict(neighbor_weight=0.0, use_demand=True, use_flow=False),
    "pressure_only_with_graph_smoothing": dict(neighbor_weight=0.3, use_demand=True, use_flow=False),
}


def localise_rows(frame_rows, methods, timing=None):
    """Rank nodes for each leak scenario in `frame_rows` with each method."""
    per_method = {m: [] for m in methods}
    detail = []
    for _, r in frame_rows.iterrows():
        ctx = get_context(r["network"])
        spec = ctx.nd.scenario(r["id"])
        truth = str(spec["truth_nodes"][0])
        if truth in ctx.nd.unstable_nodes:
            continue
        frames = ctx.nd.load(r["id"])
        entry = {"network": r["network"], "id": r["id"], "group": r["group"], "truth": truth,
                 "area": scenario_area(spec), "node_type": ctx.nd.node_type(truth),
                 "classified_leak": bool(r.get("predicted_class", "leak") == "leak"),
                 "detected": bool(r.get("adaptive_flag", True))}
        for m, cfg in methods.items():
            if cfg is None:
                ranking = LegacyLocalizer().localize(ctx.nd, frames)
            else:
                start = time.perf_counter()
                ranking = analyze(ctx, frames, None, cfg["use_demand"], neighbor_weight=cfg["neighbor_weight"],
                                  use_flow=cfg.get("use_flow", True))["ranking"]
                if m == "proposed" and timing is not None:
                    timing.append((time.perf_counter() - start) * 1000)
            loc = locate(ctx, ranking, truth)
            per_method[m].append({**entry, **loc})
            if m == "proposed":
                entry.update({"pred_top1": loc["top"], "rank": loc["rank"], "hops": loc["hops"], "metres": loc["metres"]})
        detail.append(entry)
    return per_method, detail


def main():
    t0 = time.time()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    write_split()
    table = feature_table(True)
    table_nodemand = feature_table(False)
    table.to_csv(os.path.join(RESULTS_DIR, "features.csv"), index=False)
    train_t, test_t = table[table["split"] == "train"], table[table["split"] == "test"]

    summary = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "protocol": "80/20 hold-out: fitted on training scenarios, every number measured on test scenarios",
        "split": {"seed": SEED, "test_fraction": TEST_FRACTION, "n_train": int(len(train_t)), "n_test": int(len(test_t)),
                  "train_by_class": {k: int(v) for k, v in train_t.event_class.value_counts().items()},
                  "test_by_class": {k: int(v) for k, v in test_t.event_class.value_counts().items()},
                  "grouping": "all leaks at one junction, and a scenario with its noisy twin, stay on the same side"},
        "n_scenarios": int(len(table)),
        "networks": {n: int((table.network == n).sum()) for n in available_networks()},
        "class_counts": {k: int(v) for k, v in table.event_class.value_counts().items()},
    }

    # ---- cause classification --------------------------------------------------------------
    forest, forest_model, pred_forest, test_rows = classification_block(table, "forest", "uses metered node demands")
    tree, _, _, _ = classification_block(table, "tree", "uses metered node demands")
    forest_nd, _, pred_nd, _ = classification_block(table_nodemand, "forest", "no demand meters")
    summary["classification"] = {"forest_with_demand_meters": forest, "tree_with_demand_meters": tree,
                                 "forest_without_demand_meters": forest_nd}
    rows = test_rows[["network", "id", "group", "event_class"]].copy()
    rows["predicted_class"] = pred_forest
    rows["predicted_class_no_demand_meters"] = pred_nd

    # ---- detection: any abnormal event versus normal operation (test scenarios) ------------
    truth_event = (rows.event_class != "normal").to_numpy()
    legacy, adaptive = [], []
    for _, r in rows.iterrows():
        ctx = get_context(r["network"])
        frames = ctx.nd.load(r["id"])
        residual = ctx.nd.baseline.P - frames.P[ctx.nd.baseline.P.columns]
        legacy.append(bool((residual > LEGACY_THRESHOLD_M).any().any()))
        adaptive.append(ctx.detector.is_anomalous(frames.P[ctx.nd.nodes]))
    rows["legacy_flag"], rows["adaptive_flag"] = legacy, adaptive
    summary["detection"] = {
        "legacy_fixed_0.5m": detection_metrics(truth_event, legacy),
        "adaptive_pressure": detection_metrics(truth_event, adaptive),
        "classifier": detection_metrics(truth_event, pred_forest != "normal"),
        "note": "positive = any abnormal event (leak, demand, pump, tank, blockage, ageing); test scenarios only",
        "n_normal_test": int((~truth_event).sum()),
    }
    non_leak = (rows.event_class != "leak").to_numpy()
    is_leak = (rows.event_class == "leak").to_numpy()
    summary["detection"]["leak_false_alarm_rate"] = float((pred_forest[non_leak] == "leak").mean())
    summary["detection"]["leak_recall"] = float((pred_forest[is_leak] == "leak").mean())

    # ---- localization of leaks (test scenarios) --------------------------------------------
    timings = []
    leaks = rows[rows["event_class"] == "leak"]
    per_method, detail = localise_rows(leaks, METHODS, timings)
    summary["localization"] = {m: loc_metrics(v) for m, v in per_method.items()}
    main_rows = per_method["proposed"]

    def split_by(key):
        return {k: loc_metrics([r for r in main_rows if str(r[key]) == k]) for k in sorted({str(r[key]) for r in main_rows})}
    summary["localization_breakdown"] = {"by_group": split_by("group"), "by_network": split_by("network"),
                                         "by_node_type": split_by("node_type")}
    sizes = {}
    for r in [r for r in main_rows if r["group"] == "leak_size"]:
        sizes.setdefault(f"{r['area']:g}", {"area": float(r["area"]), "rows": []})["rows"].append(r)
    summary["size_sensitivity"] = [
        {"area_m2": v["area"], "n": len(v["rows"]),
         "detected": float(np.mean([x["detected"] for x in v["rows"]])),
         "classified_leak": float(np.mean([x["classified_leak"] for x in v["rows"]])),
         "top1": float(np.mean([x["rank"] == 1 for x in v["rows"]])),
         "top5": float(np.mean([x["rank"] <= 5 for x in v["rows"]]))}
        for v in sorted(sizes.values(), key=lambda s: s["area"])]
    summary["end_to_end_leak_top1"] = float(np.mean([e["classified_leak"] and e.get("rank") == 1 for e in detail])) if detail else 0.0
    summary["mean_inference_ms"] = float(np.mean(timings)) if timings else None

    # ---- the same numbers on the TRAINING scenarios, only to show the gap -----------------
    train_rows = train_t[["network", "id", "group", "event_class"]].copy()
    train_leaks = train_rows[train_rows["event_class"] == "leak"]
    train_methods, _ = localise_rows(train_leaks, {"proposed": METHODS["proposed"]})
    summary["train_reference"] = {
        "classification_accuracy": forest["train_accuracy"],
        "localization_top1": loc_metrics(train_methods["proposed"]).get("top1"),
        "localization_n": len(train_methods["proposed"]),
        "note": "measured on training scenarios; shown only to expose over-fitting, never used as a result",
    }

    pd.DataFrame(detail).to_csv(os.path.join(RESULTS_DIR, "evaluation_leaks.csv"), index=False)
    rows.to_csv(os.path.join(RESULTS_DIR, "evaluation_scenarios.csv"), index=False)
    with open(os.path.join(RESULTS_DIR, "evaluation_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)

    # ---- console report --------------------------------------------------------------------
    pct = lambda x: f"{100 * x:5.1f}%"
    s = summary["split"]
    print(f"\n{summary['n_scenarios']} scenarios: {s['n_train']} train, {s['n_test']} test (never seen in fitting)")
    print("\nDetection on test scenarios (abnormal event vs normal):")
    for k in ("legacy_fixed_0.5m", "adaptive_pressure", "classifier"):
        d = summary["detection"][k]
        print(f"  {k:20s} P={pct(d['precision'])} R={pct(d['recall'])} F1={pct(d['f1'])} false alarms={pct(d['false_alarm_rate'])}")
    print("\nCause classification, test accuracy:")
    for k, b in summary["classification"].items():
        print(f"  {k:30s} test={pct(b['accuracy'])} macro-F1={pct(b['macro_f1'])} (train={pct(b['train_accuracy'])}, n_test={b['n_test']})")
        print("     leave-one-network-out:", {n: round(v['accuracy'], 3) for n, v in b['leave_one_network_out'].items()})
    print(f"  leak recall={pct(summary['detection']['leak_recall'])}, non-leak called a leak={pct(summary['detection']['leak_false_alarm_rate'])}")
    print("\nLeak localization on test leaks:")
    for m, v in summary["localization"].items():
        print(f"  {m:36s} n={v['n']} top1={pct(v['top1'])} top3={pct(v['top3'])} top5={pct(v['top5'])} hops={v['mean_hops']:.2f}")
    print(f"  train reference (proposed): top1={pct(summary['train_reference']['localization_top1'])} on {summary['train_reference']['localization_n']}")
    print(f"  end-to-end (classified leak and Top-1 correct): {pct(summary['end_to_end_leak_top1'])}")
    print(f"\nSaved results to {RESULTS_DIR} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
