"""Publish deterministic downstream fixtures; refuses any existing output file."""

import argparse
from pathlib import Path

from amidst.simulation.mock_scenarios import export_scenarios


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export_scenarios(args.output)


if __name__ == "__main__":
    main()
