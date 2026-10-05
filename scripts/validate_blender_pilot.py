"""Independently check a PILOT / SYNTHETIC SAMPLE without downstream inference.

Forward projection and error comparisons are evaluation-only. Inverse projection
receives only sanitized ObservationFrame records, a camera and an explicitly
configured diagnostic landmark plane; it never receives a truth record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from amidst.domain.camera import Camera
from amidst.domain.evidence import ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.geometry.inverse_projection import (
    InverseProjectionError,
    InverseProjectionFailure,
    InverseProjectionService,
)
from amidst.simulation.virtual_camera import project_world

LABEL = "PILOT / SYNTHETIC SAMPLE"
PIXEL_TOLERANCE = 0.02
SCENE_UNIT_TOLERANCE = 0.02
SAMPLE_ROLES = ("VISIBLE_GAP_VISIBLE", "FULLY_OBSERVED_CONTROL")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value: {value}")


def read_json(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)
    if not isinstance(result, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return result


def _finite(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _vector(value: Any, size: int) -> bool:
    return isinstance(value, list | tuple) and len(value) == size and all(map(_finite, value))


def _difference(left: list | tuple, right: list | tuple) -> float:
    return math.dist(left, right)


def check_plan_binding(
    data: dict[str, Any], dataset_path: Path
) -> tuple[dict[str, Any], list[str]]:
    """Evaluate the exported manifest against its optional source-bound route plan.

    Planned/actual 3D positions are compared only here, as export evaluation. This
    function never constructs an inverse-projection input or downstream route.
    """
    trajectory = data.get("trajectory", {})
    plan_path = trajectory.get("plan_path")
    if plan_path is None:
        return {"declared": False, "verified": False}, []
    errors: list[str] = []
    result: dict[str, Any] = {"declared": True, "verified": False}
    if not isinstance(plan_path, str) or not plan_path:
        return result, ["trajectory plan path must be a nonempty string"]
    path = Path(plan_path)
    if not path.is_absolute():
        path = dataset_path.parent / path
    try:
        plan = read_json(path)
    except (OSError, ValueError) as error:
        return result, [f"trajectory plan unavailable/invalid: {error}"]

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append("trajectory plan binding: " + message)

    digest = data.get("source_scene", {}).get("sha256_before")
    check(plan.get("source_asset_sha256") == digest, "source SHA-256 differs from dataset")
    check(
        plan.get("label", plan.get("data_kind")) == LABEL,
        "plan lacks PILOT / SYNTHETIC SAMPLE label",
    )
    check(plan.get("trajectory_id") == trajectory.get("trajectory_id"), "trajectory ID differs")
    check(plan.get("floor_id") == trajectory.get("floor_id"), "floor ID differs")
    check(
        plan.get("camera_ids") == [raw.get("camera_id") for raw in data.get("cameras", [])],
        "ordered camera catalog differs",
    )
    check(
        plan.get("observation_plane_z") == trajectory.get("observation_plane_z"),
        "diagnostic plane differs",
    )
    for key, legacy in (
        ("site_id", "corridor_reference"), ("sample_role", "VISIBLE_GAP_VISIBLE")
    ):
        if key in plan or key in data:
            check(plan.get(key, legacy) == data.get(key, legacy), f"{key} differs")
    basis = trajectory.get("projection_plane_basis")
    if basis is not None:
        check(basis == plan.get("projection_plane_basis"), "plane mesh basis differs")
        check(
            isinstance(basis, dict) and basis.get("source_asset_sha256") == digest,
            "diagnostic plane basis has a different source",
        )
    samples = plan.get("samples", [])
    rows = data.get("timestamps", [])
    check(len(samples) == len(rows), "timestamp/sample count differs")
    for index, (planned, row) in enumerate(zip(samples, rows, strict=False)):
        check(planned.get("timestamp") == row.get("timestamp"), f"timestamp {index} differs")
        expected = planned.get("probe_position")
        if expected is None:
            foot = planned.get("foot_position", planned.get("position"))
            height = plan.get("probe_height_units")
            if _vector(foot, 3) and _finite(height):
                expected = [foot[0], foot[1], foot[2] + height]
        actual = row.get("ground_truth", {}).get("position")
        check(
            _vector(expected, 3)
            and _vector(actual, 3)
            and _difference(expected, actual) <= SCENE_UNIT_TOLERANCE,
            f"timestamp {index} exported landmark differs from planned geometry",
        )
    support = plan.get("floor_support_evidence", {})
    result.update(
        {
            "path": str(path.resolve()),
            "sha256": sha256(path),
            "source_asset_sha256": plan.get("source_asset_sha256"),
            "site_id": plan.get("site_id"),
            "sample_count": len(samples),
            "support_probes_per_timestamp": support.get("support_probes_per_timestamp"),
            "target_full_sweep_clear": support.get("target_full_sweep_clear"),
            "physical_support_objects": support.get("physical_support_objects", []),
            "physical_floor_z_min": support.get("physical_floor_z_min"),
            "physical_floor_z_max": support.get("physical_floor_z_max"),
            "verified": not errors,
        }
    )
    return result, errors


def project_sanitized_frames(
    frames: tuple[ObservationFrame, ...],
    cameras: dict[str, Camera],
    plane: Plane,
) -> tuple[dict[tuple[int, str], tuple[float, float, float]], list[dict[str, Any]], int]:
    """A GT-free boundary: only existing 2D evidence and explicit calibration enter."""
    services = {key: InverseProjectionService(camera, plane) for key, camera in cameras.items()}
    projected: dict[tuple[int, str], tuple[float, float, float]] = {}
    failures: list[dict[str, Any]] = []
    expected_gap_rejections = 0
    for frame in frames:
        try:
            result = services[frame.camera_id].project_frame(frame)
        except InverseProjectionError as error:
            if (
                frame.status == VisibilityStatus.GAP
                and error.failure == InverseProjectionFailure.FRAME_NOT_OBSERVED
            ):
                expected_gap_rejections += 1
                continue
            failures.append(
                {
                    "frame_id": frame.frame_id,
                    "camera_id": frame.camera_id,
                    "failure": error.failure.value,
                    "message": str(error),
                }
            )
        else:
            projected[(frame.frame_id, frame.camera_id)] = tuple(result.world_position)
    return projected, failures, expected_gap_rejections


def validate_pilot(dataset_path: Path, *, verify_source: bool = True) -> dict[str, Any]:
    """Verify sampling, provenance, rendered artifacts and diagnostic projections."""
    dataset_path = dataset_path.resolve()
    run_root = dataset_path.parent
    data = read_json(dataset_path)
    errors: list[str] = []
    warnings: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    check(data.get("label") == LABEL, "dataset label must be PILOT / SYNTHETIC SAMPLE")
    check(data.get("duration_seconds") == 10, "duration window must be 10 seconds")
    check(data.get("sampling_fps") == 5, "sampling must be 5 FPS")
    sample_role = data.get("sample_role", "VISIBLE_GAP_VISIBLE")
    check(
        sample_role in SAMPLE_ROLES,
        "sample role must declare an occlusion pilot or visible control",
    )
    plan_binding, plan_errors = check_plan_binding(data, dataset_path)
    errors.extend(plan_errors)
    site_id = data.get("site_id")
    check(
        site_id is None or isinstance(site_id, str) and bool(site_id),
        "declared site ID must be a nonempty string",
    )
    source = data.get("source_scene", {})
    digest = source.get("sha256_before")
    check(
        isinstance(digest, str) and len(digest) == 64,
        "source SHA-256 must be present",
    )
    for name in ("sha256", "size", "mtime_ns"):
        check(
            source.get(f"{name}_before") == source.get(f"{name}_after"),
            f"source {name} changed during generation",
        )
    source_verified = False
    if verify_source:
        source_path = Path(source.get("path", ""))
        if source_path.is_file():
            stat = source_path.stat()
            live_digest = sha256(source_path)
            check(stat.st_size == source.get("size_after"), "live source size differs from export")
            check(
                stat.st_mtime_ns == source.get("mtime_ns_after"),
                "live source modification time differs from export",
            )
            check(live_digest == digest, "live source SHA-256 differs from export")
            source_verified = (
                stat.st_size == source.get("size_after")
                and stat.st_mtime_ns == source.get("mtime_ns_after")
                and live_digest == digest
            )
        else:
            errors.append("source scene is unavailable for identity verification")

    cameras: dict[str, Camera] = {}
    camera_rows = data.get("cameras", [])
    check(len(camera_rows) in (2, 3), "pilot must have 2 or 3 cameras")
    for raw in camera_rows:
        try:
            camera = Camera.model_validate(raw)
        except ValueError as error:
            errors.append(f"invalid Camera contract: {error}")
            continue
        check(camera.camera_id not in cameras, f"duplicate camera {camera.camera_id}")
        cameras[camera.camera_id] = camera

    trajectory = data.get("trajectory", {})
    trajectory_id = trajectory.get("trajectory_id")
    check(isinstance(trajectory_id, str) and bool(trajectory_id), "trajectory ID is missing")
    check(
        _finite(trajectory.get("length_scene_units"))
        and trajectory["length_scene_units"] > 0,
        "trajectory length must be positive finite scene units",
    )
    check(
        trajectory.get("scale_authority") == "UNVERIFIED",
        "pilot must retain the unverified physical unit scale",
    )
    warnings.append(
        "Physical metres-per-scene-unit and floor/camera-plane authority remain unverified. "
        "Diagnostic projection residuals are reported in pixels and scene units."
    )
    plane_z = trajectory.get("observation_plane_z")
    check(_finite(plane_z), "diagnostic observation plane z must be finite")

    rows = data.get("timestamps", [])
    check(len(rows) == 50, f"expected 50 timestamps, found {len(rows)}")
    timestamps = [row.get("timestamp") for row in rows]
    check(
        len(rows) == 50
        and all(
            _finite(value) and abs(value - index / 5) < 1e-9
            for index, value in enumerate(timestamps)
        ),
        "timestamps must be unique and ordered 0.0, 0.2, ..., 9.8",
    )
    check(
        [row.get("index") for row in rows] == list(range(50)),
        "timestamp indices must be contiguous 0..49",
    )

    frame_rows: list[dict[str, Any]] = []
    native_errors: list[float] = []
    depth_errors: list[float] = []
    truth_by_id: dict[int, tuple[float, float, float]] = {}
    visibility_counts: Counter[str] = Counter({"visible": 0, "occluded": 0, "out_of_FOV": 0})
    per_camera_counts = {camera_id: visibility_counts.copy() for camera_id in cameras}
    global_states: list[str] = []
    render_paths: set[Path] = set()
    render_hashes: dict[str, list[tuple[str, Any]]] = {key: [] for key in cameras}
    render_verified_count = 0
    image_qa_present_count = 0
    png_label_verified_count = 0
    png_site_label_verified_count = 0
    visible_landmark_image_verified_count = 0
    occluded_partial_body_image_count = 0
    for row in rows:
        index = row.get("index")
        timestamp = row.get("timestamp")
        truth = row.get("ground_truth", {})
        position = truth.get("position")
        valid_truth = _vector(position, 3)
        check(valid_truth, f"timestamp {index}: GT position must be a finite 3-vector")
        check(
            truth.get("provenance") == "GROUND_TRUTH",
            f"timestamp {index}: GT provenance must be GROUND_TRUTH",
        )
        check(
            truth.get("trajectory_id") == trajectory_id,
            f"timestamp {index}: trajectory ID mismatch",
        )
        check(
            truth.get("floor_id") == trajectory.get("floor_id"),
            f"timestamp {index}: trajectory floor mismatch",
        )
        if valid_truth and isinstance(index, int):
            truth_by_id[index] = tuple(position)
            if _finite(plane_z):
                check(
                    abs(position[2] - plane_z) <= SCENE_UNIT_TOLERANCE,
                    f"timestamp {index}: GT landmark leaves configured diagnostic plane",
                )

        camera_samples = row.get("per_camera", [])
        sample_ids = [sample.get("camera_id") for sample in camera_samples]
        check(
            len(sample_ids) == len(cameras) and set(sample_ids) == set(cameras),
            f"timestamp {index}: camera records must cover the complete catalog exactly once",
        )
        observed_any = False
        for sample in camera_samples:
            camera_id = sample.get("camera_id")
            if camera_id not in cameras:
                errors.append(f"timestamp {index}: unknown camera {camera_id}")
                continue
            camera = cameras[camera_id]
            context = f"timestamp {index}, camera {camera_id}"
            visibility = sample.get("visibility")
            check(
                visibility in ("visible", "occluded", "out_of_FOV"),
                f"{context}: invalid visibility classification",
            )
            visibility_counts[visibility] += 1
            per_camera_counts[camera_id][visibility] += 1
            observed_any |= visibility == "visible"
            check(_finite(sample.get("depth")), f"{context}: axial depth is non-finite")
            pixel = sample.get("pixel")
            check(
                _vector(pixel, 2) if visibility == "visible" else pixel is None,
                f"{context}: only visible records may publish finite observed pixels",
            )
            observation = sample.get("observation", {})
            if "observation_provenance" in sample:
                provenance = sample["observation_provenance"]
                check(
                    isinstance(provenance, dict)
                    and provenance.get("producer") == "BLENDER_SIMULATION_POINT_RAYCAST"
                    and provenance.get("data_kind") == "SYNTHETIC"
                    and provenance.get("label") == LABEL
                    and provenance.get("source_asset_sha256") == digest
                    and provenance.get("image_measurement") is False,
                    f"{context}: observation provenance differs from "
                    "simulation/source/label policy",
                )
                if site_id is not None:
                    check(
                        isinstance(provenance, dict) and provenance.get("site_id") == site_id,
                        f"{context}: observation provenance site differs from dataset",
                    )
            try:
                frame = ObservationFrame.model_validate(observation)
            except ValueError as error:
                errors.append(f"{context}: invalid sanitized observation: {error}")
            else:
                frame_rows.append(observation)
                check(
                    frame.frame_id == index and frame.timestamp == timestamp,
                    f"{context}: observation timestamp/frame identity mismatch",
                )
                check(frame.camera_id == camera_id, f"{context}: observation camera mismatch")
                check(frame.data_kind == "SYNTHETIC", f"{context}: evidence must be SYNTHETIC")
                check(
                    (frame.status == VisibilityStatus.OBSERVED) == (visibility == "visible"),
                    f"{context}: visibility and observation status disagree",
                )
                check(
                    list(frame.point_2d) == pixel if frame.point_2d else pixel is None,
                    f"{context}: exported observation and report pixels disagree",
                )
                if visibility == "occluded":
                    check(
                        frame.gap_reason
                        and frame.gap_reason.value
                        in ("OCCLUDED", "GEOMETRY_UNCERTAIN", "RAYCAST_LIMIT"),
                        f"{context}: occluded evidence must have an explicit raycast GAP reason",
                    )
                    if frame.gap_reason and frame.gap_reason.value == "OCCLUDED":
                        check(
                            bool(frame.occluder_id), f"{context}: occluded evidence lacks mesh ID"
                        )
                    else:
                        warnings.append(f"{context}: raycast visibility is uncertain; human review")
                if visibility == "out_of_FOV":
                    check(
                        frame.gap_reason
                        and frame.gap_reason.value
                        in ("BEHIND_CAMERA", "NEAR_CLIPPED", "FAR_CLIPPED", "OUTSIDE_FOV"),
                        f"{context}: out-of-FOV evidence has a non-camera GAP reason",
                    )

            if valid_truth:
                try:
                    forward = project_world(camera, tuple(position))
                except ValueError as error:
                    errors.append(f"{context}: forward projection failure: {error}")
                else:
                    check(
                        forward.in_frustum == (visibility != "out_of_FOV"),
                        f"{context}: calibration FOV and visibility disagree",
                    )
                    if _finite(sample.get("depth")):
                        depth_errors.append(abs(forward.axial_depth - sample["depth"]))
                    native = sample.get("blender_projection", {})
                    if _finite(native.get("axial_depth")):
                        depth_errors.append(abs(forward.axial_depth - native["axial_depth"]))
                    else:
                        errors.append(f"{context}: missing finite native Blender axial depth")
                    if forward.point_2d is not None:
                        check(
                            _vector(native.get("pixel"), 2),
                            f"{context}: native Blender projection pixel is missing/non-finite",
                        )
                        if _vector(native.get("pixel"), 2):
                            native_errors.append(_difference(forward.point_2d, native["pixel"]))
                    if visibility == "visible" and _vector(pixel, 2) and forward.point_2d:
                        native_errors.append(_difference(forward.point_2d, pixel))

            render = sample.get("render", {})
            relative = render.get("path")
            if not isinstance(relative, str) or not relative:
                errors.append(f"{context}: render path is missing")
                continue
            path = (run_root / relative).resolve()
            check(not Path(relative).is_absolute(), f"{context}: render path must be relative")
            check(path.is_relative_to(run_root), f"{context}: render escapes run root")
            check(path not in render_paths, f"{context}: reused render path")
            render_paths.add(path)
            if not path.is_relative_to(run_root) or not path.is_file():
                errors.append(f"{context}: render PNG is unavailable")
                continue
            actual_digest = sha256(path)
            check(actual_digest == render.get("sha256"), f"{context}: render SHA-256 mismatch")
            try:
                with Image.open(path) as image:
                    check(image.format == "PNG", f"{context}: render must be PNG")
                    check(
                        image.size == (camera.width, camera.height),
                        f"{context}: PNG size and camera calibration disagree",
                    )
                    image.load()
                    decoded_pixel_digest = hashlib.sha256(image.tobytes()).hexdigest()
                    if site_id is not None:
                        site_agrees = image.info.get("SiteID") == site_id
                        check(
                            site_agrees,
                            f"{context}: PNG SiteID differs from dataset",
                        )
                        png_site_label_verified_count += int(site_agrees)
                    if data.get("render_policy", {}).get("png_label_policy"):
                        expected_labels = {
                            "DatasetLabel": LABEL,
                            "DataKind": "SYNTHETIC",
                            "SourceAssetSHA256": digest,
                            "SimulationTimestampSeconds": str(timestamp),
                            "TrajectoryID": trajectory_id,
                        }
                        labels_agree = all(
                            image.info.get(key) == value for key, value in expected_labels.items()
                        )
                        check(
                            labels_agree,
                            f"{context}: PNG pilot/source/timestamp/trajectory labels mismatch",
                        )
                        png_label_verified_count += int(labels_agree)
                    if "image_diagnostics" in sample:
                        image_qa_present_count += 1
                        declared_qa = sample["image_diagnostics"]
                        if visibility == "visible":
                            check(
                                _finite(declared_qa.get("orange_target_pixels"))
                                and declared_qa["orange_target_pixels"] > 0,
                                f"{context}: visible frame QA reports no orange target pixels",
                            )
                            check(
                                declared_qa.get("orange_near_projected_landmark") is True,
                                f"{context}: visible frame QA fails projected landmark agreement",
                            )
                        rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
                        orange = (
                            (rgb[:, :, 0] > rgb[:, :, 1] * 1.35)
                            & (rgb[:, :, 0] > rgb[:, :, 2] * 1.8)
                            & (rgb[:, :, 0] > 0.15)
                        )
                        if visibility == "visible" and _vector(pixel, 2):
                            u, v = round(pixel[0]), round(pixel[1])
                            near = bool(
                                orange[max(0, v - 4) : v + 5, max(0, u - 4) : u + 5].any()
                            )
                            check(
                                near,
                                f"{context}: visible landmark has no orange target in PNG nearby",
                            )
                            visible_landmark_image_verified_count += int(near)
                        elif visibility == "occluded" and bool(orange.any()):
                            occluded_partial_body_image_count += 1
            except (OSError, ValueError) as error:
                errors.append(f"{context}: PNG decode failure: {error}")
            else:
                render_verified_count += 1
                if visibility == "visible":
                    render_hashes[camera_id].append((decoded_pixel_digest, pixel))
        expected_global = "OBSERVED" if observed_any else "GAP"
        check(row.get("gap_state") == expected_global, f"timestamp {index}: global GAP mismatch")
        global_states.append(expected_global)

    for camera_id, renders in render_hashes.items():
        previous: tuple[str, Any] | None = None
        for current in renders:
            if (
                previous
                and current[0] == previous[0]
                and _vector(current[1], 2)
                and _vector(previous[1], 2)
                and _difference(current[1], previous[1]) >= 2
            ):
                warnings.append(
                    f"{camera_id}: visible target moves by at least 2 pixels but consecutive "
                    "visible image pixels are identical; inspect target rendering."
                )
                break
            previous = current

    expected_frame_count = 50 * len(cameras)
    check(
        render_verified_count == expected_frame_count,
        f"expected {expected_frame_count} decodable camera renders, found {render_verified_count}",
    )
    check(
        image_qa_present_count == expected_frame_count,
        "every pilot camera record requires image quality diagnostics",
    )
    sanitized_path = run_root / "observations.json"
    try:
        sanitized = read_json(sanitized_path)
    except (OSError, ValueError) as error:
        errors.append(f"sanitized observations artifact unavailable/invalid: {error}")
        sanitized = {}
    check(sanitized.get("label") == LABEL, "observations artifact must have pilot label")
    check(sanitized.get("data_kind") == "SYNTHETIC", "observations artifact must be SYNTHETIC")
    if site_id is not None:
        check(
            sanitized.get("site_id") == site_id,
            "sanitized observations site differs from dataset",
        )
        try:
            separate_truth = read_json(run_root / "ground_truth.json")
        except (OSError, ValueError) as error:
            errors.append(f"separate GT artifact unavailable/invalid: {error}")
        else:
            check(
                separate_truth.get("site_id") == site_id
                and separate_truth.get("label") == LABEL
                and separate_truth.get("provenance") == "GROUND_TRUTH"
                and separate_truth.get("source_asset_sha256") == digest
                and separate_truth.get("trajectory_id") == trajectory_id,
                "separate GT artifact site/source/label/trajectory differs from dataset",
            )
            check(
                separate_truth.get("samples")
                == [{"timestamp": row["timestamp"], **row["ground_truth"]} for row in rows],
                "separate GT artifact samples differ from dataset evaluation records",
            )
    check(
        sanitized.get("source_asset_sha256") == digest,
        "observations source identity does not match dataset",
    )
    sanitized_rows = sanitized.get("frames", [])
    check(
        sanitized_rows == frame_rows,
        "separate sanitized observations differ from dataset evidence",
    )
    frames: list[ObservationFrame] = []
    for raw in sanitized_rows:
        try:
            frames.append(ObservationFrame.model_validate(raw))
        except ValueError as error:
            errors.append(f"sanitized artifact violates GT-free ObservationFrame contract: {error}")
    check(len(frames) == expected_frame_count, "sanitized evidence count does not match pilot")
    frame_keys = [(frame.frame_id, frame.camera_id) for frame in frames]
    check(len(frame_keys) == len(set(frame_keys)), "duplicate sanitized frame/camera identity")
    check(len({frame.target_id for frame in frames}) == 1, "pilot requires one synthetic target")

    inverse_failures: list[dict[str, Any]] = []
    inverse_errors: list[float] = []
    projected: dict[tuple[int, str], tuple[float, float, float]] = {}
    gap_rejections = 0
    if _finite(plane_z) and trajectory.get("floor_id"):
        plane = Plane(
            plane_id=f"pilot_landmark_plane:{trajectory_id}",
            point=(0.0, 0.0, plane_z),
            normal=(0.0, 0.0, 1.0),
            floor_id=trajectory["floor_id"],
        )
        known_frames = tuple(frame for frame in frames if frame.camera_id in cameras)
        projected, inverse_failures, gap_rejections = project_sanitized_frames(
            known_frames, cameras, plane
        )
        # Truth enters only evaluation after the projection call has returned.
        for (frame_id, _camera_id), point in projected.items():
            if frame_id in truth_by_id:
                inverse_errors.append(_difference(point, truth_by_id[frame_id]))
    check(not inverse_failures, f"{len(inverse_failures)} unexpected inverse projection failures")
    max_native_error = max(native_errors, default=0.0)
    max_depth_error = max(depth_errors, default=0.0)
    max_inverse_error = max(inverse_errors, default=0.0)
    check(max_native_error <= PIXEL_TOLERANCE, "forward projection pixel residual exceeds 0.02 px")
    check(
        max_depth_error <= SCENE_UNIT_TOLERANCE,
        "axial-depth residual exceeds 0.02 scene units",
    )
    check(
        max_inverse_error <= SCENE_UNIT_TOLERANCE,
        "diagnostic inverse projection residual exceeds 0.02 scene units",
    )
    observed_count = visibility_counts["visible"]
    check(len(projected) == observed_count, "not every visible frame projected onto pilot plane")
    check(bool(observed_count), "pilot contains no visible observations")
    if occluded_partial_body_image_count:
        warnings.append(
            f"{occluded_partial_body_image_count} occluded-landmark camera records show orange "
            "target body pixels. Point occlusion and partial-body visibility are distinct; "
            "these are simulation point observations, not image-detector outputs."
        )
    gap_indices = [index for index, status in enumerate(global_states) if status == "GAP"]
    closed_global_gap = any(
        "OBSERVED" in global_states[:index] and "OBSERVED" in global_states[index + 1 :]
        for index in gap_indices
    )
    if sample_role == "FULLY_OBSERVED_CONTROL":
        check(
            len(global_states) == 50 and not gap_indices,
            "fully observed control requires all 50 global timestamps observed",
        )
    else:
        check(closed_global_gap, "pilot must contain observed -> global GAP -> observed recovery")
    return {
        "schema_version": "blender-pilot-validation-v1",
        "label": LABEL,
        "sample_role": sample_role,
        "site_id": data.get("site_id"),
        "status": "PASS_WITH_REVIEW" if not errors else "FAILED",
        "dataset_sha256": sha256(dataset_path),
        "source_identity_verified": source_verified,
        "trajectory_plan_binding": plan_binding,
        "timestamp_count": len(rows),
        "camera_ids": list(cameras),
        "expected_camera_frame_count": expected_frame_count,
        "decoded_render_count": render_verified_count,
        "render_target_quality": {
            "image_diagnostics_present_count": image_qa_present_count,
            "png_provenance_labels_verified_count": png_label_verified_count,
            "png_site_labels_verified_count": png_site_label_verified_count,
            "visible_landmark_png_verified_count": visible_landmark_image_verified_count,
            "occluded_landmark_partial_body_visible_count": occluded_partial_body_image_count,
            "method": "INDEPENDENT_PNG_ORANGE_MASK_NEAR_VISIBLE_POINT_DIAGNOSTIC_ONLY",
        },
        "sanitized_observation_count": len(frames),
        "visibility_counts": dict(visibility_counts),
        "per_camera_visibility_counts": {
            key: dict(value) for key, value in per_camera_counts.items()
        },
        "global_observed_timestamp_count": global_states.count("OBSERVED"),
        "global_gap_timestamp_count": len(gap_indices),
        "global_gap_indices": gap_indices,
        "observed_gap_observed_recovery": closed_global_gap,
        "projection": {
            "native_blender_forward_max_error_pixels": max_native_error,
            "axial_depth_max_error_scene_units": max_depth_error,
            "pilot_plane_inverse_projected_count": len(projected),
            "pilot_plane_inverse_max_error_scene_units": max_inverse_error,
            "pilot_plane_inverse_mean_error_scene_units": (
                sum(inverse_errors) / len(inverse_errors) if inverse_errors else None
            ),
            "expected_gap_rejections": gap_rejections,
            "unexpected_failures": inverse_failures,
            "plane_authority": "PILOT_DIAGNOSTIC_ONLY_NOT_FORMAL_FLOOR_BINDING",
            "pixel_tolerance": PIXEL_TOLERANCE,
            "scene_unit_tolerance": SCENE_UNIT_TOLERANCE,
        },
        "gt_isolation": {
            "sanitized_observation_schema": "amidst.domain.evidence.ObservationFrame",
            "inverse_inputs": ["sanitized 2D frames", "camera calibration", "explicit pilot plane"],
            "ground_truth_used_for": [
                "forward simulation evaluation", "post-projection evaluation"
            ],
            "graph_ranking_reconstruction_benchmark_run": False,
        },
        "full_dataset_ready": False,
        "full_dataset_readiness_reason": (
            "Human image-quality review, physical scale and formal geometry/floor/camera-plane "
            "authority are still pending; this checks only the small synthetic pilot."
        ),
        "errors": errors,
        "warnings": warnings,
    }


def render_report(result: dict[str, Any]) -> str:
    projection = result["projection"]
    lines = [
        "# Blender pilot validation — PILOT / SYNTHETIC SAMPLE",
        "",
        f"Status: **{result['status']}**. Source identity verified: "
        f"`{result['source_identity_verified']}`.",
        "",
        f"- Site: {result['site_id']}; sample role: {result['sample_role']}.",
        f"- Trajectory plan binding: {result['trajectory_plan_binding']}.",
        f"- Timestamps: {result['timestamp_count']}/50; decoded renders: "
        f"{result['decoded_render_count']}/{result['expected_camera_frame_count']}.",
        f"- Cameras: {', '.join(result['camera_ids'])}.",
        f"- Per-camera records: {result['visibility_counts']}.",
        f"- Global GAP timestamps: {result['global_gap_timestamp_count']}; "
        f"observed → GAP → observed: {result['observed_gap_observed_recovery']}.",
        f"- Native Blender forward residual: "
        f"{projection['native_blender_forward_max_error_pixels']:.8g} pixels maximum.",
        f"- Axial-depth residual: {projection['axial_depth_max_error_scene_units']:.8g} "
        "scene units maximum.",
        f"- Pilot landmark-plane inverse projection: "
        f"{projection['pilot_plane_inverse_projected_count']} visible records; "
        f"{projection['pilot_plane_inverse_max_error_scene_units']:.8g} scene units maximum.",
        f"- GAP records correctly rejected by inverse projection: "
        f"{projection['expected_gap_rejections']}.",
        f"- Visible landmarks verified against orange target PNG pixels: "
        f"{result['render_target_quality']['visible_landmark_png_verified_count']}; "
        f"occluded landmarks with partially visible target body: "
        f"{result['render_target_quality']['occluded_landmark_partial_body_visible_count']}.",
        "",
        "The inverse-projection call reads only strict sanitized 2D ObservationFrame records, "
        "camera calibration and an explicit static diagnostic plane. GT is read afterward "
        "for evaluation. No Graph, ranking, reconstruction or benchmark runs occur.",
        "",
        "**Full dataset readiness: pending.** " + result["full_dataset_readiness_reason"],
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {item}" for item in result["errors"])
    if not result["errors"]:
        lines.append("- None.")
    lines.extend(["", "## Review notes", ""])
    lines.extend(f"- {item}" for item in result["warnings"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()
    result = validate_pilot(args.dataset)
    root = args.dataset.resolve().parent
    (root / "validation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    (root / "validation.md").write_text(render_report(result), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "timestamps": result["timestamp_count"],
                "renders": result["decoded_render_count"],
                "visibility": result["visibility_counts"],
                "global_gap_timestamps": result["global_gap_timestamp_count"],
                "errors": result["errors"],
            },
            ensure_ascii=False,
        )
    )
    raise SystemExit(0 if not result["errors"] else 1)


if __name__ == "__main__":
    main()
