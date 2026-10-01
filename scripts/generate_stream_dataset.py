"""Generate a replaceable versioned stream dataset from strict legacy mock inputs."""

import argparse
from pathlib import Path

from amidst.simulation.stream_fixture import experiment_config, export_stream_dataset
from amidst.storage.json_files import write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-root", type=Path, default=Path("data/mock"))
    parser.add_argument("--dataset-output", type=Path, required=True)
    parser.add_argument("--metric-config", type=Path, required=True)
    parser.add_argument("--experiment-output", type=Path, required=True)
    args = parser.parse_args()
    manifest = export_stream_dataset(args.legacy_root, args.dataset_output)
    config = experiment_config(
        manifest, args.dataset_output / "dataset.json", args.metric_config,
        config_directory=args.experiment_output.parent,
    )
    write_json(args.experiment_output, config.model_dump(mode="json"))


if __name__ == "__main__":
    main()
