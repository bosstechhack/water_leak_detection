import numpy as np
import pandas as pd


def persistent_peak(frame: pd.DataFrame, steps: int = 2) -> pd.Series:
    """Per-column peak of a signal that stays above that level for `steps` consecutive samples.

    A single noisy sample cannot create a peak; the signal has to persist.
    """
    if steps <= 1 or len(frame) < steps:
        return frame.max()
    return frame.rolling(steps).min().max()


class AnomalyDetector:
    """Pressure-residual detector.

    Residual = P_baseline(t) - P_observed(t). Without calibration data the threshold is the fixed
    `threshold_drop` (0.5 m, the Semester 1 baseline). When `fit` receives normal-operation runs the
    threshold is learned from their residual noise: max(min_threshold, k * sigma). An alarm also
    needs the residual to persist for `persistence` samples, so a single noisy reading is ignored.
    """

    def __init__(self, threshold_drop=0.5, k=4.0, min_threshold=0.1, persistence=1):
        self.threshold_drop = threshold_drop
        self.threshold = threshold_drop
        self.k = k
        self.min_threshold = min_threshold
        self.persistence = persistence
        self.sigma = None
        self.baseline_df = None

    def fit(self, baseline_df: pd.DataFrame, normal_runs=None):
        self.baseline_df = baseline_df
        if normal_runs:
            residuals = np.concatenate([
                (baseline_df - run[baseline_df.columns].loc[baseline_df.index]).to_numpy().ravel()
                for run in normal_runs])
            self.sigma = float(np.nanstd(residuals))
            self.threshold = max(self.min_threshold, self.k * self.sigma)
        return self

    def residuals(self, test_df: pd.DataFrame) -> pd.DataFrame:
        if self.baseline_df is None:
            raise ValueError("Detector must be fitted with baseline data first.")
        cols = [c for c in self.baseline_df.columns if c in test_df.columns]
        idx = self.baseline_df.index.intersection(test_df.index)
        return self.baseline_df.loc[idx, cols] - test_df.loc[idx, cols]

    def detect(self, test_df: pd.DataFrame) -> pd.DataFrame:
        """Boolean frame: residual above the threshold at each node and time."""
        return self.residuals(test_df) > self.threshold

    def is_anomalous(self, test_df: pd.DataFrame, nodes=None) -> bool:
        residuals = self.residuals(test_df)
        if nodes is not None:
            residuals = residuals[[n for n in nodes if n in residuals.columns]]
        return bool((persistent_peak(residuals, self.persistence) > self.threshold).any())
