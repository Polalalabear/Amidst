"""Read-only scoped adapter major-flow validation of a frozen v2 experiment.

This command never evaluates accuracy or opens truth/recipe sidecars. Tool-flow
calls and repeated lookup telemetry have separate populations, and each latency
receipt requires a fresh path to preserve previous evidence.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
from typing import Any
from unittest.mock import patch

from amidst.engineering.access import TOOLS, Mode, Tool, digest
from amidst.engineering.facade import ToolFailure
from amidst.engineering.local_pilot import MODES, _save, benchmark_queries, mock_agent
from amidst.engineering.local_service import LocalPilotService
from amidst.engineering.registry import opaque_ref
from amidst.engineering.research_scene import DEFAULT_CONFIG
from amidst.research_accuracy.adapter import load_service
from amidst.research_accuracy.run import load
from amidst.research_accuracy.verify import denied_sidecars

FORBIDDEN = ("actor_identity", "render_annotations", "recipe", "ground_truth", "source_locator")


def _public(value: object, *, private_paths: tuple[str, ...]) -> None:
    serialized = json.dumps(value, sort_keys=True, allow_nan=False).casefold()
    if any(field in serialized for field in FORBIDDEN) or any(
        path.casefold() in serialized for path in private_paths
    ):
        raise AssertionError("adapter public payload exposed an evaluator field or private locator")


def _rejected(
    service: LocalPilotService, name: str, tool: Tool, payload: dict[str, Any], expected: str,
) -> dict[str, str]:
    try:
        service.call(tool, payload)
    except ToolFailure as error:
        if str(error) != expected:
            raise AssertionError(
                f"{name}: expected {expected}, got a different safe code") from None
        return {"check": name, "tool": tool, "status": "REJECTED", "safe_error_code": expected}
    raise AssertionError(f"{name}: invalid scoped request was accepted")


def validate(source: Path, receipt: Path) -> dict[str, Any]:
    source, receipt = source.resolve(), receipt.resolve()
    if receipt.exists() or receipt.is_symlink():
        raise ValueError("adapter validation requires a fresh receipt path")
    package, _, manifest, _ = load(source)
    private_paths = (str(source), manifest["source_locator"], str(package.simulation_export_path))
    sidecars = {
        package.simulation_export_path,
        DEFAULT_CONFIG,
        package.simulation_export_path.parent / "recipe.json",
        package.simulation_export_path.parent / "reference_annotations.json",
    }
    report: dict[str, Any] = {
        "schema_version": "accuracy.adapter-validation.v2",
        "experiment_id": manifest["experiment_id"],
        "source_run_id": package.run_id,
        "split": package.split,
        "manifest_sha256": digest(manifest),
        "config_sha256": manifest["config_sha256"],
        "dataset_sha256": package.dataset_sha256,
        "source_algorithm_sha256": {
            name: sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
            for name in ("validation.py", "adapter.py")
        },
        "variant": "end_to_end",
        "accuracy_evaluated": False,
        "external_model_calls": False,
        "formal_phase1_acceptance": False,
        "call_population_note": (
            "MockAgent scoped demonstration and one observation lookup per mode; "
            "repeat-query telemetry and negative checks are counted separately."
        ),
        "modes": {},
    }
    with denied_sidecars(sidecars, removed=True) as sidecar_reads:
        services = {mode: load_service(source, mode=mode) for mode in MODES}
        for mode in MODES:
            service = services[mode]
            session = {"session_ref": service.guard.session_ref}
            _public(service.context(), private_paths=private_paths)
            successful: list[dict[str, str]] = []
            original_call = service.call

            def audited(
                tool: Tool, payload: object,
                call: Callable[[Tool, object], dict[str, Any]] = original_call,
                responses: list[dict[str, str]] = successful,
            ) -> dict[str, Any]:
                result = call(tool, payload)
                _public(result, private_paths=private_paths)
                responses.append({"tool": tool, "response_sha256": digest(result)})
                return result

            with patch.object(service, "call", side_effect=audited):
                flow = mock_agent(service)
                first_camera = next(iter(service.cameras))
                observations = service.call(
                    "query_observations",
                    session | {"camera_ref": first_camera, "time_range": [0, 2]},
                )
            _public(flow, private_paths=private_paths)
            counts = Counter(row["tool"] for row in successful)
            if set(counts) != set(TOOLS):
                raise AssertionError("scoped major flow did not exercise all eight tools")
            if service.guard.stage != "RESULTS" or flow["context"]["observation_mode"] != mode:
                raise AssertionError("major flow lost its server-owned stage/mode")
            other_mode: Mode = (
                "photos_plus_observations" if mode == "photos_only" else "photos_only")
            foreign_mode = services[other_mode]
            foreign_variant = load_service(source, variant="baseline", mode=mode)
            input_service = load_service(source, mode=mode, input_stage=True)
            if service.guard.session_ref == foreign_mode.guard.session_ref or (
                service.guard.session_ref == foreign_variant.guard.session_ref
            ):
                raise AssertionError("cross-mode or cross-variant sessions collided")
            camera = next(iter(service.cameras))
            event = next(iter(service.events))
            negative = [
                _rejected(service, "wrong_scope_camera", "query_events", session | {
                    "camera_ref": opaque_ref("camera", "foreign-scope"), "time_range": [0, 2],
                }, "SCOPE_DENIED"),
                _rejected(service, "missing_local_anchor", "query_events", session | {
                    "time_range": [0, 2],
                }, "LOCAL_ANCHOR_REQUIRED"),
                _rejected(service, "caller_stage_override", "query_events", session | {
                    "camera_ref": camera, "time_range": [0, 2], "decision_stage": "RESULTS",
                }, "INVALID_OR_UNAVAILABLE"),
                _rejected(service, "wrong_session", "get_event_detail", {
                    "session_ref": "session-wrong", "event_ref": event,
                }, "SCOPE_DENIED"),
                _rejected(service, "foreign_mode_event_reference", "get_event_detail", session | {
                    "event_ref": next(iter(foreign_mode.events)),
                }, "REFERENCE_DENIED"),
                _rejected(service, "foreign_variant_reference", "get_event_detail", session | {
                    "event_ref": next(iter(foreign_variant.events)),
                }, "REFERENCE_DENIED"),
                _rejected(input_service, "input_event_read", "query_events", {
                    "session_ref": input_service.guard.session_ref,
                    "camera_ref": camera, "time_range": [0, 2],
                }, "STAGE_DENIED"),
            ]
            telemetry = benchmark_queries(service)
            _public(telemetry, private_paths=private_paths)
            report["modes"][mode] = {
                "binding_sha256": digest(service.guard.binding),
                "freeze_receipt_sha256": manifest["variants"]["end_to_end"][mode][
                    "receipt_sha256"],
                "public_context_sha256": digest(service.context()),
                "scoped_major_flow_sha256": digest(flow),
                "scoped_major_flow_calls": len(successful),
                "scoped_major_flow_calls_by_tool": dict(sorted(counts.items())),
                "scoped_response_hashes": successful,
                "observation_lookup_sha256": digest(observations),
                "card_count": len(flow["cards"]),
                "all_eight_tools_exercised": True,
                "no_forbidden_public_fields_or_locators": True,
                "cross_mode_and_variant_sessions_distinct": True,
                "negative_check_count": len(negative),
                "negative_checks": negative,
                "query_telemetry": telemetry,
            }
        if sidecar_reads["attempted_reads"]:
            raise AssertionError("adapter validation attempted to read an evaluator sidecar")
        report["evaluation_sidecar_attempted_reads"] = sidecar_reads["attempted_reads"]
    report["negative_check_count"] = sum(
        row["negative_check_count"] for row in report["modes"].values())
    report["status"] = "PASS_SCOPED_ADAPTER_MAJOR_FLOW"
    _save(receipt, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    report = validate(args.source, args.receipt)
    print(json.dumps({"status": report["status"], "experiment_id": report["experiment_id"],
                      "modes": list(report["modes"]),
                      "negative_check_count": report["negative_check_count"],
                      "evaluation_sidecar_attempted_reads": 0,
                      "receipt_sha256": digest(report)}))


if __name__ == "__main__":
    main()
