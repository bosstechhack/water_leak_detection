import argparse
import json
import os
import warnings
import zlib

import numpy as np

from simulator import Simulator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
NETWORK_DIR = os.path.join(PROJECT_DIR, "data", "networks")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "data", "raw_simulations")
SCENARIO_FILE = os.path.join(BASE_DIR, "scenarios.json")
STABILITY_PROBE = {"type": "global_demand", "factor": 1.01, "start_hour": 0}
STABILITY_LIMIT_M = 5.0      # a node swinging more than this for a 1% demand change is ill-conditioned
STABILITY_HOUR_LIMIT_M = 0.5  # hours where 90% of nodes swing more than this are switching artefacts


def save_run(results, out_dir, sid, noise=None, seed=0):
    pressures = Simulator.extract_pressures(results)
    flows = Simulator.extract_flows(results)
    demands = Simulator.extract_demands(results)
    if noise:
        rng = np.random.default_rng(zlib.crc32(sid.encode()) + int(seed))
        pressures = Simulator.add_sensor_noise(pressures, absolute_std=noise.get("pressure_std", 0), rng=rng)
        flows = Simulator.add_sensor_noise(flows, relative_std=noise.get("flow_rel", 0), rng=rng)
        demands = Simulator.add_sensor_noise(demands, relative_std=noise.get("demand_rel", 0), rng=rng)
    pressures.to_csv(os.path.join(out_dir, f"{sid}_pressures.csv"))
    flows.to_csv(os.path.join(out_dir, f"{sid}_flows.csv"))
    demands.to_csv(os.path.join(out_dir, f"{sid}_demands.csv"))


def have_files(out_dir, sid):
    return all(os.path.isfile(os.path.join(out_dir, f"{sid}_{kind}.csv")) for kind in ("pressures", "flows", "demands"))


def find_unstable(sim, baseline):
    """Find nodes and hours whose pressure is not a reliable signal.

    A tiny (1%) demand change is applied. Nodes that swing wildly (for example discharge nodes of
    a pump that is switched off) and hours where most of the network swings (a control such as a
    pump start time shifting) are ill-conditioned, so detection and localization skip them.
    """
    probe = Simulator.extract_pressures(sim.run(STABILITY_PROBE))
    swing = (probe - Simulator.extract_pressures(baseline)).abs()
    nodes = swing.max()
    hours = swing.quantile(0.9, axis=1)
    return (sorted(str(n) for n in nodes[nodes > STABILITY_LIMIT_M].index),
            [int(t) for t in hours[hours > STABILITY_HOUR_LIMIT_M].index])


def run_checked(sim, scenario):
    """Run a scenario; raise if WNTR reports that the hydraulics did not converge."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        results = sim.run(scenario)
    if any("did not converge" in str(w.message) for w in caught):
        raise RuntimeError("hydraulic simulation did not converge")
    return results


def main():
    parser = argparse.ArgumentParser(description="Generate hydraulic scenario CSVs")
    parser.add_argument("--force", action="store_true", help="Regenerate and overwrite existing scenario CSVs")
    parser.add_argument("--network", help="Only this network (net1, net2, net3)")
    parser.add_argument("--only", help="Only this scenario id")
    args = parser.parse_args()
    with open(SCENARIO_FILE, encoding="utf-8") as f:
        config = json.load(f)
    duration = int(config.get("duration_hours", 24))

    for name, net in config["networks"].items():
        if args.network and args.network != name:
            continue
        network_file = os.path.join(NETWORK_DIR, net["file"])
        if not os.path.exists(network_file):
            raise FileNotFoundError(f"Network model not found: {network_file}")
        out_dir = os.path.join(OUTPUT_DIR, name)
        os.makedirs(out_dir, exist_ok=True)
        sim = Simulator(network_file, duration_hours=duration)

        baseline = None
        if args.force or not have_files(out_dir, "baseline") or not os.path.isfile(os.path.join(out_dir, "meta.json")):
            print(f"[{name}] baseline")
            baseline = sim.run_baseline()
            save_run(baseline, out_dir, "baseline")
            unstable, unstable_times = find_unstable(sim, baseline)
            with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
                json.dump({"network": name, "file": net["file"], "duration_hours": duration,
                           "unstable_nodes": unstable, "unstable_times": unstable_times}, f, indent=1)
            print(f"[{name}] excluded nodes: {unstable}; excluded times (s): {unstable_times}")

        manifest, failures = [], []
        for scenario in net["scenarios"]:
            sid = scenario["id"]
            if args.only and args.only != sid:
                continue
            manifest.append(scenario)
            if not args.force and have_files(out_dir, sid):
                continue
            try:
                results = run_checked(sim, scenario)
                save_run(results, out_dir, sid, scenario.get("sensor_noise"), scenario.get("noise_seed", 0))
            except Exception as error:  # keep going; report at the end
                failures.append({"id": sid, "error": repr(error)[:300]})
                manifest.pop()
                print(f"[{name}] FAILED {sid}: {error}")
        if args.only:
            continue
        with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"network": name, "scenarios": manifest}, f, indent=1)
        if failures:
            with open(os.path.join(out_dir, "failures.json"), "w", encoding="utf-8") as f:
                json.dump(failures, f, indent=1)
        print(f"[{name}] saved {len(manifest)} scenarios ({len(failures)} failed) to {out_dir}")


if __name__ == "__main__":
    main()
