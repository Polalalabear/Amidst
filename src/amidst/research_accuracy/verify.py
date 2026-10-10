"""Independent empty-output rebuilds with evaluator sidecar reads poisoned/removed."""

from __future__ import annotations

import argparse
import builtins
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from amidst.engineering.access import digest
from amidst.engineering.local_pilot import MODES, _save
from amidst.engineering.research_scene import DEFAULT_CONFIG
from amidst.research_accuracy.adapter import load_service
from amidst.research_accuracy.run import VARIANTS, build, frozen, load


@contextmanager
def denied_sidecars(paths: set[Path], *, removed: bool) -> Iterator[dict[str, int]]:
    """Virtual replacements preserve source bytes; runtime must never request these files."""
    paths = {p.resolve() for p in paths}
    counts = {"attempted_reads": 0}
    original_bytes, original_text, original_open = Path.read_bytes, Path.read_text, builtins.open

    def check(path: object) -> bool:
        return isinstance(path, (str, Path)) and Path(path).resolve() in paths

    def poisoned_bytes(path: Path) -> bytes:
        if check(path):
            counts["attempted_reads"] += 1
            if removed:
                raise FileNotFoundError("evaluation sidecar virtually removed")
            return b'{"actor_identity":"POISON","recipe":"POISON"}'
        return original_bytes(path)

    def poisoned_text(path: Path, *args: Any, **kwargs: Any) -> str:
        if check(path):
            return poisoned_bytes(path).decode()
        return original_text(path, *args, **kwargs)

    def poisoned_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        if check(file):
            counts["attempted_reads"] += 1
            raise AssertionError("runtime attempted to open evaluator-only sidecar")
        return original_open(file, *args, **kwargs)

    with (
        patch.object(Path, "read_bytes", poisoned_bytes),
        patch.object(Path, "read_text", poisoned_text),
        patch("builtins.open", poisoned_open),
    ):
        yield counts


def verify(original: Path, output: Path) -> dict[str, Any]:
    package, registry, manifest, policy = load(original)
    original_states = {
        (v, m): frozen(original, v, m, manifest, package, registry)
        for v in VARIANTS
        for m in MODES
    }
    snapshots = {
        key: {
            "pixels": digest(s.perception),
            "inference": digest(s.inference),
            "events": digest(s.events),
            "receipt": digest(s.receipt),
        }
        for key, s in original_states.items()
    }
    result: dict[str, Any] = {
        "schema_version": "accuracy.reproduction.v2",
        "experiment_id": manifest["experiment_id"],
        "checks": {},
    }
    sidecars = {
        package.simulation_export_path,
        DEFAULT_CONFIG,
        package.simulation_export_path.parent / "recipe.json",
        package.simulation_export_path.parent / "reference_annotations.json",
    }
    raw_sha = {str(p): digest(p.read_bytes().hex()) for p in sidecars if p.exists()}
    for condition in ("replacement", "removal"):
        target = output / condition
        with denied_sidecars(sidecars, removed=condition == "removal") as counts:
            rebuilt = build(
                Path(manifest["source_locator"]),
                target,
                policy,
                experiment_id=manifest["experiment_id"],
            )
            p, reg, checked, _ = load(target)
            checks = {}
            for key, hashes in snapshots.items():
                state = frozen(target, key[0], key[1], checked, p, reg)
                values = {
                    "pixels": digest(state.perception),
                    "inference": digest(state.inference),
                    "events": digest(state.events),
                    "receipt": digest(state.receipt),
                }
                checks["/".join(key)] = values == hashes
            service = load_service(target)
            session = {"session_ref": service.guard.session_ref}
            camera = next(iter(service.cameras))
            response = service.call(
                "query_events", session | {"camera_ref": camera, "time_range": [0, 4]}
            )
        if not all(checks.values()) or counts["attempted_reads"] != 0:
            raise ValueError("GT poisoning/removal changed inference or attempted a truth read")
        result["checks"][condition] = {
            "empty_output": True,
            "manifest_equal": rebuilt == manifest,
            "variant_mode_hashes_equal": checks,
            "sidecar_read_attempts": counts["attempted_reads"],
            "frozen_tool_response_sha256": digest(response),
        }
    if raw_sha != {str(p): digest(p.read_bytes().hex()) for p in sidecars if p.exists()}:
        raise ValueError("immutable source changed during reproduction")
    result["source_bytes_unchanged"] = True
    result["poisoning_method"] = (
        "Virtual exact-path replacement/removal; source assets never mutated"
    )
    _save(output / "receipt.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.source, args.output)
    print(json.dumps({"experiment_id": result["experiment_id"], "verified": True}))


if __name__ == "__main__":
    main()
