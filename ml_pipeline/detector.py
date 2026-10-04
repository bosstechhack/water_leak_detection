import pandas as pd
import numpy as np

class AnomalyDetector:
    def __init__(self, threshold_drop=0.5):
        """
        Baseline anomaly detector using hydraulic pressure residuals.
        Residual = P_baseline(t) - P_test(t).
        If residual > threshold_drop (in meters of pressure head), an anomaly is flagged.
        """
        self.threshold_drop = threshold_drop

    def fit(self, baseline_df: pd.DataFrame):
        self.baseline_df = baseline_df

    def detect(self, test_df: pd.DataFrame):
        if self.baseline_df is None:
            raise ValueError("Detector must be fitted with baseline data first.")
            
        # Calculate residual at each timestamp and node
        residuals = self.baseline_df - test_df
        
        # Anomaly is flagged when residual exceeds threshold drop
        anomalies = residuals > self.threshold_drop
        return anomalies

