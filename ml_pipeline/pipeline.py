"""One entry point used by the API and the evaluation: analyse a scenario against its baseline."""
import numpy as np
import pandas as pd

from classifier import CLASSES, LABELS
from dataset import NetworkData
from detector import AnomalyDetector
from features import FEATURES, calibrate, extract, node_signals, quiet_mask
from localizer import Localizer
from split import get_split

_CONTEXTS = {}


class Context:
    """Everything fixed for one network: data, learned noise levels, adaptive detector."""

    def __init__(self, name):
        self.nd = NetworkData(name)
        # Noise levels are learned from the TRAINING normal runs only; test runs are never used here.
        split = get_split()
        normal_ids = [s["id"] for s in self.nd.scenarios()
                      if s["event_class"] == "normal" and split.get(s["id"]) == "train"]
        normal_runs = [self.nd.load(i) for i in normal_ids]
        self.ref = calibrate(self.nd, normal_runs)
        self.detector = AnomalyDetector(persistence=2).fit(self.nd.baseline.P[self.nd.nodes],
                                                            [r.P[self.nd.nodes] for r in normal_runs])


def get_context(name):
    if name not in _CONTEXTS:
        _CONTEXTS[name] = Context(name)
    return _CONTEXTS[name]


def analyze(ctx, test, models=None, use_demand=True, top_k=5, neighbor_weight=0.0, use_flow=True):
    """Detect, classify the cause and (if it is a leak) rank candidate nodes.

    Returns a dict with: features, event_class, probabilities, has_anomaly (adaptive detector),
    ranking (Series of node scores, best first) and per-node signals.
    """
    nd, ref = ctx.nd, ctx.ref
    feats = extract(nd, ref, test, use_demand)
    drop, rise, unacc, residual = node_signals(nd, ref, test, use_demand)
    has_anomaly = ctx.detector.is_anomalous(test.P[nd.nodes])
    out = {"features": feats, "has_anomaly": has_anomaly, "drop": drop, "rise": rise, "unacc": unacc,
           "residual": residual, "event_class": None, "probabilities": {}}
    if models is not None:
        row = pd.DataFrame([feats])[FEATURES]
        model = models["forest"]
        proba = model.predict_proba(row)[0]
        out["probabilities"] = {str(c): float(p) for c, p in zip(model.classes_, proba)}
        out["event_class"] = str(model.classes_[int(np.argmax(proba))])
        out["tree_class"] = str(models["tree"].predict(row)[0])
        if bool(quiet_mask(row).iloc[0]):   # everything within sensor noise: normal operation
            out["event_class"], out["tree_class"] = "normal", "normal"
            out["probabilities"] = {"normal": 1.0}
    out["ranking"] = Localizer(neighbor_weight=neighbor_weight, use_demand=use_demand, use_flow=use_flow).localize(nd, ref, test)
    return out
