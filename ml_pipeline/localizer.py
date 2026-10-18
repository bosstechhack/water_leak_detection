import numpy as np
import pandas as pd

from features import node_signals


class Localizer:
    """Topology-aware leak localizer.

    Two signals per node, each scaled to 0-1 by its own maximum:
      A(i) = unaccounted flow (balance change minus metered-demand change). A leak is the only
             thing that makes a node lose water that no meter accounts for, so A is the primary signal.
             If no node shows an unaccounted flow above noise, A is ignored.
      D(i) = persistent pressure drop (helps when flow data are weak or noisy).
    Score(i) = A(i) + pressure_weight * D(i), then smoothed over the pipe graph:
    Score'(i) = Score(i) + beta * mean(Score(j) for j adjacent to i). Pressure drops spread to
    neighbours, so a node surrounded by affected nodes can outrank an isolated spike.
    beta = 0 (the default) switches graph smoothing off. Evaluation showed smoothing lowers Top-1
    accuracy, so it is kept only as an option for comparison.
    """

    def __init__(self, pressure_weight=0.3, neighbor_weight=0.0, use_demand=True, use_flow=True):
        self.use_flow = use_flow
        self.pressure_weight = pressure_weight
        self.neighbor_weight = neighbor_weight
        self.use_demand = use_demand

    def localize(self, nd, ref, test):
        drop, _, unacc, _ = node_signals(nd, ref, test, self.use_demand)
        a = unacc / unacc.max() if (self.use_flow and unacc.max() >= 1.0) else unacc * 0.0
        d = drop / drop.max() if drop.max() > 0 else drop * 0.0
        score = a + self.pressure_weight * d
        if self.neighbor_weight:
            allowed = set(nd.nodes)
            smooth = {}
            for node in nd.nodes:
                neighbours = [n for n in nd.graph.neighbors(node) if n in allowed]
                smooth[node] = score[neighbours].mean() if neighbours else 0.0
            score = score + self.neighbor_weight * pd.Series(smooth)
        return score.sort_values(ascending=False)


class LegacyLocalizer:
    """Semester 1 baseline: peak pressure drop + 50 x positive flow divergence (no topology)."""

    def __init__(self, flow_weight=50.0):
        self.flow_weight = flow_weight

    def localize(self, nd, test):
        base, nodes = nd.baseline, nd.nodes
        scores = (base.P[nodes] - test.P[nodes]).max()
        div = (nd.divergence(test.F) - nd.divergence(base.F))[nodes].max().clip(lower=0)
        return (scores + self.flow_weight * div).sort_values(ascending=False)
