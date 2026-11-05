"""Quality gate: promote a registered food11 version to `champion` only if it is clearly better.

usage: python src/food11/promote.py --version 8 [--n 3347] [--metric test_accuracy]

The candidate must beat the champion by at least 2 standard errors of the champion's
accuracy, se = sqrt(p * (1 - p) / n). Otherwise it gets the `challenger` alias and the
champion stays where it is. The decision is written as tags on the candidate version.
"""

import argparse
import math
import os
import sys

from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

MODEL_NAME = "food11"
# size of the evaluation split (the test set in train.py), per dataset param logged by train.py
TEST_SPLIT_SIZE = {"processed": 3347, "mini": 1096}


def run_metric(client: MlflowClient, run_id: str, metric: str) -> float:
    metrics = client.get_run(run_id).data.metrics
    if metric not in metrics:
        sys.exit(f"run {run_id} has no metric '{metric}' (has: {sorted(metrics)})")
    return metrics[metric]


def test_size(client: MlflowClient, run_id: str) -> int:
    dataset = client.get_run(run_id).data.params.get("dataset", "processed")
    return TEST_SPLIT_SIZE[dataset]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="candidate model version number")
    parser.add_argument("--metric", default="test_accuracy")
    parser.add_argument("--n", type=int, help="test set size (default: from the champion run's dataset param)")
    args = parser.parse_args()

    client = MlflowClient(tracking_uri=os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000"))

    candidate = client.get_model_version(MODEL_NAME, args.version)
    acc_candidate = run_metric(client, candidate.run_id, args.metric)

    try:
        champion = client.get_model_version_by_alias(MODEL_NAME, "champion")
    except MlflowException:
        champion = None

    if champion is None:
        # nothing to compare against: the first model becomes champion
        client.set_registered_model_alias(MODEL_NAME, "champion", candidate.version)
        client.set_model_version_tag(MODEL_NAME, candidate.version, "gate_decision", "promoted (no previous champion)")
        client.set_model_version_tag(MODEL_NAME, candidate.version, "gate_candidate_acc", f"{acc_candidate:.4f}")
        print(f"no champion yet: v{candidate.version} ({acc_candidate:.4f}) is now champion")
        return

    if champion.version == candidate.version:
        sys.exit(f"v{candidate.version} is already the champion, nothing to do")

    acc_champion = run_metric(client, champion.run_id, args.metric)
    n = args.n or test_size(client, champion.run_id)
    se = math.sqrt(acc_champion * (1 - acc_champion) / n)
    threshold = acc_champion + 2 * se

    if acc_candidate >= threshold:
        client.set_registered_model_alias(MODEL_NAME, "champion", candidate.version)
        decision = f"promoted to champion (replaced v{champion.version})"
    else:
        client.set_registered_model_alias(MODEL_NAME, "challenger", candidate.version)
        decision = f"challenger (champion v{champion.version} kept)"

    tags = {
        "gate_decision": decision,
        "gate_candidate_acc": f"{acc_candidate:.4f}",
        "gate_champion_acc": f"{acc_champion:.4f}",
        "gate_champion_version": champion.version,
        "gate_threshold": f"{threshold:.4f}",
        "gate_n": str(n),
    }
    for key, value in tags.items():
        client.set_model_version_tag(MODEL_NAME, candidate.version, key, value)

    print(f"champion  v{champion.version}: {args.metric}={acc_champion:.4f}  (n={n}, se={se:.4f})")
    print(f"candidate v{candidate.version}: {args.metric}={acc_candidate:.4f}  (needs >= {threshold:.4f})")
    print(f"decision: {decision}")


if __name__ == "__main__":
    main()
