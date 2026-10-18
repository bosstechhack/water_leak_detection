# Semester 1 Completion Report

All numbers come from `data/results/evaluation_summary.json`, produced by `python ml_pipeline/evaluate.py`.
They are **simulation results on held-out test scenarios**, not real sensor performance.

## Training and testing
All 617 scenarios were split once (seed 42) into **478 for learning (about 80%)** and **139 for testing (about 20%)**.
The noise thresholds and the cause classifier are fitted on the training scenarios only; every result below is measured on the test scenarios.
Near-copies stay on the same side of the split: all leaks at one junction, and a scenario with its sensor-noise twin. Each network and kind of event is split about 80/20.
The dashboard tags every scenario *Unseen test* or *Training* and shows unseen ones by default. The split is saved in `data/results/split.json`.

Settings chosen during development (leak-score weight 0.3, no neighbour smoothing, quiet-gate cut-offs) used all scenarios and were not re-tuned after the split.

## What was built
| Area | Delivered |
|---|---|
| Networks | Net1, Net2, Net3 (EPANET benchmarks) |
| Scenarios | 617 scenarios (net1: 155, net2: 171, net3: 291), all with ground truth |
| Events | leak (every junction, 5 sizes, 4 start times, noise, hidden behind another event), local and global demand change, hydrant, pump outage, reservoir head, tank level, closed or throttled pipe, pipe ageing, normal days with sensor noise |
| Detection | per-network noise threshold learned from training normal runs, persistence rule, quiet gate |
| Cause classifier | random forest and a printable decision tree on 14 physics features |
| Localization | unaccounted-flow plus pressure-drop ranking; error in pipe hops and metres |
| Backend | FastAPI, SQLite scenario catalogue (with train/test tag), analysis and evaluation endpoints |
| Dashboard | LeakLens: guided scenario picker, light/dark themes, plain-language verdicts, Unseen test / Training tags, Performance and Guide tabs |

## Results (test scenarios only)
**Detection** (abnormal event vs normal; 12 normal test days)

| Method | Precision | Recall | F1 | False alarms |
|---|---|---|---|---|
| Fixed 0.5 m threshold | 95.7% | 87.4% | 91.4% | 41.7% |
| Adaptive pressure detector | 100.0% | 77.2% | 87.1% | 0.0% |
| Detector + cause classifier | 100.0% | 93.7% | 96.7% | 0.0% |

**Leak localization** (60 test leaks)

| Method | Top-1 | Top-3 | Top-5 | Mean hops |
|---|---|---|---|---|
| legacy_pressure_plus_divergence | 58.3% | 70.0% | 71.7% | 3.35 |
| proposed | 96.7% | 98.3% | 98.3% | 0.13 |
| proposed_with_graph_smoothing | 96.7% | 98.3% | 98.3% | 0.13 |
| proposed_no_demand_meters | 93.3% | 98.3% | 98.3% | 0.72 |
| pressure_only | 60.0% | 70.0% | 70.0% | 3.05 |
| pressure_only_with_graph_smoothing | 50.0% | 63.3% | 65.0% | 3.18 |

End-to-end (classified as a leak and Top-1 correct): 96.7%. About 22 ms per scenario.
For comparison, leak Top-1 on the training leaks is 97.8%.

**Cause classification**: test accuracy 82.7% (training accuracy 95.6%), macro-F1 76.4%, on 139 test scenarios.
Leak recall 89.6%; non-leak events wrongly called a leak 1.4%.
Per-class F1: normal 75.0%, leak 93.8%, demand_change 100.0%, source_event 66.7%, tank_event 61.5%, valve_block 85.7%, ageing 52.2%.

**Leave-one-network-out** (train on the training scenarios of two networks, test on the third network's test scenarios)

| Held-out | Accuracy | Leak recall | Leak precision | Accuracy without demand meters |
|---|---|---|---|---|
| net1 | 48.5% | 100.0% | 100.0% | 45.5% |
| net2 | 81.8% | 92.3% | 100.0% | 75.0% |
| net3 | 54.8% | 73.3% | 100.0% | 14.5% |

## Honest limitations
- **Small test set.** 139 test scenarios, 60 scored leaks and 12 normal days: one miss moves Top-1 by about 1.7 points, and the split was made once.
- **Training gap.** Cause accuracy is 95.6% on training and 82.7% on test, so the model partly memorises. Pump, tank, blockage and ageing are mixed up most.
- **Demand meters are assumed.** Without them localization and cause accuracy drop, and on an unseen Net3 cause accuracy falls to 14.5%.
- **Leak recall of 89.6% is lowered by one excluded node.** All seven test leaks not named as leaks are at Net3 node 601, a pump-outlet node excluded as unreliable; every other test leak was named a leak.
- **Small leaks are missed.** Leaks inside sensor noise are reported as normal.
- **The very largest leaks are hard to pinpoint** because they depress pressure across the whole network.
- **Unseen network.** Leaks are mostly found; fine-grained non-leak causes do not transfer yet. This is the main Semester 2 item.
- **Graph smoothing did not help** on the test leaks (96.7% vs 96.7%), so it is off.
- Net3 nodes 61 and 601 and hour 21 are excluded (pump switching). Pump speed changes were not simulated (WNTR does not support them). Blockage candidates that did not converge were dropped.

## Fixes to the Semester 1 slides
| Slide | Correction |
|---|---|
| 7 | The backend uses **SQLite**, not PostgreSQL |
| 7 | "Deviation + network distance": network distance is used for the localization error (hops, metres) and the search region; smoothing over neighbours did not help |
| 7-8 | Evaluation is an 80/20 hold-out; F1, false alarm, Top-k, error, inference time and cross-network tests are all computed on test scenarios |
