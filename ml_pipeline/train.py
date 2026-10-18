"""Build the feature table for every scenario and train the event classifier."""
import os

import pandas as pd

import classifier
from dataset import RESULTS_DIR, available_networks
from features import FEATURES
from pipeline import get_context, analyze
from split import get_split, write_split


def feature_table(use_demand=True):
    split = get_split()
    rows = []
    for name in available_networks():
        ctx = get_context(name)
        for scenario in ctx.nd.scenarios():
            frames = ctx.nd.load(scenario["id"])
            feats = analyze(ctx, frames, None, use_demand)["features"]
            rows.append({"network": name, "id": scenario["id"], "split": split[scenario["id"]], "group": scenario["group"],
                         "event_class": scenario["event_class"],
                         "truth": "|".join(scenario.get("truth_nodes", [])), **feats})
    return pd.DataFrame(rows)


def main():
    write_split()
    table = feature_table(True)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    table.to_csv(os.path.join(RESULTS_DIR, "features.csv"), index=False)
    train = table[table["split"] == "train"]          # the model only ever sees training scenarios
    X, y = train[FEATURES], train["event_class"]
    forest, tree = classifier.make_model("forest").fit(X, y), classifier.make_model("tree").fit(X, y)
    classifier.save({"forest": forest, "tree": tree, "features": FEATURES})
    with open(os.path.join(RESULTS_DIR, "decision_rules.txt"), "w", encoding="utf-8") as f:
        f.write(classifier.tree_rules(tree))
    print(f"Trained on {len(train)} training scenarios ({len(table) - len(train)} test scenarios held out).")
    print(classifier.tree_rules(tree))


if __name__ == "__main__":
    main()
