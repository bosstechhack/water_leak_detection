import wntr
import pandas as pd
import os

class Simulator:
    def __init__(self, network_file):
        """Initialize the simulator with an EPANET .inp file."""
        self.network_file = network_file
        self.wn = wntr.network.WaterNetworkModel(network_file)
        
    def run_baseline(self):
        """Run the simulation without any leaks and return the results."""
        # Reset the network state
        self.wn = wntr.network.WaterNetworkModel(self.network_file)
        # Set simulation to exactly 24 hours
        self.wn.options.time.duration = 24 * 3600
        sim = wntr.sim.WNTRSimulator(self.wn)
        results = sim.run_sim()
        return results
        
    def run_leak_scenario(self, leak_node_name, leak_area, start_time):
        """
        Run the simulation with a leak at a specific node.
        leak_area: Size of the leak in square meters.
        start_time: Time in seconds when the leak starts.
        """
        self.wn = wntr.network.WaterNetworkModel(self.network_file)
        # Set simulation to exactly 24 hours
        self.wn.options.time.duration = 24 * 3600
        
        # Add a leak to the specified node
        node = self.wn.get_node(leak_node_name)
        node.add_leak(self.wn, area=leak_area, start_time=start_time)
        
        sim = wntr.sim.WNTRSimulator(self.wn)
        results = sim.run_sim()
        return results

    def extract_pressures(self, results):
        """Extract junction pressures into a DataFrame."""
        return results.node['pressure']

    def extract_flows(self, results):
        """Extract pipe flows into a DataFrame."""
        return results.link['flowrate']
