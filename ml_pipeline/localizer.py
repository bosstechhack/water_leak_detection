import pandas as pd
import numpy as np

class Localizer:
    def __init__(self, flow_weight=50.0):
        """
        Hydraulic Localizer implementing Option A:
        Directional Mass Imbalance (Flow Divergence) + Spatial Pressure Drop Residuals.
        
        Score(i) = Max_ΔP(i) + λ * Net_Flow_Divergence(i)
        
        Where Net_Flow_Divergence(i) measures the physical mass loss (inflow - outflow)
        at each node, perfectly distinguishing leak sinks from throughput pipes and pumps.
        """
        self.baseline_df = None
        self.baseline_flow_df = None
        self.flow_weight = flow_weight

    def fit(self, baseline_df: pd.DataFrame, baseline_flow_df: pd.DataFrame = None):
        """Store baseline expected pressures and flows."""
        self.baseline_df = baseline_df
        self.baseline_flow_df = baseline_flow_df

    def localize(self, test_df: pd.DataFrame, test_flow_df: pd.DataFrame = None, node_link_dirs: dict = None):
        """
        Rank candidate nodes based on combined Pressure Drop Residual (ΔP) 
        and Directional Mass Imbalance (ΔQ divergence).
        """
        if self.baseline_df is None:
            raise ValueError("Localizer must be fitted with baseline data first.")
            
        # 1. Spatial Pressure Drop Residuals (Baseline - Test)
        p_residuals = self.baseline_df - test_df
        max_p_drops = p_residuals.max()
        
        scores = max_p_drops.copy()
        
        # 2. Directional Net Flow Divergence (Mass Imbalance)
        if self.baseline_flow_df is not None and test_flow_df is not None and node_link_dirs:
            for node_id, link_specs in node_link_dirs.items():
                str_node = str(node_id)
                if str_node in scores.index:
                    # Calculate net mass imbalance across all timesteps: Sum(sign * (Q_test - Q_base))
                    net_divergence_series = pd.Series(0.0, index=test_flow_df.index)
                    for link_name, direction_sign in link_specs:
                        if link_name in test_flow_df.columns and link_name in self.baseline_flow_df.columns:
                            diff = (test_flow_df[link_name] - self.baseline_flow_df[link_name]) * direction_sign
                            net_divergence_series += diff
                    
                    # Only positive divergence (mass exiting network via leak) adds to score
                    max_divergence = float(net_divergence_series.max())
                    if max_divergence > 0:
                        scores[str_node] += self.flow_weight * max_divergence
                
        # Rank candidate nodes in descending order
        ranked_nodes = scores.sort_values(ascending=False)
        return ranked_nodes


