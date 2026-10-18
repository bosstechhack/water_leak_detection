import numpy as np
import wntr
from wntr.network.controls import Control, ControlAction, SimTimeCondition
from wntr.network.model import LinkStatus


class Simulator:
    """Run repeatable hydraulic scenarios from a clean EPANET model.

    A scenario is a dict. Simple scenarios have a ``type`` plus parameters; a
    ``combined`` scenario holds several of them in ``events``. Supported event
    types: leak, demand_change, global_demand, hydrant, pump_outage,
    reservoir_head, tank_level, pipe_close, pipe_throttle, roughness.
    """

    def __init__(self, network_file, duration_hours=24):
        self.network_file = network_file
        self.duration_hours = duration_hours

    # ------------------------------------------------------------------ helpers
    def _hours(self, event, key, default):
        return int(float(event.get(key, default)) * 3600)

    def _window(self, event):
        start = self._hours(event, "start_hour", 12)
        end = self._hours(event, "end_hour", self.duration_hours)
        return start, end

    @staticmethod
    def _base_multipliers(wn, pattern_name, count):
        """Hourly multipliers of an existing pattern, repeated to `count` steps."""
        name = pattern_name or wn.options.hydraulic.pattern
        if name and name in wn.pattern_name_list:
            original = list(wn.get_pattern(name).multipliers)
        else:
            original = [1.0]
        return [original[i % len(original)] for i in range(count)]

    def _pattern_steps(self, wn):
        step = int(wn.options.time.pattern_timestep)
        return step, int(self.duration_hours * 3600 / step) + 1

    def _scale_junction_demand(self, wn, node_name, factor, start, end):
        node = wn.get_node(node_name)
        if len(node.demand_timeseries_list) == 0:
            return
        step, count = self._pattern_steps(wn)
        for k, demand in enumerate(node.demand_timeseries_list):
            base = self._base_multipliers(wn, demand.pattern_name, count)
            factors = [base[i] * (factor if start <= i * step < end else 1.0) for i in range(count)]
            pname = f"scn_dem_{node_name}_{k}"
            if pname in wn.pattern_name_list:
                wn.remove_pattern(pname)
            wn.add_pattern(pname, factors)
            demand.pattern_name = pname

    def _check_junction(self, wn, name, what):
        if name not in wn.junction_name_list:
            raise ValueError(f"{what} location {name} is not a junction in this network")

    # ------------------------------------------------------------------- events
    def _apply(self, wn, event):
        kind = event.get("type")
        start, end = self._window(event)
        full = end >= self.duration_hours * 3600

        if kind == "leak":
            node = str(event["node"])
            self._check_junction(wn, node, "Leak")
            wn.get_node(node).add_leak(wn, area=float(event["leak_area"]), start_time=start,
                                       end_time=None if full else end)
        elif kind == "demand_change":
            node = str(event["node"])
            self._check_junction(wn, node, "Demand")
            self._scale_junction_demand(wn, node, float(event["factor"]), start, end)
        elif kind == "global_demand":
            for node in wn.junction_name_list:
                self._scale_junction_demand(wn, node, float(event["factor"]), start, end)
        elif kind == "hydrant":
            node = str(event["node"])
            self._check_junction(wn, node, "Hydrant")
            step, count = self._pattern_steps(wn)
            window = [1.0 if start <= i * step < end else 0.0 for i in range(count)]
            pname = f"scn_hydrant_{node}"
            wn.add_pattern(pname, window)
            wn.get_node(node).add_demand(float(event["flow"]), pname)
        elif kind == "pump_outage":
            pump = str(event["pump"])
            if pump not in wn.pump_name_list:
                raise ValueError(f"Pump {pump} is not present in this network")
            wn.get_link(pump).add_outage(wn, start_time=start, end_time=end)
        elif kind == "reservoir_head":
            name = str(event["reservoir"])
            if name not in wn.reservoir_name_list:
                raise ValueError(f"Reservoir {name} is not present in this network")
            res = wn.get_node(name)
            base = float(res.head_timeseries.base_value)
            ratio = (base + float(event["delta_m"])) / base
            step, count = self._pattern_steps(wn)
            factors = [ratio if start <= i * step < end else 1.0 for i in range(count)]
            pname = f"scn_head_{name}"
            wn.add_pattern(pname, factors)
            res.head_timeseries.pattern_name = pname
        elif kind == "tank_level":
            name = str(event["tank"])
            if name not in wn.tank_name_list:
                raise ValueError(f"Tank {name} is not present in this network")
            tank = wn.get_node(name)
            tank.init_level = tank.min_level + float(event["fraction"]) * (tank.max_level - tank.min_level)
        elif kind in ("pipe_close", "pipe_throttle"):
            pipe = str(event["pipe"])
            if pipe not in wn.pipe_name_list:
                raise ValueError(f"Pipe {pipe} is not present in this network")
            link = wn.get_link(pipe)
            if kind == "pipe_throttle":
                link.minor_loss = float(event.get("minor_loss", 5000.0))
            else:
                close = Control(SimTimeCondition(wn, "=", start),
                                ControlAction(link, "status", LinkStatus.Closed), name=f"close_{pipe}")
                wn.add_control(f"close_{pipe}", close)
                if not full:
                    reopen = Control(SimTimeCondition(wn, "=", end),
                                     ControlAction(link, "status", LinkStatus.Open), name=f"open_{pipe}")
                    wn.add_control(f"open_{pipe}", reopen)
        elif kind == "roughness":
            factor = float(event["factor"])
            for name in wn.pipe_name_list:
                wn.get_link(name).roughness *= factor
        elif kind != "baseline":
            raise ValueError(f"Unsupported scenario type: {kind}")

    # --------------------------------------------------------------------- run
    def run(self, scenario=None):
        scenario = scenario or {"type": "baseline"}
        wn = wntr.network.WaterNetworkModel(self.network_file)
        wn.options.time.duration = int(self.duration_hours * 3600)
        wn.options.hydraulic.demand_model = "PDD"
        events = scenario.get("events") if scenario.get("type") == "combined" else [scenario]
        for event in events:
            self._apply(wn, event)
        return wntr.sim.WNTRSimulator(wn).run_sim()

    def run_baseline(self):
        return self.run({"type": "baseline"})

    def run_leak_scenario(self, leak_node_name, leak_area, start_time):
        return self.run({"type": "leak", "node": str(leak_node_name),
                         "leak_area": leak_area, "start_hour": start_time / 3600})

    # --------------------------------------------------------------- extraction
    @staticmethod
    def extract_pressures(results):
        return results.node["pressure"]

    @staticmethod
    def extract_flows(results):
        return results.link["flowrate"]

    @staticmethod
    def extract_demands(results):
        """Consumer (metered) demand delivered at each node, leak flow excluded."""
        return results.node["demand"]

    @staticmethod
    def add_sensor_noise(frame, absolute_std=0.0, relative_std=0.0, rng=None):
        """Return a copy with Gaussian measurement noise (fixed seed via rng)."""
        rng = rng or np.random.default_rng(0)
        noisy = frame.copy()
        values = frame.to_numpy(dtype=float)
        noise = rng.normal(0.0, 1.0, values.shape) * (absolute_std + relative_std * np.abs(values))
        noisy.loc[:, :] = values + noise
        return noisy
