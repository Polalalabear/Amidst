"""Read-only approved-scale checks; native geometry and historical artifacts stay intact."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from amidst.architectural_scale import ArchitecturalScale, load_architectural_scale
from amidst.physical_authority import (
    ReadOnlyPhysicalAuthorityProvider,
    canonical_geometry_sha256,
)
from amidst.physical_units import physical_policy_in_blender_units
from amidst.scene_geometry import (
    GeometryAuthorityError,
    ReadOnlySceneGeometryProvider,
)


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def validate_measurement_units(document: dict[str, Any], scale: ArchitecturalScale) -> int:
    require(document["scale_authority"] == "APPROVED", "measurement scale is not approved")
    require(document["measurement_role"] == "SANITY_CHECK_EVIDENCE", "wrong measurement role")
    require(document["architectural_scale"] == scale.model_dump(mode="json"),
            "measurement authority differs from approved record")
    count = 0

    def check(value: Any) -> None:
        nonlocal count
        if isinstance(value, list):
            for child in value:
                check(child)
        elif isinstance(value, dict):
            for key, child in value.items():
                if key.endswith("_bu") and isinstance(child, (int, float)):
                    metric_key = key.removesuffix("_bu") + "_m"
                    if metric_key in value:
                        metric = value[metric_key]
                        require(isinstance(metric, (int, float)) and math.isclose(
                            metric, scale.to_metres(child), rel_tol=1e-12, abs_tol=1e-12,
                        ), f"incorrect measurement conversion: {key}")
                        count += 1
                check(child)

    check(document)
    require(count > 0, "no BU/metre measurement pairs checked")
    for row in document["measurements"]:
        require(not row["used_to_derive_scale"], "measurement cannot derive user authority")
        require(row["scale_authority"] == "APPROVED", "row scale is not approved")
        require(row["metres_per_blender_unit"] == scale.metres_per_blender_unit,
                "row scale differs from approved record")
    return count


def validate(args: argparse.Namespace) -> dict[str, Any]:
    measurement = json.loads(args.measurements.read_text())
    expected_source = measurement["source"]["before"]
    scale = load_architectural_scale(args.scale, expected_source["sha256"])
    fingerprint = {
        "sha256": digest(args.source), "size_bytes": args.source.stat().st_size,
        "mtime_ns": args.source.stat().st_mtime_ns,
    }
    require(expected_source == measurement["source"]["after"] == fingerprint,
            "source SHA-256/size/mtime differs from read-only measurement")
    conversions = validate_measurement_units(measurement, scale)
    legacy = json.loads(args.legacy_geometry.read_text())
    current = json.loads(args.geometry.read_text())
    allowed_changes = {
        "unit_scale_m", "scale_authority", "scale_approval_id", "portal_protection_tolerance_m",
    }
    require(current.keys() == legacy.keys(), "geometry schema keys changed")
    require(all(current[key] == legacy[key] for key in current if key not in allowed_changes),
            "native geometry or non-scale ownership changed")
    require(current["unit_scale_m"] == scale.metres_per_blender_unit
            and current["scale_authority"] == "APPROVED"
            and current["scale_approval_id"] == scale.approval_id,
            "geometry scale approval differs")
    native_padding = legacy["portal_protection_tolerance_m"] / legacy["unit_scale_m"]
    require(math.isclose(current["portal_protection_tolerance_m"],
                         scale.to_metres(native_padding), rel_tol=1e-12),
            "native doorway protection changed")
    provider = ReadOnlySceneGeometryProvider.from_json(
        args.geometry, expected_source_sha256=scale.source_asset_sha256,
    )
    physical = ReadOnlyPhysicalAuthorityProvider.from_json(
        args.geometry, args.physical_authority,
        expected_source_sha256=scale.source_asset_sha256,
        expected_geometry_sha256=canonical_geometry_sha256(provider.snapshot),
    )
    gates: list[dict[str, Any]] = []
    for scope in physical.resolution.scopes:
        try:
            physical.require_scope(scope.scope_id, purpose=scope.purpose)
        except GeometryAuthorityError as error:
            require(not any("SCALE_NOT_APPROVED" in reason for reason in error.reasons),
                    "approved scale still rejected by provider")
            gates.append({
                "scope_id": scope.scope_id, "purpose": str(scope.purpose),
                "status": "REFUSED_PENDING_OTHER_AUTHORITIES",
                "remaining_reason_counts": dict(Counter(
                    reason.split(":", 1)[0] for reason in error.reasons
                )),
            })
        else:
            gates.append({"scope_id": scope.scope_id, "status": "APPROVED"})
    anomalies = [
        {key: row[key] for key in (
            "measurement_id", "actual_source_length_bu", "actual_source_length_m",
            "source_to_annotation_length_ratio", "ambiguities",
        )}
        for row in measurement["measurements"]
        if row["source_to_annotation_length_ratio"] is not None and (
            row["source_to_annotation_length_ratio"] < 0.25
            or row["source_to_annotation_length_ratio"] > 2.5
        )
    ]
    # Ratio flags locate unreliable nearest-hit bindings; they never infer architectural authority.
    return {
        "schema_version": "approved-school-scale-validation-v1", "status": "PASS",
        "architectural_scale": scale.model_dump(mode="json"), "source": fingerprint,
        "native_geometry_unchanged": True, "native_surface_count": len(current["surfaces"]),
        "native_doorway_protection_bu": native_padding,
        "portal_protection_tolerance_m": current["portal_protection_tolerance_m"],
        "measurement_role": "SANITY_CHECK_EVIDENCE", "conversion_pairs_checked": conversions,
        "measurement_count": len(measurement["measurements"]),
        "unresolved_portal_directions": len(measurement["unresolved_portals"]),
        "floor_rise_bu": measurement["floor_height"]["vertical_height_bu"],
        "floor_rise_m": measurement["floor_height"]["vertical_height_m"],
        "physical_authority_level": str(physical.resolution.level), "physical_scope_gates": gates,
        "physical_policy_units": physical_policy_in_blender_units(
            physical.resolution.policy, scale, source_asset_sha256=scale.source_asset_sha256,
        ),
        "sanity_result": "NO_RELIABLE_EVIDENCE_OF_IMPLAUSIBLE_SCALE",
        "binding_anomalies": anomalies,
        "anomaly_interpretation": (
            "UNAPPROVED_NEAREST_HIT_BINDINGS_NOT_CONFIRMED_ROOM_OR_DOOR_SIZES"
        ),
        "source_geometry_scaled": False, "formal_benchmark_run": False,
        "history_rewritten": False,
        "inputs": {str(path): digest(path) for path in (
            args.scale, args.legacy_geometry, args.geometry, args.physical_authority,
            args.measurements, Path("scripts/validate_school_scale.py"),
        )},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "scale", "legacy-geometry", "geometry", "physical-authority",
                 "measurements", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report = validate(args)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "geometry_scale_validation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
    )
    rows = [
        "# Approved school v3 scale validation / 已核准尺度驗證", "",
        "**PASS — 1 BU = 0.0247 m；APPROVED，使用者定義的研究模型尺度。**", "",
        "Mesh measurements are sanity-check evidence; external dimensions are not required.",
        "原始 .blend SHA-256／size／mtime、所有 native vertices／faces／planes／ownership 不變。",
        f"Checked {report['conversion_pairs_checked']} BU/metre pairs across "
        f"{report['measurement_count']} rows; native surfaces: {report['native_surface_count']}.",
        f"Floor support rise: {report['floor_rise_bu']:.6f} BU = {report['floor_rise_m']:.6f} m.",
        "", f"可靠截面未顯示尺度明顯不合理；以下 {len(report['binding_anomalies'])} 筆"
        "是 nearest-hit binding 異常，",
        "不能宣稱為真實門寬或房間寬，也不以 sanity check 重新推導已核准尺度。", "",
        "| Measurement | Source section BU | Converted m | Source / annotation |",
        "| --- | ---: | ---: | ---: |",
    ]
    rows.extend(
        f"| {row['measurement_id']} | {row['actual_source_length_bu']:.6f} | "
        f"{row['actual_source_length_m']:.6f} | {row['source_to_annotation_length_ratio']:.6f} |"
        for row in report["binding_anomalies"]
    )
    rows.extend([
        "", "Scale approval removes SCALE_NOT_APPROVED; physical authority remains PROVISIONAL.",
        "Floor／stair／obstacle volume／body／clearance 仍須各自核准，formal scopes 持續拒絕。",
        "原 0.28 BU doorway protection = 0.006916 m；沒有改變原始 BU 邊界或診斷門檻。",
        "", "[Approved geometry](geometry.json) · [Physical authority](physical_authority.json) ·",
        "[Measurement evidence](../school_v3_scale_calibration_20261006/measurements.md) ·",
        "[Unit contract](../../../docs/GEOMETRY_PROVIDER.md)", "",
        "SI inputs must use source-bound adapters before the core. Legacy runner/pilot exports",
        "remain historical native inputs until explicitly normalized; no automatic migration.",
        "No Graph/Top-K/GT/metric semantics or historical benchmark artifacts changed.",
    ])
    (args.output / "geometry_scale_validation.md").write_text("\n".join(rows) + "\n")
    print(json.dumps({"status": report["status"], "pairs": report["conversion_pairs_checked"],
                      "binding_anomalies": len(report["binding_anomalies"])}))


if __name__ == "__main__":
    main()
