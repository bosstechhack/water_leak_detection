import os
import pandas as pd
import wntr
from detector import AnomalyDetector
from localizer import Localizer

def evaluate_scenario(baseline_p_csv, test_p_csv, baseline_f_csv=None, test_f_csv=None, network_file=None, true_leak_node='15', k=5):
    """
    Evaluates a specific leak scenario against the baseline using Option A (Pressure + Directional Flow Divergence).
    Returns Top-1 accuracy (bool) and Top-k accuracy (bool).
    """
    baseline_df = pd.read_csv(baseline_p_csv, index_col=0)
    test_df = pd.read_csv(test_p_csv, index_col=0)
    
    b_flow_df = pd.read_csv(baseline_f_csv, index_col=0) if baseline_f_csv and os.path.exists(baseline_f_csv) else None
    t_flow_df = pd.read_csv(test_f_csv, index_col=0) if test_f_csv and os.path.exists(test_f_csv) else None
    
    node_link_dirs = {}
    if network_file and os.path.exists(network_file):
        wn = wntr.network.WaterNetworkModel(network_file)
        for node_name in wn.node_name_list:
            str_n = str(node_name)
            dirs = []
            for link_name in wn.get_links_for_node(node_name):
                link_obj = wn.get_link(link_name)
                sign = 1.0 if link_obj.end_node_name == node_name else -1.0
                dirs.append((str(link_name), sign))
            node_link_dirs[str_n] = dirs
    
    detector = AnomalyDetector()
    detector.fit(baseline_df)
    
    localizer = Localizer(flow_weight=50.0)
    localizer.fit(baseline_df, b_flow_df)
    
    # 1. Detection
    anomalies = detector.detect(test_df)
    has_anomaly = anomalies.any(axis=1).any()
    
    if not has_anomaly:
        print("No anomalies detected.")
        return False, False
        
    ranked_nodes = localizer.localize(test_df, t_flow_df, node_link_dirs)
    
    if network_file and os.path.exists(network_file):
        wn = wntr.network.WaterNetworkModel(network_file)
        ranked_nodes = ranked_nodes[ranked_nodes.index.isin(wn.junction_name_list)]
    
    top_1 = str(ranked_nodes.index[0]) == str(true_leak_node)
    top_k = str(true_leak_node) in [str(n) for n in ranked_nodes.index[:k]]
    
    print(f"True Leak Node: {true_leak_node}")
    print(f"Top 5 Predicted: {list(ranked_nodes.index[:5])}")
    print(f"Top-1 Match: {top_1}")
    print(f"Top-{k} Match: {top_k}")
    
    return top_1, top_k

if __name__ == "__main__":
    evaluate_scenario(
        baseline_p_csv='../data/raw_simulations/baseline_pressures.csv',
        test_p_csv='../data/raw_simulations/leak_15_pressures.csv',
        baseline_f_csv='../data/raw_simulations/baseline_flows.csv',
        test_f_csv='../data/raw_simulations/leak_15_flows.csv',
        network_file='../data/networks/Net3.inp',
        true_leak_node='15'
    )

