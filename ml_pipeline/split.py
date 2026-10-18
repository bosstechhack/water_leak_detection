"""Fixed 80/20 train/test split of all scenarios.

The model, the noise thresholds and the classifier are fitted on the training scenarios only.
Every reported accuracy comes from the test scenarios, which the system has never seen.

Scenarios that are near-copies of each other always stay on the same side, otherwise the test
would be too easy:
  * all leaks at the same junction (every size, start time, noise level, and "hidden behind" variant);
  * a scenario and its sensor-noise twin (id ending in _noisy).
The split is stratified: each network and each kind of event is split about 80/20.
"""
import json
import os
import random

from dataset import DATA_DIR, RESULTS_DIR, available_networks

SEED = 42
TEST_FRACTION = 0.2
_CACHE = {}


def _group(network, spec):
    if spec["event_class"] == "leak" and spec.get("truth_nodes"):
        return f"{network}|leak|{spec['truth_nodes'][0]}"
    sid = spec["id"]
    return f"{network}|{sid[:-6] if sid.endswith('_noisy') else sid}"


def get_split():
    """Return {scenario_id: 'train' | 'test'} (deterministic: same every run)."""
    if "split" in _CACHE:
        return _CACHE["split"]
    out = {}
    for network in available_networks():
        with open(os.path.join(DATA_DIR, network, "manifest.json"), encoding="utf-8") as f:
            scenarios = json.load(f)["scenarios"]
        strata = {}
        for spec in scenarios:
            strata.setdefault(spec["event_class"], {}).setdefault(_group(network, spec), []).append(spec["id"])
        for event_class, groups in strata.items():
            total = sum(len(v) for v in groups.values())
            target = max(1, round(TEST_FRACTION * total)) if len(groups) > 1 else 0
            keys = sorted(groups)
            random.Random(f"{SEED}-{network}-{event_class}").shuffle(keys)
            taken = 0
            for key in keys:
                side = "test" if taken < target else "train"
                if side == "test":
                    taken += len(groups[key])
                for sid in groups[key]:
                    out[sid] = side
    _CACHE["split"] = out
    return out


def write_split():
    """Save the split next to the results so it can be inspected."""
    split = get_split()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    info = {"seed": SEED, "test_fraction": TEST_FRACTION,
            "train": sorted(k for k, v in split.items() if v == "train"),
            "test": sorted(k for k, v in split.items() if v == "test")}
    with open(os.path.join(RESULTS_DIR, "split.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, indent=1)
    return info


if __name__ == "__main__":
    info = write_split()
    print(f"train {len(info['train'])}, test {len(info['test'])}")
