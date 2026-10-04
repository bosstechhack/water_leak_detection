import os
import pandas as pd
from simulator import Simulator
from download_networks import download_network

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NETWORK_FILE = os.path.abspath(os.path.join(BASE_DIR, '../data/networks/Net3.inp'))
OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, '../data/raw_simulations'))

def main():
    if not os.path.exists(NETWORK_FILE):
        print(f"{NETWORK_FILE} not found. Attempting automatic download/setup...")
        download_network()

    if not os.path.exists(NETWORK_FILE):
        print(f"Error: Could not obtain {NETWORK_FILE}.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    sim = Simulator(NETWORK_FILE)

    print("Running baseline simulation for Net3...")
    baseline_results = sim.run_baseline()
    
    baseline_pressures = sim.extract_pressures(baseline_results)
    baseline_flows = sim.extract_flows(baseline_results)
    
    baseline_pressures.to_csv(os.path.join(OUTPUT_DIR, 'baseline_pressures.csv'))
    baseline_flows.to_csv(os.path.join(OUTPUT_DIR, 'baseline_flows.csv'))
    print("Baseline saved.")

    # Generate leak scenarios:
    # 1. Node 15 (Branch / Outer Node)
    # 2. Node 115 (Central 4-Way Intersection Node)
    scenarios = [
        {'node': '15', 'area': 0.05, 'start': 12 * 3600},
        {'node': '115', 'area': 0.03, 'start': 12 * 3600},
    ]

    for sc in scenarios:
        leak_node = sc['node']
        leak_area = sc['area']
        leak_start = sc['start']

        print(f"Running leak scenario at node {leak_node}...")
        leak_results = sim.run_leak_scenario(leak_node, leak_area, leak_start)
        
        leak_pressures = sim.extract_pressures(leak_results)
        leak_flows = sim.extract_flows(leak_results)
        
        leak_pressures.to_csv(os.path.join(OUTPUT_DIR, f'leak_{leak_node}_pressures.csv'))
        leak_flows.to_csv(os.path.join(OUTPUT_DIR, f'leak_{leak_node}_flows.csv'))
        print(f"Leak scenario at node {leak_node} saved.")

if __name__ == "__main__":
    main()

