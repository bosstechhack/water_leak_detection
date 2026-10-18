"""Build simulation/scenarios.json: a scenario matrix for several networks.

Scenario ids and parameters are generated from each network's own topology, so
node, pipe, pump, tank and reservoir ids are always valid for that network.
"""
import json
import os
import warnings

import networkx as nx
import numpy as np
import wntr

from simulator import Simulator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NETWORK_DIR = os.path.join(BASE_DIR, "..", "data", "networks")
OUTPUT = os.path.join(BASE_DIR, "scenarios.json")
NETWORKS = {"net1": "Net1.inp", "net2": "Net2.inp", "net3": "Net3.inp"}

DURATION_HOURS = 24
SWEEP_AREA = 0.001          # m2, orifice area used in the all-junction sweep
LEAK_SIZES = [0.0001, 0.0003, 0.001, 0.003, 0.01]
LEAK_STARTS = [2, 8, 12, 20]
NOISE_LOW = {"pressure_std": 0.05, "flow_rel": 0.005, "demand_rel": 0.005}
NOISE_HIGH = {"pressure_std": 0.2, "flow_rel": 0.02, "demand_rel": 0.02}


def leak(node, area, start=12):
    return {"type": "leak", "node": node, "leak_area": area, "start_hour": start}


def topology(name, path):
    wn = wntr.network.WaterNetworkModel(path)
    sim = Simulator(path, DURATION_HOURS)
    base = sim.run_baseline()
    graph = nx.Graph(wn.to_graph().to_undirected())
    junctions = list(wn.junction_name_list)
    demand = {j: sum(d.base_value for d in wn.get_node(j).demand_timeseries_list) for j in junctions}
    pressure = base.node["pressure"][junctions].mean()
    flows = base.link["flowrate"].abs().mean()
    return wn, base, graph, junctions, demand, pressure, flows


def representative_nodes(graph, junctions, demand, pressure):
    picks = []
    degree = dict(graph.degree())

    def add(candidates, key, reverse=False):
        pool = [n for n in candidates if n not in picks]
        if pool:
            picks.append(sorted(pool, key=key, reverse=reverse)[0])

    dead = [n for n in junctions if degree[n] == 1]
    add(dead, lambda n: demand[n])                       # dead end, low demand
    add(dead, lambda n: demand[n], reverse=True)         # dead end, high demand
    add(junctions, lambda n: degree[n], reverse=True)    # most connected hub
    add(junctions, lambda n: demand[n], reverse=True)    # highest demand
    add(junctions, lambda n: pressure[n])                # lowest pressure
    add(junctions, lambda n: pressure[n], reverse=True)  # highest pressure
    return picks


def converges(path, event):
    """True if the scenario's hydraulics converge (blockages can make Net3 diverge)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            Simulator(path, DURATION_HOURS).run(event)
        except Exception:
            return False
    return not any("did not converge" in str(w.message) for w in caught)


def active_window(base, pump, length=4):
    """First `length` hours in which the pump actually carries flow in the baseline."""
    flow = base.link["flowrate"][pump]
    hours = [int(t // 3600) for t in flow.index if abs(flow[t]) > 1e-6]
    hours = [h for h in hours if h < DURATION_HOURS]
    if not hours:
        return None
    start = hours[0] if hours[0] > 0 else (hours[1] if len(hours) > 1 else 0)
    return start, min(start + length, DURATION_HOURS)


def build_network(name, filename):
    path = os.path.join(NETWORK_DIR, filename)
    wn, base, graph, junctions, demand, pressure, flows = topology(name, path)
    reps = representative_nodes(graph, junctions, demand, pressure)
    sc = []

    def add(sid, group, event_class, spec, truth=None, noise=None):
        item = {"id": f"{name}_{sid}", "group": group, "event_class": event_class, **spec}
        item["truth_nodes"] = truth or []
        if noise:
            item["sensor_noise"] = noise
        sc.append(item)

    # Normal operation (no event): sensor noise only, used for false-alarm testing.
    for k, (label, noise) in enumerate([("low", NOISE_LOW)] * 8 + [("high", NOISE_HIGH)] * 8):
        add(f"normal_{label}_{k}", "normal", "normal", {"type": "baseline", "noise_seed": k}, noise=noise)

    add("normal_clean", "normal", "normal", {"type": "baseline"})
    add("normal_vlow", "normal", "normal", {"type": "baseline", "noise_seed": 9},
        noise={"pressure_std": 0.01, "flow_rel": 0.001, "demand_rel": 0.001})

    # Leaks: sweep over every junction, then size / start-time / noise variations.
    for node in junctions:
        add(f"leak_{node}", "leak_sweep", "leak", leak(node, SWEEP_AREA), [node])
    for node in reps:
        for area in LEAK_SIZES:
            add(f"leak_{node}_area{area:g}", "leak_size", "leak", leak(node, area), [node])
    for node in reps[:2]:
        for start in LEAK_STARTS:
            add(f"leak_{node}_start{start}", "leak_start", "leak", leak(node, SWEEP_AREA, start), [node])
    for node in reps:
        add(f"leak_{node}_noisy", "leak_noisy", "leak", leak(node, SWEEP_AREA), [node], NOISE_LOW)

    # Demand changes (not leaks).
    for node in reps[:3]:
        add(f"demand_up_{node}", "demand", "demand_change",
            {"type": "demand_change", "node": node, "factor": 1.5, "start_hour": 12})
        add(f"demand_down_{node}", "demand", "demand_change",
            {"type": "demand_change", "node": node, "factor": 0.5, "start_hour": 12})
    add("demand_global_up", "demand", "demand_change", {"type": "global_demand", "factor": 1.3, "start_hour": 12})
    add("demand_global_down", "demand", "demand_change", {"type": "global_demand", "factor": 0.7, "start_hour": 12})
    for node in reps[:2]:
        add(f"hydrant_{node}", "demand", "demand_change",
            {"type": "hydrant", "node": node, "flow": 0.01, "start_hour": 10, "end_hour": 14})

    # Source / pump / reservoir changes.
    for pump in wn.pump_name_list:
        for length in (2, 4, 6):
            window = active_window(base, pump, length)
            if window:
                add(f"pump_outage_{pump}_{length}h", "source", "source_event",
                    {"type": "pump_outage", "pump": pump, "start_hour": window[0], "end_hour": window[1]})
    for res in wn.reservoir_name_list:
        for delta in (-10.0, -5.0, -2.0, 2.0, 5.0, 10.0):
            add(f"reservoir_head_{res}_{delta:+g}m", "source", "source_event",
                {"type": "reservoir_head", "reservoir": res, "delta_m": delta, "start_hour": 12})

    # Tank changes.
    for tank in wn.tank_name_list[:3]:
        for frac in (0.1, 0.2, 0.3, 0.7, 0.9):
            add(f"tank_{tank}_level{int(frac * 100)}", "tank", "tank_event",
                {"type": "tank_level", "tank": tank, "fraction": frac})
        links = [l for l in wn.get_links_for_node(tank) if l in wn.pipe_name_list]
        if links:
            add(f"tank_{tank}_isolate", "tank", "tank_event",
                {"type": "pipe_close", "pipe": links[0], "start_hour": 10})

    # Blocked or throttled pipes: busiest pipes between two junctions that do not cut the network.
    bridges = {frozenset(b) for b in nx.bridges(graph)}
    eligible = [p for p in wn.pipe_name_list
                if wn.get_link(p).start_node_name in junctions and wn.get_link(p).end_node_name in junctions
                and frozenset((wn.get_link(p).start_node_name, wn.get_link(p).end_node_name)) not in bridges]
    eligible.sort(key=lambda p: flows[p], reverse=True)
    closers = [p for p in eligible if converges(path, {"type": "pipe_close", "pipe": p, "start_hour": 10})][:5]
    throttlers = [p for p in eligible if p not in closers and
                  converges(path, {"type": "pipe_throttle", "pipe": p, "minor_loss": 5000.0})][:3]
    for pipe in closers:
        add(f"pipe_close_{pipe}", "blockage", "valve_block", {"type": "pipe_close", "pipe": pipe, "start_hour": 10})
    for pipe in throttlers:
        add(f"pipe_throttle_{pipe}", "blockage", "valve_block",
            {"type": "pipe_throttle", "pipe": pipe, "minor_loss": 5000.0})

    # Ageing: all pipes rougher.
    for factor in (0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95):
        add(f"ageing_roughness_{int(factor * 100)}", "ageing", "ageing", {"type": "roughness", "factor": factor})

    # Leaks hidden behind another disturbance. The truth is still the leak.
    pumps = [(p, active_window(base, p)) for p in wn.pump_name_list]
    pumps = [(p, w) for p, w in pumps if w]
    for node in reps[:4]:
        other = next((n for n in reps if n != node), junctions[0])
        add(f"leak_{node}_with_demand", "leak_confounded", "leak",
            {"type": "combined", "events": [leak(node, SWEEP_AREA),
                                            {"type": "global_demand", "factor": 1.3, "start_hour": 8}]}, [node])
        add(f"leak_{node}_with_hydrant", "leak_confounded", "leak",
            {"type": "combined", "events": [leak(node, SWEEP_AREA),
                                            {"type": "hydrant", "node": other, "flow": 0.01,
                                             "start_hour": 10, "end_hour": 14}]}, [node])
        if closers and converges(path, {"type": "combined", "events": [leak(node, SWEEP_AREA),
                {"type": "pipe_close", "pipe": closers[0], "start_hour": 8}]}):
            add(f"leak_{node}_with_blockage", "leak_confounded", "leak",
                {"type": "combined", "events": [leak(node, SWEEP_AREA),
                                                {"type": "pipe_close", "pipe": closers[0], "start_hour": 8}]}, [node])
        if pumps:
            pump, window = pumps[0]
            add(f"leak_{node}_with_pump_outage", "leak_confounded", "leak",
                {"type": "combined", "events": [leak(node, SWEEP_AREA),
                                                {"type": "pump_outage", "pump": pump,
                                                 "start_hour": window[0], "end_hour": window[1]}]}, [node])
    # Sensor-noise twins of the non-leak events, so the classifier also sees noisy measurements.
    for item in list(sc):
        if item["event_class"] in ("demand_change", "source_event", "tank_event", "valve_block", "ageing"):
            sc.append({**item, "id": item["id"] + "_noisy", "sensor_noise": NOISE_LOW})
    return {"file": filename, "scenarios": sc}


def main():
    config = {"duration_hours": DURATION_HOURS, "networks": {}}
    for name, filename in NETWORKS.items():
        config["networks"][name] = build_network(name, filename)
        print(f"{name}: {len(config['networks'][name]['scenarios'])} scenarios")
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=1)
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
