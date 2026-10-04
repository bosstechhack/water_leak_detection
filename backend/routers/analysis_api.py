from fastapi import APIRouter
import pandas as pd
import sys
import os
from schemas import AnalysisResponse, PredictionResult, NodeMetric, FlowMetric
import wntr

# Add ml_pipeline to path so we can import models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../ml_pipeline')))
from detector import AnomalyDetector
from localizer import Localizer

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NETWORK_FILE = os.path.abspath(os.path.join(BASE_DIR, "../../data/networks/Net3.inp"))

@router.get("/analyze/{scenario_name}", response_model=AnalysisResponse)
def analyze_scenario(scenario_name: str):
    data_dir = os.path.abspath(os.path.join(BASE_DIR, "../../data/raw_simulations"))
    baseline_csv = os.path.join(data_dir, "baseline_pressures.csv")
    test_csv = os.path.join(data_dir, f"{scenario_name}_pressures.csv")
    baseline_flow_csv = os.path.join(data_dir, "baseline_flows.csv")
    test_flow_csv = os.path.join(data_dir, f"{scenario_name}_flows.csv")
    
    if not os.path.exists(baseline_csv) or not os.path.exists(test_csv):
        return AnalysisResponse(has_anomaly=False, predicted_leaks=[], node_metrics={}, flow_metrics={})
        
    baseline_df = pd.read_csv(baseline_csv, index_col=0)
    test_df = pd.read_csv(test_csv, index_col=0)
    
    # Read flow data if available
    b_flow_df = pd.read_csv(baseline_flow_csv, index_col=0) if os.path.exists(baseline_flow_csv) else None
    t_flow_df = pd.read_csv(test_flow_csv, index_col=0) if os.path.exists(test_flow_csv) else None

    # Load WNTR model for elevation and link connections if available
    wn = None
    node_pipe_map = {}
    node_link_dirs = {}
    if os.path.exists(NETWORK_FILE):
        try:
            wn = wntr.network.WaterNetworkModel(NETWORK_FILE)
            for node_name in wn.node_name_list:
                str_n = str(node_name)
                links = wn.get_links_for_node(node_name)
                node_pipe_map[str_n] = [str(link) for link in links]
                
                # Directional signs: +1.0 for inflow to node, -1.0 for outflow from node
                dirs = []
                for link_name in links:
                    link_obj = wn.get_link(link_name)
                    sign = 1.0 if link_obj.end_node_name == node_name else -1.0
                    dirs.append((str(link_name), sign))
                node_link_dirs[str_n] = dirs
        except Exception as e:
            print("WNTR load notice:", e)

    detector = AnomalyDetector()
    detector.fit(baseline_df)
    
    anomalies = detector.detect(test_df)
    has_anomaly = anomalies.any(axis=1).any()
    
    predictions = []
    top_predicted_node_ids = set()
    if has_anomaly:
        localizer = Localizer(flow_weight=50.0)
        localizer.fit(baseline_df, b_flow_df)
        ranked_nodes = localizer.localize(test_df, t_flow_df, node_link_dirs)
        
        # Filter candidate leak locations to junction nodes
        if wn:
            ranked_nodes = ranked_nodes[ranked_nodes.index.isin(wn.junction_name_list)]
        
        # Take Top 5
        for node_id, score in ranked_nodes.head(5).items():
            str_id = str(node_id)
            predictions.append(PredictionResult(
                node_id=str_id,
                confidence_score=float(score)
            ))
            top_predicted_node_ids.add(str_id)
            
    # Calculate detailed node metrics for every node
    node_metrics = {}
    
    # Compute residuals (Baseline - Test)
    residuals = baseline_df - test_df
    max_drops = residuals.max()
    
    for col in test_df.columns:
        str_node = str(col)
        base_press = float(baseline_df[col].mean())
        curr_press = float(test_df[col].mean())
        drop_val = float(max_drops[col])
        
        # Extract 24-hour time series arrays
        b_series = [round(float(v), 2) for v in baseline_df[col].values]
        c_series = [round(float(v), 2) for v in test_df[col].values]

        # Determine status — use 3.0m threshold for visual highlighting
        # (0.5m is too sensitive; nearly all connected nodes exceed it)
        if str_node in top_predicted_node_ids:
            status = "Predicted Leak Location"
        elif drop_val > 3.0:
            status = "Anomalous Pressure Drop"
        else:
            status = "Normal"
            
        elevation = 0.0
        connected_pipes = []
        node_type = "Junction"
        if wn and str_node in wn.node_name_list:
            node_obj = wn.get_node(str_node)
            elevation = float(getattr(node_obj, 'elevation', 0.0) or 0.0)
            node_type = str(node_obj.node_type)
            if getattr(node_obj, 'base_demand', 0.0) is not None and getattr(node_obj, 'base_demand', 0.0) < 0:
                node_type = "Reservoir"  # Main Supply Source Inlet
            connected_pipes = node_pipe_map.get(str_node, [])
            
        # Flow divergence (mass imbalance) for this node
        node_div = 0.0
        if b_flow_df is not None and t_flow_df is not None and str_node in node_link_dirs:
            net_div_series = pd.Series(0.0, index=t_flow_df.index)
            for link_name, direction_sign in node_link_dirs[str_node]:
                if link_name in t_flow_df.columns and link_name in b_flow_df.columns:
                    net_div_series += (t_flow_df[link_name] - b_flow_df[link_name]) * direction_sign
            node_div = max(0.0, float(net_div_series.max()))

        # Composite score
        comp_score = float(ranked_nodes.get(str_node, drop_val + 20.0 * node_div)) if has_anomaly else 0.0

        node_metrics[str_node] = NodeMetric(
            node_id=str_node,
            node_type=node_type,
            elevation=elevation,
            baseline_pressure=round(base_press, 2),
            current_pressure=round(curr_press, 2),
            pressure_drop=round(drop_val, 2),
            flow_divergence=round(node_div, 4),
            composite_score=round(comp_score, 2),
            status=status,
            connected_pipes=connected_pipes,
            baseline_series=b_series,
            current_series=c_series
        )

    # Compute flow metrics for pipes if available
    flow_metrics = {}
    if b_flow_df is not None and t_flow_df is not None:
        for col in t_flow_df.columns:
            str_link = str(col)
            b_flow = float(b_flow_df[col].mean())
            c_flow = float(t_flow_df[col].mean())
            f_change = c_flow - b_flow
            flow_metrics[str_link] = FlowMetric(
                link_id=str_link,
                baseline_flow=round(b_flow, 4),
                current_flow=round(c_flow, 4),
                flow_change=round(f_change, 4)
            )

    return AnalysisResponse(
        has_anomaly=bool(has_anomaly),
        predicted_leaks=predictions,
        node_metrics=node_metrics,
        flow_metrics=flow_metrics
    )
