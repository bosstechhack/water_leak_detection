"""Event-cause classifier: leak, demand change, source (pump/reservoir), tank, blocked pipe, ageing, normal."""
import os

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier, export_text

from features import FEATURES

CLASSES = ["normal", "leak", "demand_change", "source_event", "tank_event", "valve_block", "ageing"]
LABELS = {
    "normal": "Normal operation",
    "leak": "Leak",
    "demand_change": "Demand change",
    "source_event": "Pump / reservoir change",
    "tank_event": "Tank change",
    "valve_block": "Blocked or throttled pipe",
    "ageing": "Pipe ageing (roughness)",
}
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "event_classifier.joblib")


def make_model(kind="forest"):
    if kind == "tree":   # shallow tree: its rules can be printed and explained
        return DecisionTreeClassifier(max_depth=4, class_weight="balanced", random_state=0)
    return RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=0, n_jobs=1)


def tree_rules(tree):
    return export_text(tree, feature_names=FEATURES)


def save(models, path=MODEL_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(models, path)


def load(path=MODEL_PATH):
    return joblib.load(path) if os.path.isfile(path) else None
