"""Scenario catalog: reads the generated manifests and keeps a copy in SQLite (table `scenarios`)."""
import json
import os
import sys

from sqlalchemy.orm import Session

from models import ScenarioRecord

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ml_pipeline")))
from split import get_split  # noqa: E402

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "raw_simulations"))
NETWORK_FILES = {"net1": "Net1.inp", "net2": "Net2.inp", "net3": "Net3.inp"}


def describe(spec):
    """Readable name for a scenario spec."""
    kind = spec.get("type")
    hour = lambda e: f"{float(e.get('start_hour', 12)):g}:00"
    if kind == "baseline":
        noise = spec.get("sensor_noise")
        return "Normal operation" + (f" (sensor noise {noise.get('pressure_std', 0):g} m)" if noise else "")
    if kind == "leak":
        return f"Leak at node {spec['node']} ({spec['leak_area']:g} m2, from {hour(spec)})"
    if kind == "demand_change":
        return f"Demand at node {spec['node']} x{spec['factor']:g} (from {hour(spec)})"
    if kind == "global_demand":
        return f"All demands x{spec['factor']:g} (from {hour(spec)})"
    if kind == "hydrant":
        return f"Hydrant flow at node {spec['node']} ({hour(spec)} to {float(spec.get('end_hour', 24)):g}:00)"
    if kind == "pump_outage":
        return f"Pump {spec['pump']} outage ({hour(spec)} to {float(spec.get('end_hour', 24)):g}:00)"
    if kind == "reservoir_head":
        return f"Reservoir {spec['reservoir']} head {spec['delta_m']:+g} m"
    if kind == "tank_level":
        return f"Tank {spec['tank']} starts at {spec['fraction'] * 100:.0f}% level"
    if kind == "pipe_close":
        return f"Pipe {spec['pipe']} closed (from {hour(spec)})"
    if kind == "pipe_throttle":
        return f"Pipe {spec['pipe']} partly blocked"
    if kind == "roughness":
        return f"Pipe ageing (roughness x{spec['factor']:g})"
    if kind == "combined":
        return " + ".join(describe(e) for e in spec["events"])
    return spec.get("id", "scenario")


SIZE_LABELS = [(0.0001, "Tiny"), (0.0003, "Small"), (0.001, "Medium"), (0.003, "Large"), (0.01, "Burst")]
EVENT_KINDS = {"leak": "leak", "demand_change": "demand", "global_demand": "demand", "hydrant": "demand",
               "pump_outage": "source", "reservoir_head": "source", "tank_level": "tank", "pipe_close": "blockage",
               "pipe_throttle": "blockage", "roughness": "ageing", "baseline": "normal"}


def params(spec):
    """Structured facts about a scenario, used by the dashboard's guided picker."""
    events = spec["events"] if spec.get("type") == "combined" else [spec]
    out = {"category": spec["event_class"], "noisy": bool(spec.get("sensor_noise")), "hidden_by": None,
           "node": None, "size": None, "size_label": None, "start_hour": None}
    for event in events:
        kind = event.get("type")
        if kind == "leak":
            out["node"] = str(event["node"])
            out["size"] = event["leak_area"]
            out["size_label"] = min(SIZE_LABELS, key=lambda s: abs(s[0] - event["leak_area"]))[1]
            out["start_hour"] = event.get("start_hour", 12)
        elif spec.get("type") == "combined":
            out["hidden_by"] = EVENT_KINDS.get(kind, kind)
        else:
            out["node"] = str(event["node"]) if event.get("node") else None
            out["kind"] = kind
            for key in ("factor", "pump", "reservoir", "tank", "pipe", "delta_m", "fraction"):
                if key in event:
                    out[key] = event[key]
    return out


def load_manifests():
    items = []
    if not os.path.isdir(DATA_DIR):
        return items
    for name in sorted(os.listdir(DATA_DIR)):
        path = os.path.join(DATA_DIR, name, "manifest.json")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                for spec in json.load(f)["scenarios"]:
                    items.append({"network": name, "spec": spec})
    return items


def sync(db: Session):
    """Replace the SQLite scenario table with the current manifests."""
    # the table layout may have changed since the database was created, so rebuild it
    ScenarioRecord.__table__.drop(db.get_bind(), checkfirst=True)
    ScenarioRecord.__table__.create(db.get_bind())
    for item in load_manifests():
        spec = item["spec"]
        db.add(ScenarioRecord(id=spec["id"], network=item["network"], name=describe(spec),
                              scenario_group=spec["group"], event_class=spec["event_class"],
                              truth_nodes="|".join(spec.get("truth_nodes", [])),
                              params_json=json.dumps({**params(spec), "split": get_split().get(spec["id"], "train")}),
                              csv_dir=os.path.join(DATA_DIR, item["network"])))
    # the baseline is always available for every network
    for name in {i["network"] for i in load_manifests()}:
        db.add(ScenarioRecord(id=f"{name}_baseline", network=name, name="Baseline (no event)",
                              scenario_group="baseline", event_class="normal", truth_nodes="",
                              params_json=json.dumps({"category": "normal", "noisy": False, "hidden_by": None, "node": None,
                                                      "size": None, "size_label": None, "start_hour": None,
                                                      "split": "reference"}),
                              csv_dir=os.path.join(DATA_DIR, name)))
    db.commit()
