"""Load simulated scenarios and network topology for one network."""
import json
import os
from dataclasses import dataclass

import networkx as nx
import numpy as np
import pandas as pd
import wntr

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT, "data", "raw_simulations")
NETWORK_DIR = os.path.join(ROOT, "data", "networks")
RESULTS_DIR = os.path.join(ROOT, "data", "results")


@dataclass
class Frames:
    """Time series for one scenario: pressures, link flows and metered node demands."""
    P: pd.DataFrame
    F: pd.DataFrame
    D: pd.DataFrame


def available_networks():
    if not os.path.isdir(DATA_DIR):
        return []
    return sorted(n for n in os.listdir(DATA_DIR)
                  if os.path.isfile(os.path.join(DATA_DIR, n, "manifest.json")))


class NetworkData:
    """Topology plus saved simulation data for one network (net1, net2, net3)."""

    def __init__(self, name):
        self.name = name
        self.dir = os.path.join(DATA_DIR, name)
        with open(os.path.join(self.dir, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        with open(os.path.join(self.dir, "manifest.json"), encoding="utf-8") as f:
            self.manifest = json.load(f)["scenarios"]
        self.network_file = os.path.join(NETWORK_DIR, meta["file"])
        self.unstable_nodes = set(meta.get("unstable_nodes", []))
        self.unstable_times = set(meta.get("unstable_times", []))

        self.wn = wntr.network.WaterNetworkModel(self.network_file)
        self.junctions = [str(n) for n in self.wn.junction_name_list]
        self.nodes = [n for n in self.junctions if n not in self.unstable_nodes]   # analysed junctions
        self.all_nodes = [str(n) for n in self.wn.node_name_list]
        self.links = [str(n) for n in self.wn.link_name_list]
        self.reservoirs = [str(n) for n in self.wn.reservoir_name_list]
        self.tanks = [str(n) for n in self.wn.tank_name_list]
        self.pumps = [str(n) for n in self.wn.pump_name_list]

        # Pipe graph (undirected). Edge weight = pipe length in metres; pumps and valves count as 1 m.
        self.graph = nx.Graph()
        self.graph.add_nodes_from(self.all_nodes)
        for lname in self.links:
            link = self.wn.get_link(lname)
            length = float(getattr(link, "length", 1.0) or 1.0)
            self.graph.add_edge(str(link.start_node_name), str(link.end_node_name), weight=length, link=lname)

        # Incidence matrix: +1 where the link ends at the node (inflow), -1 where it starts there.
        node_pos = {n: i for i, n in enumerate(self.all_nodes)}
        self.incidence = np.zeros((len(self.all_nodes), len(self.links)))
        for j, lname in enumerate(self.links):
            link = self.wn.get_link(lname)
            self.incidence[node_pos[str(link.start_node_name)], j] = -1.0
            self.incidence[node_pos[str(link.end_node_name)], j] = 1.0
        self.node_pos = node_pos
        self.degree = dict(self.graph.degree())
        self.elevation = {str(n): float(getattr(self.wn.get_node(n), "elevation", 0.0) or 0.0)
                          for n in self.wn.node_name_list}
        self.baseline = self.load("baseline")

    def scenarios(self):
        return self.manifest

    def scenario(self, sid):
        for item in self.manifest:
            if item["id"] == sid:
                return item
        return None

    def load(self, sid):
        def read(kind):
            frame = pd.read_csv(os.path.join(self.dir, f"{sid}_{kind}.csv"), index_col=0)
            frame.columns = frame.columns.astype(str)
            return frame.loc[[t for t in frame.index if int(t) not in self.unstable_times]]
        return Frames(P=read("pressures"), F=read("flows"), D=read("demands"))

    def divergence(self, F):
        """Net inflow minus outflow at every node (rows = time, columns = all_nodes)."""
        values = F[self.links].to_numpy(dtype=float) @ self.incidence.T
        return pd.DataFrame(values, index=F.index, columns=self.all_nodes)

    def hops(self, a, b):
        try:
            return nx.shortest_path_length(self.graph, a, b)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return float("nan")

    def distance_m(self, a, b):
        try:
            return float(nx.shortest_path_length(self.graph, a, b, weight="weight"))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return float("nan")

    def node_type(self, node):
        """Dead end, hub or ordinary junction, for result breakdowns."""
        d = self.degree.get(node, 0)
        return "dead-end" if d == 1 else ("hub" if d >= 4 else "inline")
