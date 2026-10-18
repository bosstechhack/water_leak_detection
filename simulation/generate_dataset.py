import json
import os
import argparse
import pandas as pd
from simulator import Simulator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
NETWORK_FILE = os.path.join(PROJECT_DIR, "data", "networks", "Net3.inp")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "data", "raw_simulations")
SCENARIO_FILE = os.path.join(BASE_DIR, "scenarios.json")


def main():
    parser = argparse.ArgumentParser(description="Generate hydraulic scenario CSVs")
    parser.add_argument("--force", action="store_true", help="Regenerate and overwrite existing scenario CSVs")
    args = parser.parse_args()
    if not os.path.exists(NETWORK_FILE):
        raise FileNotFoundError(f"Network model not found: {NETWORK_FILE}")
    with open(SCENARIO_FILE, encoding="utf-8") as f:
        config = json.load(f)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    duration_hours = int(config.get("duration_hours", 24))
    simulator = Simulator(NETWORK_FILE, duration_hours=duration_hours)
    scenarios = [{"id": "baseline", "type": "baseline"}, *config["scenarios"]]
    metadata = []

    for scenario in scenarios:
        scenario_id = scenario["id"]
        pressure_path = os.path.join(OUTPUT_DIR, f"{scenario_id}_pressures.csv")
        flow_path = os.path.join(OUTPUT_DIR, f"{scenario_id}_flows.csv")
        if not args.force and os.path.isfile(pressure_path) and os.path.isfile(flow_path):
            print(f"Keeping existing data for {scenario_id}; use --force to regenerate")
            metadata.append({"scenario_id": scenario_id, **scenario,
                             "network": os.path.basename(NETWORK_FILE),
                             "duration_hours": duration_hours})
            continue
        print(f"Simulating {scenario_id}...")
        results = simulator.run(scenario)
        Simulator.extract_pressures(results).to_csv(
            pressure_path)
        Simulator.extract_flows(results).to_csv(
            flow_path)
        metadata.append({"scenario_id": scenario_id, **scenario,
                         "network": os.path.basename(NETWORK_FILE),
                         "duration_hours": duration_hours})

    pd.DataFrame(metadata).to_csv(os.path.join(OUTPUT_DIR, "scenarios.csv"), index=False)
    print(f"Saved {len(scenarios)} scenarios and metadata to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
