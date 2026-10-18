"""Evaluate saved scenarios against their simulation labels."""
import os
import sys
import pandas as pd
import wntr
from detector import AnomalyDetector
from localizer import Localizer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT, "data", "raw_simulations")
NETWORK_FILE = os.path.join(ROOT, "data", "networks", "Net3.inp")


def link_directions(network_file):
    wn = wntr.network.WaterNetworkModel(network_file)
    result = {}
    for node in wn.node_name_list:
        result[str(node)] = [(str(link), 1.0 if wn.get_link(link).end_node_name == node else -1.0)
                             for link in wn.get_links_for_node(node)]
    return wn, result


def main():
    metadata_path = os.path.join(DATA_DIR, "scenarios.csv")
    if not os.path.exists(metadata_path):
        raise FileNotFoundError("Scenario labels are missing. Run simulation/generate_dataset.py first.")
    metadata = pd.read_csv(metadata_path).fillna("")
    baseline_p = pd.read_csv(os.path.join(DATA_DIR, "baseline_pressures.csv"), index_col=0)
    baseline_f_path = os.path.join(DATA_DIR, "baseline_flows.csv")
    baseline_f = pd.read_csv(baseline_f_path, index_col=0) if os.path.exists(baseline_f_path) else None
    detector = AnomalyDetector()
    detector.fit(baseline_p)
    wn, directions = link_directions(NETWORK_FILE)
    rows = []

    for _, scenario in metadata.iterrows():
        sid, event_type = str(scenario["scenario_id"]), str(scenario["type"])
        if event_type == "baseline":
            continue
        p_path = os.path.join(DATA_DIR, f"{sid}_pressures.csv")
        f_path = os.path.join(DATA_DIR, f"{sid}_flows.csv")
        if not os.path.exists(p_path):
            print(f"Skipping {sid}: pressure file missing")
            continue
        test_p = pd.read_csv(p_path, index_col=0)
        common_nodes = [n for n in baseline_p if n in test_p]
        common_times = baseline_p.index.intersection(test_p.index)
        b_p, t_p = baseline_p.loc[common_times, common_nodes], test_p.loc[common_times, common_nodes]
        detected = bool(detector.detect(t_p).to_numpy().any())
        pred_node, top5, top1_ok, top5_ok = "", [], None, None
        if event_type == "leak" and detected:
            test_f = pd.read_csv(f_path, index_col=0) if os.path.exists(f_path) else None
            localizer = Localizer(flow_weight=50.0)
            localizer.fit(b_p, baseline_f)
            ranking = localizer.localize(t_p, test_f, directions)
            ranking = ranking[ranking.index.astype(str).isin(set(map(str, wn.junction_name_list)))]
            top5 = [str(x) for x in ranking.index[:5]]
            pred_node = top5[0] if top5 else ""
            true_node = str(scenario.get("node", ""))
            top1_ok, top5_ok = pred_node == true_node, true_node in top5
        rows.append({"scenario_id": sid, "event_type": event_type, "detected": detected,
                     "predicted_top1": pred_node, "top5": "|".join(top5),
                     "true_node": str(scenario.get("node", "")),
                     "top1_correct": top1_ok, "top5_correct": top5_ok,
                     "nonleak_anomaly_flag": bool(event_type != "leak" and detected)})

    result = pd.DataFrame(rows)
    output = os.path.join(DATA_DIR, "evaluation_results.csv")
    result.to_csv(output, index=False)
    print(result.to_string(index=False))
    leak_rows = result[result.event_type == "leak"]
    nonleak_rows = result[result.event_type != "leak"]
    print("\nSummary")
    print(f"Leak detection: {int(leak_rows.detected.sum())}/{len(leak_rows)}")
    if len(leak_rows):
        evaluated = leak_rows[leak_rows.top1_correct.notna()]
        print(f"Leak Top-1: {int(evaluated.top1_correct.sum())}/{len(evaluated)}")
        print(f"Leak Top-5: {int(evaluated.top5_correct.sum())}/{len(evaluated)}")
    print(f"Non-leak anomaly flags (not a leak classification): {int(nonleak_rows.nonleak_anomaly_flag.sum())}/{len(nonleak_rows)}")
    print(f"Saved detailed results: {output}")


if __name__ == "__main__":
    main()
