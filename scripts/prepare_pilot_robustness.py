"""Prepare a fixed, bounded robustness matrix from three existing Blender pilots.

This is export-stage perturbation, not new Blender rendering or school authority.
Inference preparation allowlists metadata and 2D evidence only. Evaluation truth
is exported separately using the same predeclared timestamp map, never to choose
parameters, projected endpoints, topology or a candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from amidst.datasets.pilot import PILOT_LABEL, PilotInferenceContext, PilotObservationExport
from amidst.domain.camera import Camera

CHECKPOINT = "51f1ec7c34b8766b44ce2bb2ba98bdb8c9ca321e"
SEED = 20261006


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    site_id: str
    source_directory: str
    area_id: str
    walkable_id: str
    description: str
    time_scale: float = 1.0
    window: tuple[float, float] | None = None
    removed_camera: str | None = None
    noise_half_width_pixels: float = 0.0
    max_speed_scene_units_s: float = 32.0
    lateral_offset_scene_units: float = 12.0


OFFICE = "data/pilot/phase1_wall_pilot_20261005/office"
SCENARIOS = (
    Scenario("S01_office_medium", "office", OFFICE, "AREA_1F_OFFICE", "WALK_1F_OFFICE",
             "Native office reference: two cameras, 5.0s endpoint gap."),
    Scenario("S02_corridor_long", "corridor", "data/pilot/school_v3_pilot_20261005",
             "AREA_1F_ELEVATOR", "WALK_1F_CORRIDOR_01",
             "Native corridor: different camera pair, 6.0s gap. AREA name is historical; "
             "no elevator or transition is asserted."),
    Scenario("S03_auditorium_native_short", "auditorium",
             "data/pilot/school_v3_multisite_20261005/auditorium",
             "AREA_1F_AUDITORIUM", "WALK_1F_AUDITORIUM",
             "Native 9.0–9.8s window: 0.4s same-camera gap; expose unsupported topology.",
             window=(9.0, 9.8)),
    Scenario("S04_office_remove_front", "office", OFFICE, "AREA_1F_OFFICE", "WALK_1F_OFFICE",
             "Delete front camera calibration AND all its records; do not invent GAP evidence.",
             removed_camera="CAM_1F_AUDITORIUM_FRONT"),
    Scenario("S05_office_remove_rear", "office", OFFICE, "AREA_1F_OFFICE", "WALK_1F_OFFICE",
             "Delete rear camera calibration AND all its records; do not invent recovery.",
             removed_camera="CAM_1F_AUDITORIUM_REAR"),
    Scenario("S06_office_pixel_noise", "office", OFFICE, "AREA_1F_OFFICE", "WALK_1F_OFFICE",
             "Uniform independent u/v noise in [-0.25,+0.25]px on OBSERVED pixels only.",
             noise_half_width_pixels=0.25),
    Scenario("S07_office_short_tight", "office", OFFICE, "AREA_1F_OFFICE", "WALK_1F_OFFICE",
             "Timestamp compression x0.5: 10Hz, 2.5s gap; speed33, offset12. Not new renders.",
             time_scale=0.5, max_speed_scene_units_s=33.0),
    Scenario("S08_office_short_ambiguous", "office", OFFICE, "AREA_1F_OFFICE", "WALK_1F_OFFICE",
             "Same as S07 except offset1: three feasible nearby configured branches, K=3.",
             time_scale=0.5, max_speed_scene_units_s=33.0, lateral_offset_scene_units=1.0),
    Scenario("S09_office_short_speed_failure", "office", OFFICE,
             "AREA_1F_OFFICE", "WALK_1F_OFFICE",
             "Same compressed observations; speed31 makes every configured route infeasible.",
             time_scale=0.5, max_speed_scene_units_s=31.0),
)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def map_time(timestamp: float, scenario: Scenario) -> float:
    return round(float(timestamp) * scenario.time_scale, 12)


def keep_time(timestamp: float, scenario: Scenario) -> bool:
    return scenario.window is None or scenario.window[0] <= timestamp <= scenario.window[1]


def verify_source(dataset: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    source = dataset["source_scene"]
    path = Path(source["path"])
    stat = path.stat()
    if (
        source["sha256_before"] != source["sha256_after"]
        or (sha256(path), stat.st_size, stat.st_mtime_ns)
        != (source["sha256_before"], source["size_before"], source["mtime_ns_before"])
    ):
        raise ValueError("preserved Blender source identity differs from existing export")
    lineage = dataset.get("source_lineage")
    audit_sha = audit["source_sha256"]
    if lineage is None:
        if source["sha256_before"] != audit_sha:
            raise ValueError("original scene and semantic audit differ")
    else:
        if (
            lineage["original_source_sha256"] != audit_sha
            or lineage["original_source_identity_verified"] is not True
            or lineage["wall_semantic_marking_policy"]
            != "ANNOTATION_ONLY_PHYSICAL_ROLE_NOT_APPROVED"
        ):
            raise ValueError("derived source lineage must preserve annotation-only authority")
        original = Path(lineage["original_source_path"])
        original_stat = original.stat()
        if (sha256(original), original_stat.st_size, original_stat.st_mtime_ns) != (
            audit_sha, lineage["original_source_size"], lineage["original_source_mtime_ns"],
        ):
            raise ValueError("original source lineage identity differs")
    return {"path": str(path), "sha256": source["sha256_before"],
            "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def prepare_inference_fixture(
    repository: Path, scenario: Scenario, output: Path, *, dataset_path: Path | None = None,
) -> dict[str, Any]:
    """Read existing 2D/calibration/independent-plane metadata; never open a GT file.

    The original dataset is a mixed container, inspected only at export preparation.
    Unknown fields, positions, depths and trajectory waypoints are never copied to
    consumer inputs. Single-camera removal intentionally produces a context that
    the existing two-camera consumer rejects; its contract is not silently relaxed.
    """
    if output.exists():
        raise FileExistsError(output)
    source_root = repository / scenario.source_directory
    dataset_path = dataset_path or source_root / "dataset.json"
    observations_path = source_root / "observations.json"
    audit_path = repository / "data/scene_audit/school_v3_semantic_validation.json"
    dataset = json.loads(dataset_path.read_text())
    original = json.loads(observations_path.read_text())
    audit = json.loads(audit_path.read_text())
    source = verify_source(dataset, audit)
    if (
        dataset.get("label") != PILOT_LABEL or original.get("label") != PILOT_LABEL
        or original.get("data_kind") != "SYNTHETIC"
        or original["source_asset_sha256"] != source["sha256"]
    ):
        raise ValueError("existing pilot label/source binding differs")
    # Corridor predates the required site_id field; normalize its container only.
    normalized = {**original, "site_id": scenario.site_id}
    observations = PilotObservationExport.model_validate(normalized)
    if scenario.time_scale not in (1.0, 0.5):
        raise ValueError("bounded matrix supports only the predeclared native/half time scales")
    rng = random.Random(SEED)
    frames = []
    deltas = []
    for frame in observations.frames:
        if not keep_time(frame.timestamp, scenario) or frame.camera_id == scenario.removed_camera:
            continue
        row = frame.model_dump(mode="json")
        row["timestamp"] = map_time(frame.timestamp, scenario)
        if frame.point_2d is not None and scenario.noise_half_width_pixels:
            delta = [rng.uniform(-scenario.noise_half_width_pixels,
                                 scenario.noise_half_width_pixels) for _ in range(2)]
            row["point_2d"] = [a + b for a, b in zip(frame.point_2d, delta, strict=True)]
            deltas.append({"camera_id": frame.camera_id, "frame_id": frame.frame_id,
                           "delta_uv_pixels": delta})
        frames.append(row)
    evidence = PilotObservationExport.model_validate({
        "label": PILOT_LABEL, "data_kind": "SYNTHETIC", "site_id": scenario.site_id,
        "source_asset_sha256": source["sha256"], "frames": frames,
    })
    cameras = tuple(Camera.model_validate(row) for row in dataset["cameras"]
                    if row["camera_id"] != scenario.removed_camera)
    if {frame.camera_id for frame in evidence.frames} != {c.camera_id for c in cameras}:
        raise ValueError("fixture camera records and selected calibration differ")
    for frame in evidence.frames:
        if frame.point_2d is None:
            continue
        camera = next(c for c in cameras if c.camera_id == frame.camera_id)
        u, v = frame.point_2d
        if not 0 <= u < camera.width or not 0 <= v < camera.height:
            raise ValueError("predeclared noise would leave the calibrated image; no clipping")
    objects = {obj["id"]: obj for obj in audit["geometry_objects"]}
    area, walkable = objects[scenario.area_id], objects[scenario.walkable_id]
    if (
        area["kind"] != "AREA" or walkable["kind"] != "WALKABLE"
        or area["floor"] != walkable["floor"]
    ):
        raise ValueError("configured annotation envelope floor/type differs")
    basis = dataset["trajectory"]["projection_plane_basis"]
    if basis["source_asset_sha256"] != source["sha256"] or (
        basis["purpose"] != "PILOT_DIAGNOSTIC_ONLY"
    ):
        raise ValueError("static diagnostic plane must bind independent source metadata")
    plane_z = sum(float(basis[key]) for key in (
        "physical_floor_z", "foot_clearance_units", "landmark_offset_units",
    ))
    if not math.isclose(plane_z, dataset["trajectory"]["observation_plane_z"], abs_tol=1e-9):
        raise ValueError("independent plane basis differs from static declared plane")
    output.mkdir(parents=True)
    evidence_path = output / "observations.json"
    write_json(evidence_path, evidence.model_dump(mode="json"))
    context = {
        "label": PILOT_LABEL, "data_kind": "SYNTHETIC", "site_id": scenario.site_id,
        "source_id": f"pilot_robustness:{scenario.scenario_id}",
        "spatial_context_id": f"PILOT_ROBUSTNESS_{scenario.site_id.upper()}",
        "source_asset_sha256": source["sha256"], "observations_sha256": sha256(evidence_path),
        "cameras": [c.model_dump(mode="json") for c in cameras],
        "plane": {"plane_id": f"PILOT_{scenario.site_id.upper()}_STATIC_LANDMARK_PLANE",
                  "point": [0, 0, plane_z], "normal": [0, 0, 1],
                  "floor_id": area["floor"], "zone_id": scenario.area_id},
        "zone": {"floor_id": area["floor"], "zone_id": scenario.area_id,
                 "walkable_object_id": scenario.walkable_id,
                 "bounds_min": area["bounds"][0], "bounds_max": area["bounds"][1],
                 "authority": "ANNOTATION_AABB_ONLY_PROVISIONAL"},
        "coordinate_units": "BLENDER_SCENE_UNITS", "scale_authority": "UNVERIFIED",
        "plane_authority": "PILOT_DIAGNOSTIC_ONLY_NOT_FORMAL_FLOOR_BINDING",
    }
    if scenario.removed_camera is None:
        context = PilotInferenceContext.model_validate(context).model_dump(mode="json")
    write_json(output / "projection_context.json", context)
    write_json(output / "scenario_config.json", {
        "label": PILOT_LABEL, "scenario_id": scenario.scenario_id,
        "lateral_offset_scene_units": scenario.lateral_offset_scene_units,
        "max_speed_scene_units_s": scenario.max_speed_scene_units_s,
        "max_candidate_paths": 3, "random_seed": SEED,
    })
    manifest = {
        "label": PILOT_LABEL, "purpose": "EXPORT_PREPARATION_ONLY_NOT_INFERENCE_INPUT",
        "scenario": asdict(scenario), "source": source,
        "original_observations_sha256": sha256(observations_path),
        "context_sha256": sha256(output / "projection_context.json"),
        "observations_sha256": sha256(evidence_path), "noise_seed": SEED,
        "noise_deltas": deltas, "independent_plane_basis": basis,
        "timestamp_mapping": [{"original": t, "variant": map_time(t, scenario)}
                              for t in sorted({f.timestamp for f in observations.frames})
                              if keep_time(t, scenario)],
        "camera_ids": [c.camera_id for c in cameras],
        "physical_validity": "PROVISIONAL", "new_blender_renders": False,
        "gt_loaded_for_inference_preparation": False,
        "historical_elevator_name_creates_no_transition": True,
    }
    write_json(output.parent / "preparation_manifest.json", manifest)
    return manifest


def prepare_evaluation_fixture(
    repository: Path, scenario: Scenario, output: Path,
) -> dict[str, Any]:
    """Separate export/evaluation-only reference, with predeclared time mapping."""
    source = repository / scenario.source_directory / "ground_truth.json"
    truth = json.loads(source.read_text())
    if truth.get("label") != PILOT_LABEL or truth.get("provenance") != "GROUND_TRUTH":
        raise ValueError("evaluation source must be labeled Ground Truth")
    truth = {**truth, "site_id": scenario.site_id,
             "samples": [{**row, "timestamp": map_time(row["timestamp"], scenario)}
                         for row in truth["samples"] if keep_time(row["timestamp"], scenario)]}
    write_json(output / "ground_truth.json", truth)
    # Poison is evaluation-only and deliberately cannot regenerate 2D evidence.
    poisoned = {**truth, "samples": [
        {**row, "position": [x + delta for x, delta in zip(
            row["position"], (10000.0, -20000.0, 30000.0), strict=True,
        )]} for row in truth["samples"]
    ]}
    write_json(output / "poisoned_ground_truth.json", poisoned)
    manifest = {
        "label": PILOT_LABEL, "purpose": "EVALUATION_DEBUG_ONLY",
        "original_truth_sha256": sha256(source), "original_trajectory_id": truth["trajectory_id"],
        "scenario_id": scenario.scenario_id, "truth_sample_count": len(truth["samples"]),
        "timestamp_mapping_predeclared_not_gt_selected": True,
        "physical_scale_authority": "UNVERIFIED",
    }
    write_json(output / "evaluation_export_manifest.json", manifest)
    return manifest


def prepare_matrix(repository: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    inventory: dict[str, Any] = {
        "label": PILOT_LABEL, "scope": "CONTROLLED_ROBUSTNESS_NOT_FORMAL_CASES_1_3",
        "checkpoint_commit": CHECKPOINT, "random_seed": SEED,
        "physical_validity": "PROVISIONAL", "unique_existing_trajectories": 3,
        "scenario_count": len(SCENARIOS), "coverage_epsilon_scene_units": 0.02,
        "metric_policy": "EXISTING_UNMODIFIED_FIRST_PRIMARY_PER_DISTINCT_CANDIDATE",
        "no_parameter_selection_by_gt": True, "scenarios": [],
    }
    # Save the fixed controls before any evaluation export or inference is run.
    write_json(output / "predeclared_matrix.json", {
        "label": PILOT_LABEL, "scenarios": [asdict(s) for s in SCENARIOS],
    })
    for scenario in SCENARIOS:
        root = output / "scenarios" / scenario.scenario_id
        inference = prepare_inference_fixture(repository, scenario, root / "fixture/inference")
        evaluation = prepare_evaluation_fixture(repository, scenario, root / "fixture/evaluation")
        inventory["scenarios"].append({
            "scenario_id": scenario.scenario_id, "site_id": scenario.site_id,
            "description": scenario.description, "path": str(root.resolve()),
            "trajectory_id": evaluation["original_trajectory_id"],
            "camera_ids": inference["camera_ids"], "time_scale": scenario.time_scale,
            "source_asset_sha256": inference["source"]["sha256"],
            "timestamp_count": len(inference["timestamp_mapping"]),
        })
    write_json(output / "scenario_inventory.json", inventory)
    return inventory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory = prepare_matrix(args.repository.resolve(), args.output.resolve())
    print(f"{PILOT_LABEL}: {inventory['scenario_count']} controls / 3 existing trajectories")


if __name__ == "__main__":
    main()
