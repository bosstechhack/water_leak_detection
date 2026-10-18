import wntr


class Simulator:
    """Run repeatable hydraulic scenarios from a clean EPANET model."""

    def __init__(self, network_file, duration_hours=24):
        self.network_file = network_file
        self.duration_hours = duration_hours

    def run(self, scenario=None):
        scenario = scenario or {"type": "baseline"}
        wn = wntr.network.WaterNetworkModel(self.network_file)
        wn.options.time.duration = int(self.duration_hours * 3600)
        event_type = scenario.get("type", "baseline")
        start = int(scenario.get("start_hour", 12) * 3600)
        end = int(scenario.get("end_hour", self.duration_hours) * 3600)

        if event_type == "leak":
            node_name = str(scenario["node"])
            if node_name not in wn.junction_name_list:
                raise ValueError(f"Leak location {node_name} is not a junction in this network")
            wn.get_node(node_name).add_leak(
                wn, area=float(scenario["leak_area"]), start_time=start,
                end_time=end if end < self.duration_hours * 3600 else None,
            )
        elif event_type == "demand_change":
            node_name = str(scenario["node"])
            if node_name not in wn.junction_name_list:
                raise ValueError(f"Demand location {node_name} is not a junction in this network")
            node = wn.get_node(node_name)
            factor = float(scenario["factor"])
            pattern_step = int(wn.options.time.pattern_timestep)
            count = int(self.duration_hours * 3600 / pattern_step) + 1
            original = []
            for demand in node.demand_timeseries_list:
                if demand.pattern_name and demand.pattern_name in wn.pattern_name_list:
                    original = list(wn.get_pattern(demand.pattern_name).multipliers)
                    break
            if not original:
                original = [1.0]
            factors = [
                original[i % len(original)] * (1.0 if i * pattern_step < start else factor)
                for i in range(count)
            ]
            pattern_name = f"scenario_demand_{node_name}"
            wn.add_pattern(pattern_name, factors)
            demands = node.demand_timeseries_list
            if len(demands) == 0:
                raise ValueError(f"Junction {node_name} has no demand entry to modify")
            # Apply the scenario profile to each demand category at the selected junction.
            for demand in demands:
                demand.pattern_name = pattern_name
        elif event_type == "pump_outage":
            pump_name = str(scenario["pump"])
            if pump_name not in wn.pump_name_list:
                raise ValueError(f"Pump {pump_name} is not present in this network")
            wn.get_link(pump_name).add_outage(wn, start_time=start, end_time=end)
        elif event_type != "baseline":
            raise ValueError(f"Unsupported scenario type: {event_type}")

        results = wntr.sim.WNTRSimulator(wn).run_sim()
        return results

    def run_baseline(self):
        return self.run({"type": "baseline"})

    def run_leak_scenario(self, leak_node_name, leak_area, start_time):
        return self.run({"type": "leak", "node": str(leak_node_name),
                         "leak_area": leak_area, "start_hour": start_time / 3600})

    @staticmethod
    def extract_pressures(results):
        return results.node["pressure"]

    @staticmethod
    def extract_flows(results):
        return results.link["flowrate"]
