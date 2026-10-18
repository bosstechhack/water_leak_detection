"""Signals and features that tell a leak apart from demand, pump, tank, valve and ageing changes.

All quantities compare a scenario with the network's normal-operation baseline. Thresholds are
learned from the network's own normal runs (sensor noise only), so features are comparable
across networks.

Physics used:
  * node balance: inflow - outflow = metered demand + leak flow, so
    unaccounted flow = change in balance - change in metered demand = leak flow.
  * a leak is local and unmetered; a demand change is metered; pump, reservoir and tank changes
    move pressure over a wide area; a blocked pipe lowers pressure downstream and raises it upstream.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from detector import persistent_peak

PERSISTENCE = 2
K_SIGMA = 4.0
EPS = 1e-9

FEATURES = [
    "drop_ratio",        # largest persistent pressure drop / noise threshold
    "frac_hit",          # share of junctions with a persistent drop above threshold
    "median_ratio",      # median node drop / threshold (uniform shift when high)
    "conc_drop",         # share of the total drop sitting at the worst node
    "rise_ratio",        # largest persistent pressure rise / threshold
    "frac_rise",         # share of junctions with a persistent rise
    "flow_frac",         # share of pipes with a persistent flow change
    "source_change",     # change in reservoir supply / total demand
    "tank_change",       # change in tank net flow / total demand
    "pump_drop",         # largest relative loss of pump flow (1 = pump off)
    "unacc_ratio",       # largest unaccounted flow at a node / noise threshold
    "unacc_conc",        # share of unaccounted flow at the worst node
    "demand_frac",       # share of nodes with a metered demand change
    "demand_total",      # signed total metered demand change / total demand
]


@dataclass
class Reference:
    """Noise levels learned from a network's normal-operation runs."""
    p_threshold: float
    f_sigma: pd.Series
    u_sigma: dict      # keyed by use_demand (True / False): per-node sigma of unaccounted flow
    d_sigma: pd.Series
    total_demand: float


def _unaccounted(nd, base, test, nodes, use_demand=True):
    """Change in node flow balance, minus the change in metered demand when demand data is used."""
    delta = nd.divergence(test.F) - nd.divergence(base.F)
    delta = delta[nodes]
    if use_demand:
        delta = delta - (test.D[nodes] - base.D[nodes])
    return delta


def unaccounted_flow(nd, base, test, nodes, use_demand=True):
    """Public wrapper: time series of unaccounted flow (m3/s) at each node."""
    return _unaccounted(nd, base, test, nodes, use_demand)


def calibrate(nd, normal_runs=None):
    """Learn noise thresholds from the network's normal runs."""
    base = nd.baseline
    runs = normal_runs
    if runs is None:
        runs = [nd.load(s["id"]) for s in nd.scenarios() if s["event_class"] == "normal"]
    nodes = nd.nodes
    p_res = np.concatenate([(base.P[nodes] - r.P[nodes]).to_numpy().ravel() for r in runs])
    p_threshold = max(0.1, K_SIGMA * float(np.nanstd(p_res)))
    f_sigma = pd.concat([(r.F[nd.links] - base.F[nd.links]) for r in runs]).std()
    d_sigma = pd.concat([(r.D[nodes] - base.D[nodes]) for r in runs]).std()
    u_sigma = {}
    for flag in (True, False):
        u = pd.concat([_unaccounted(nd, base, r, nodes, flag) for r in runs])
        u_sigma[flag] = u.std()
    total_demand = float(base.D[nodes].clip(lower=0).sum(axis=1).mean())   # consumers only (Net2 has a negative-demand source)
    return Reference(p_threshold=p_threshold, f_sigma=f_sigma.fillna(0.0), u_sigma=u_sigma,
                     d_sigma=d_sigma.fillna(0.0), total_demand=max(total_demand, EPS))


def node_signals(nd, ref, test, use_demand=True):
    """Per-node pressure drop (in units of threshold) and unaccounted flow (in units of threshold)."""
    base, nodes = nd.baseline, nd.nodes
    residual = base.P[nodes] - test.P[nodes]
    drop = persistent_peak(residual, PERSISTENCE).clip(lower=0) / ref.p_threshold
    rise = persistent_peak(-residual, PERSISTENCE).clip(lower=0) / ref.p_threshold
    u = _unaccounted(nd, base, test, nodes, use_demand)
    sigma = ref.u_sigma[use_demand].reindex(nodes).fillna(0.0).clip(lower=1e-6)
    unacc = persistent_peak(u, PERSISTENCE).clip(lower=0) / (K_SIGMA * sigma)
    return drop, rise, unacc, residual


def extract(nd, ref, test, use_demand=True):
    """Feature dictionary for one scenario."""
    base, nodes = nd.baseline, nd.nodes
    drop, rise, unacc, _ = node_signals(nd, ref, test, use_demand)
    f = {}
    f["drop_ratio"] = float(drop.max())
    f["frac_hit"] = float((drop > 1).mean())
    f["median_ratio"] = float(drop.median())
    f["conc_drop"] = float(drop.max() / (drop.sum() + EPS))
    f["rise_ratio"] = float(rise.max())
    f["frac_rise"] = float((rise > 1).mean())

    dflow = (test.F[nd.links] - base.F[nd.links])
    flow_z = persistent_peak(dflow.abs(), PERSISTENCE) / (K_SIGMA * ref.f_sigma.reindex(nd.links).clip(lower=1e-6))
    f["flow_frac"] = float((flow_z > 1).mean())

    ddiv = nd.divergence(test.F) - nd.divergence(base.F)
    supply = -ddiv[nd.reservoirs].sum(axis=1) if nd.reservoirs else pd.Series(0.0, index=ddiv.index)
    tank = ddiv[nd.tanks].sum(axis=1) if nd.tanks else pd.Series(0.0, index=ddiv.index)
    f["source_change"] = float(supply.abs().max() / ref.total_demand)
    f["tank_change"] = float(tank.abs().max() / ref.total_demand)
    pump_drop = 0.0
    for pump in nd.pumps:
        scale = max(float(base.F[pump].abs().max()), EPS)
        pump_drop = max(pump_drop, float(((base.F[pump] - test.F[pump]) / scale).max()))
    f["pump_drop"] = float(np.clip(pump_drop, 0.0, 1.0))

    f["unacc_ratio"] = float(unacc.max())
    f["unacc_conc"] = float(unacc.max() / (unacc.sum() + EPS))
    if use_demand:
        d_delta = test.D[nodes] - base.D[nodes]
        d_sigma = ref.d_sigma.reindex(nodes).clip(lower=1e-6)
        d_z = persistent_peak(d_delta.abs(), PERSISTENCE) / (K_SIGMA * d_sigma)
        f["demand_frac"] = float((d_z > 1).mean())
        total = d_delta.sum(axis=1)
        f["demand_total"] = float(total.iloc[int(np.argmax(total.abs().to_numpy()))] / ref.total_demand)
    else:
        f["demand_frac"] = 0.0
        f["demand_total"] = 0.0
    return {name: f[name] for name in FEATURES}


def quiet_mask(table):
    """Rows where every signal is within sensor noise: nothing to classify, so the state is 'normal'.

    Stage 1 of the pipeline (detect) - only scenarios that rise above noise go to the classifier.
    """
    return ((table["drop_ratio"] < 1) & (table["rise_ratio"] < 1) & (table["unacc_ratio"] < 1)
            & (table["flow_frac"] < 0.1) & (table["demand_frac"] == 0))
