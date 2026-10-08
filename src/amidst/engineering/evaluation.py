"""Independent local evaluation/debug after content-bound inference freeze.

Only this module reads the simulation GT sidecar.  It cannot be called through
Agent tools and never changes perception, association, candidates or snapshots.
The separate presentation export uses frozen inference alone, without GT.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import Field, FiniteFloat

from amidst.engineering.access import FreezeReceipt, digest
from amidst.engineering.association import InferenceBundle, SyntheticStaticContext
from amidst.engineering.perception import (
    Measurement,
    PerceptionResult,
    PixelModel,
    RGBFrame,
    frame_manifest_sha256,
)
from amidst.engineering.registry import LocationRegistry, ResourceScope, opaque_ref
from amidst.integration.repositories import RepositorySnapshot

if TYPE_CHECKING:
    from amidst.engineering.run import RunManifest


class FrozenRunError(ValueError):
    """Fixed error codes keep private local locators out of external diagnostics."""


class TruthActor(PixelModel):
    actor_identity: str
    position_xyz_m: tuple[FiniteFloat, FiniteFloat, FiniteFloat]


class TruthAnnotation(PixelModel):
    actor_identity: str
    contact_uv: tuple[FiniteFloat, FiniteFloat]
    unoccluded_bbox_xyxy: tuple[int, int, int, int]
    contact_inside_frame: bool


class TruthFrame(PixelModel):
    timestamp: FiniteFloat
    actors: tuple[TruthActor, ...] = ()
    camera_id: str | None = None
    render_annotations: tuple[TruthAnnotation, ...] = ()


class TruthExport(PixelModel):
    schema_version: Literal["simulation.export.v1"]
    boundary: Literal["EVALUATION_DEBUG_ONLY"]
    recipe: dict[str, object]
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ground_truth: tuple[TruthFrame, ...]


@dataclass(frozen=True)
class VerifiedRun:
    manifest: RunManifest
    registry: LocationRegistry
    context: SyntheticStaticContext
    modes: tuple[tuple[FreezeReceipt, PerceptionResult, InferenceBundle], ...]


def _verified_run(root: Path) -> VerifiedRun:
    # Lazy import permits run.py to use evaluation without a module cycle.
    from amidst.engineering.run import (
        EngineeringConfig,
        RunManifest,
        algorithm_hashes,
        effective_config_hash,
        load_facades,
    )

    if not (root / "run_manifest.json").is_file():
        raise FrozenRunError("FREEZE_REQUIRED")
    try:
        # Shared read path verifies new envelopes/bindings without ever loading GT.
        # Independent checks below also bind the evaluation pixel/frame population.
        load_facades(root)
    except (OSError, ValueError) as error:
        raise FrozenRunError("FREEZE_BINDING_MISMATCH") from error
    try:
        manifest = RunManifest.model_validate_json((root / "run_manifest.json").read_bytes())
        registry = LocationRegistry.model_validate_json((root / "registry.json").read_bytes())
        context = SyntheticStaticContext.model_validate_json(
            (root / "static_context.json").read_bytes()
        )
        config = EngineeringConfig.model_validate_json(
            (root / "engineering_config.json").read_bytes()
        )
    except (OSError, ValueError) as error:
        raise FrozenRunError("FROZEN_INPUT_INVALID") from error
    if not manifest.receipts:
        raise FrozenRunError("FREEZE_REQUIRED")
    if manifest.algorithm_hashes != algorithm_hashes():
        raise FrozenRunError("IMPLEMENTATION_FREEZE_MISMATCH")
    scope = manifest.scope
    if (
        registry.sha256 != manifest.registry_sha256
        or manifest.source_sha256 != scope.source_sha256
        or context.source_sha256 != scope.source_sha256
        or context.context_sha256 != scope.spatial_context_sha256
        or context.spatial_context_id != scope.spatial_context_id
    ):
        raise FrozenRunError("CONTEXT_FREEZE_MISMATCH")
    frames = tuple(frame for frame in registry.frames if frame.scope == scope)
    if not frames or len(frames) != len(manifest.frame_links):
        raise FrozenRunError("MEDIA_BINDING_MISMATCH")
    reverse_links = {value: key for key, value in manifest.frame_links.items()}
    if len(reverse_links) != len(manifest.frame_links):
        raise FrozenRunError("MEDIA_BINDING_MISMATCH")
    rgb_frames = []
    for frame in frames:
        path = root / frame.relative_path
        if frame.media_ref not in reverse_links or not path.resolve().is_relative_to(
            root.resolve()
        ):
            raise FrozenRunError("MEDIA_BINDING_MISMATCH")
        try:
            payload = path.read_bytes()
        except OSError as error:
            raise FrozenRunError("MEDIA_UNAVAILABLE") from error
        if len(payload) != frame.size_bytes or sha256(payload).hexdigest() != frame.sha256:
            raise FrozenRunError("MEDIA_FREEZE_MISMATCH")
        rgb_frames.append(
            RGBFrame(
                media_ref=reverse_links[frame.media_ref],
                camera_id=frame.camera_id,
                timestamp=frame.timestamp,
                path=path,
                sha256=frame.sha256,
                width=frame.width,
                height=frame.height,
            )
        )
    dataset_hash = frame_manifest_sha256(rgb_frames)
    media_hash = digest([(frame.media_ref, frame.sha256) for frame in registry.frames])
    modes = []
    seen_modes: set[str] = set()
    for receipt in manifest.receipts:
        binding = receipt.binding
        mode = binding.observation_mode
        if mode in seen_modes:
            raise FrozenRunError("DUPLICATE_MODE_FREEZE")
        seen_modes.add(mode)
        try:
            perception = PerceptionResult.model_validate_json(
                (root / f"perception_{mode}.json").read_bytes(),
            )
            inference = InferenceBundle.model_validate_json(
                (root / f"inference_{mode}.json").read_bytes(),
            )
            snapshot = RepositorySnapshot.model_validate_json(
                (root / f"snapshot_{mode}.json").read_bytes(),
            )
        except (OSError, ValueError) as error:
            raise FrozenRunError("FROZEN_INPUT_INVALID") from error
        expected_scope = (
            scope.place_id,
            scope.model_id,
            scope.model_revision,
            scope.run_id,
            scope.clock_id,
            opaque_ref("source", scope.source_id, scope.source_sha256),
            scope.spatial_context_id,
        )
        bound_scope = (
            binding.place_id,
            binding.model_id,
            binding.model_revision,
            binding.run_id,
            binding.clock_id,
            binding.source_ref,
            binding.spatial_context_id,
        )
        inferred_scope = (
            inference.scope.place_id,
            inference.scope.model_id,
            inference.scope.model_revision,
            inference.scope.run_id,
            inference.scope.clock_id,
            inference.scope.source_ref,
            inference.scope.spatial_context_id,
        )
        if (
            bound_scope != expected_scope
            or inferred_scope != expected_scope
            or perception.model_id != scope.model_id
            or perception.run_id != scope.run_id
            or binding.config_sha256 != manifest.config_sha256
            or effective_config_hash(
                config,
                manifest.generator_config_sha256,
                context,
                inference.policy,
                manifest.algorithm_hashes,
            )
            != manifest.config_sha256
            or binding.registry_sha256 != registry.sha256
            or binding.registry_version != registry.schema_version
            or binding.media_sha256 != media_hash
            or binding.dataset_sha256 != dataset_hash
            or perception.input_manifest_sha256 != dataset_hash
            or inference.input_manifest_sha256 != dataset_hash
            or binding.producer_sha256 != perception.producer_sha256
            or inference.producer_sha256 != perception.producer_sha256
            or inference.scope.source_sha256 != scope.source_sha256
            or inference.scope.context_sha256 != scope.spatial_context_sha256
            or inference.static_context_sha256 != digest(context)
            or inference.snapshot != snapshot
            or not receipt.verify(binding, inference, perception.model_dump(mode="json"))
        ):
            raise FrozenRunError("FREEZE_BINDING_MISMATCH")
        if {row.frame_ref for row in perception.frame_statuses} != set(manifest.frame_links):
            raise FrozenRunError("FRAME_STATUS_BINDING_MISMATCH")
        modes.append((receipt, perception, inference))
    return VerifiedRun(manifest, registry, context, tuple(modes))


def _write_debug(path: Path, value: object) -> None:
    """Evaluation outputs are separate mutable local debug products."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _stats(values: list[float]) -> dict[str, float | int | None]:
    ordered = sorted(values)
    return {
        "samples": len(ordered),
        "mean": math.fsum(ordered) / len(ordered) if ordered else None,
        "rms": math.sqrt(math.fsum(value * value for value in ordered) / len(ordered))
        if ordered
        else None,
        "maximum": ordered[-1] if ordered else None,
    }


def _iou(box: tuple[float, float, float, float], truth: tuple[int, int, int, int]) -> float:
    x0, y0, x1, y1 = box
    a0, b0, a1, b1 = truth
    intersection = max(0.0, min(x1, a1) - max(x0, a0)) * max(
        0.0,
        min(y1, b1) - max(y0, b0),
    )
    union = (x1 - x0) * (y1 - y0) + (a1 - a0) * (b1 - b0) - intersection
    return intersection / union if union > 0 else 0.0


def _eligible(
    annotation: TruthAnnotation, camera_id: str, width: int, height: int, *, bbox: bool = False
) -> bool:
    u, v = annotation.contact_uv
    if not annotation.contact_inside_frame or not 0 <= u < width or not 0 <= v < height:
        return False
    # Exact procedural-v1 recipe only; never extrapolated to another model.
    if camera_id == "CAM_A" and 138 <= u <= 214 and 105 <= v <= 239:
        return False
    if bbox:
        x0, y0, x1, y1 = annotation.unoccluded_bbox_xyxy
        if x0 < 0 or y0 < 0 or x1 > width or y1 > height:
            return False
        if camera_id == "CAM_A" and x0 < 215 and x1 > 138 and y0 < 240 and y1 > 105:
            return False
    return True


def _mode_evaluation(
    perception: PerceptionResult,
    inference: InferenceBundle,
    truth: TruthExport,
    registry: LocationRegistry,
    scope: ResourceScope,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    annotations = {
        (row.camera_id, row.timestamp): row.render_annotations
        for row in truth.ground_truth
        if row.camera_id is not None
    }
    actors = {
        (row.timestamp, actor.actor_identity): actor.position_xyz_m
        for row in truth.ground_truth
        for actor in row.actors
    }
    frame_sizes = {
        (row.camera_id, row.timestamp): (row.width, row.height)
        for row in registry.frames
        if row.scope == scope
    }
    by_frame: dict[tuple[str, float], list[Measurement]] = defaultdict(list)
    for measurement in perception.measurements:
        by_frame[(measurement.camera_id, measurement.timestamp)].append(measurement)
    projected = {row.observation_id: row for row in inference.projected_measurements}
    pixel_errors, ground_errors, best_ious = [], [], []
    eligible_count, matched_count = 0, 0
    details: list[dict[str, object]] = []
    for key, (width, height) in sorted(frame_sizes.items()):
        camera_id, timestamp = key
        original = annotations.get(key, ())
        eligible = [row for row in original if _eligible(row, camera_id, width, height)]
        bbox_eligible = [
            row for row in original if _eligible(row, camera_id, width, height, bbox=True)
        ]
        measurements = by_frame[key]
        eligible_count += len(eligible)
        pairs = sorted(
            (math.dist(row.contact_pixel, annotation.contact_uv), index, gt_index)
            for index, row in enumerate(measurements)
            for gt_index, annotation in enumerate(eligible)
        )
        used_measurements, used_annotations = set(), set()
        for distance, index, gt_index in pairs:
            if (
                distance <= 24
                and index not in used_measurements
                and gt_index not in used_annotations
            ):
                matched_count += 1
                used_measurements.add(index)
                used_annotations.add(gt_index)
        for measurement in measurements:
            if not eligible:
                continue
            annotation = min(
                eligible,
                key=lambda item: math.dist(
                    measurement.contact_pixel,
                    item.contact_uv,
                ),
            )
            pixel_error = math.dist(measurement.contact_pixel, annotation.contact_uv)
            pixel_errors.append(pixel_error)
            projected_measurement = projected.get(measurement.observation_id)
            gt_position = actors.get((timestamp, annotation.actor_identity))
            ground_error = None
            if projected_measurement and projected_measurement.point and gt_position:
                ground_error = math.dist(projected_measurement.point.world_position, gt_position)
                ground_errors.append(ground_error)
            best_iou = max(
                (_iou(measurement.bbox_xyxy, row.unoccluded_bbox_xyxy) for row in bbox_eligible),
                default=None,
            )
            if best_iou is not None:
                best_ious.append(best_iou)
            details.append(
                {
                    "camera_id": camera_id,
                    "timestamp": timestamp,
                    "measurement_id": measurement.observation_id,
                    "measurement_status": measurement.status,
                    "evaluation_only_nearest_actor": annotation.actor_identity,
                    "truth_contact_uv": annotation.contact_uv,
                    "pixel_contact_error": pixel_error,
                    "ground_contact_error_m": ground_error,
                    "best_unoccluded_bbox_iou": best_iou,
                }
            )
    return {
        "frame_count": len(perception.frame_statuses),
        "measurement_count": len(perception.measurements),
        "local_track_count": len(perception.tracks),
        "frame_status_counts": dict(Counter(row.status for row in perception.frame_statuses)),
        "measurement_status_counts": dict(Counter(row.status for row in perception.measurements)),
        "eligible_actor_contacts": eligible_count,
        "one_to_one_contact_matches_24px": matched_count,
        "eligible_detection_recall_24px": matched_count / eligible_count
        if eligible_count
        else None,
        "nearest_eligible_pixel_contact_error_px": _stats(pixel_errors),
        "same_nearest_contact_ground_error_m": _stats(ground_errors),
        "best_unoccluded_bbox_iou": _stats(best_ious),
        "association_kind_counts": dict(
            Counter(row.kind for row in inference.association_hypotheses)
        ),
        "association_status_counts": dict(
            Counter(row.status for row in inference.association_hypotheses)
        ),
        "projection_status_counts": dict(
            Counter(row.status for row in inference.projected_measurements)
        ),
        "canonical_gap_count": len(inference.snapshot.gaps),
        "candidate_count": sum(len(row.event.candidates) for row in inference.snapshot.gaps),
        "association_identity_precision": "N/A",
        "association_identity_recall": "N/A",
        "detection_precision": "N/A",
        "formal_research_metrics": "N/A",
    }, details


def evaluate_frozen_run(root: Path) -> dict[str, object]:
    """Verify every mode first, then read GT for independent local aggregate metrics."""
    root = root.resolve()
    verified = _verified_run(root)
    gt_path = root / "simulation" / "export" / "ground_truth.json"
    try:
        gt_bytes = gt_path.read_bytes()
        truth = TruthExport.model_validate_json(gt_bytes)
    except (OSError, ValueError) as error:
        raise FrozenRunError("EVALUATION_TRUTH_UNAVAILABLE") from error
    scope = verified.manifest.scope
    if (
        truth.dataset_sha256 != verified.modes[0][0].binding.dataset_sha256
        or digest(truth.recipe) != verified.manifest.generator_config_sha256
        or digest(
            {
                key: value
                for key, value in truth.recipe.items()
                if key not in {"run_id", "frame_count", "fps"}
            }
        )
        != verified.manifest.model_source_sha256
        or truth.recipe.get("generator_version") != "procedural-rgb-lab-v1"
        or truth.recipe.get("model_id") != scope.model_id
        or truth.recipe.get("run_id") != scope.run_id
        or truth.recipe.get("occlusion") != "CAM_A static pillar x=[138,214] y=[105,239]"
    ):
        raise FrozenRunError("EVALUATION_TRUTH_BINDING_MISMATCH")
    frame_keys = {
        (frame.camera_id, frame.timestamp)
        for frame in verified.registry.frames
        if frame.scope == scope
    }
    annotation_rows = [row for row in truth.ground_truth if row.camera_id is not None]
    actor_rows = [row for row in truth.ground_truth if row.camera_id is None]
    annotation_keys = [(row.camera_id, row.timestamp) for row in annotation_rows]
    actor_times = [row.timestamp for row in actor_rows]
    identities = truth.recipe.get("actors")
    if (
        not isinstance(identities, list)
        or not identities
        or not all(isinstance(identity, str) for identity in identities)
        or len(set(identities)) != len(identities)
        or len(set(annotation_keys)) != len(annotation_keys)
        or set(annotation_keys) != frame_keys
        or len(set(actor_times)) != len(actor_times)
        or set(actor_times) != {timestamp for _, timestamp in frame_keys}
        or any(
            {actor.actor_identity for actor in row.actors} != set(identities)
            or len(row.actors) != len(identities)
            for row in actor_rows
        )
        or any(
            {item.actor_identity for item in row.render_annotations} != set(identities)
            or len(row.render_annotations) != len(identities)
            for row in annotation_rows
        )
    ):
        raise FrozenRunError("EVALUATION_TRUTH_INCOMPLETE")
    modes, debug = {}, {}
    for receipt, perception, inference in verified.modes:
        summary, details = _mode_evaluation(perception, inference, truth, verified.registry, scope)
        modes[receipt.binding.observation_mode] = summary
        debug[receipt.binding.observation_mode] = details
    result: dict[str, object] = {
        "schema_version": "simulation.evaluation.v1",
        "status": "SYNTHETIC_ENGINEERING_MEASURED",
        "origin": "SYNTHETIC",
        "authority": "ENGINEERING_FIXTURE_ONLY",
        "run_id": scope.run_id,
        "model_id": scope.model_id,
        "dataset_sha256": verified.modes[0][0].binding.dataset_sha256,
        "config_sha256": verified.manifest.config_sha256,
        "registry_sha256": verified.registry.sha256,
        "freeze_receipt_sha256": [receipt.receipt_sha256 for receipt, _, _ in verified.modes],
        "evaluation_truth_sha256": sha256(gt_bytes).hexdigest(),
        "eligibility": {
            "contact": "GT contact inside RGB image and outside exact v1 static pillar image mask",
            "bbox": "Full annotated bbox inside image with no exact v1 pillar intersection",
            "recall_matching": "Greedy one-to-one nearest pixel contact, distance <=24px",
            "error_matching": "Per-measurement nearest eligible contact, evaluation only",
            "merged_partial_measurements": "Retained; one component can match at most one actor",
        },
        "modes": modes,
        "formal_phase1_acceptance": False,
        "external_model_calls": False,
        "limitations": [
            "Procedural scene diagnostics do not certify school or real cameras.",
            "Nearest-contact/best-IoU diagnostics are not mAP or identity accuracy.",
            "Association has multiple provisional hypotheses; evaluation never chooses a winner.",
            "Detailed actor annotations remain in local evaluation/debug only.",
        ],
    }
    _write_debug(
        root / "evaluation" / "debug" / "details.json",
        {
            "boundary": "LOCAL_EVALUATION_DEBUG_ONLY",
            "truth_sha256": sha256(gt_bytes).hexdigest(),
            "modes": debug,
        },
    )
    _write_debug(root / "evaluation" / "summary.json", result)
    return result


def export_inference_demo(root: Path) -> dict[str, object]:
    """Create a standalone PNG/RRD from verified inference; this never reads GT."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import rerun as rr

    root = root.resolve()
    verified = _verified_run(root)
    receipt, _, inference = verified.modes[0]
    output = root / "presentation"
    output.mkdir(parents=True, exist_ok=True)
    png_path, rrd_path = output / "inference.png", output / "inference.rrd"
    figure = plt.figure(figsize=(10, 5.5))
    axis = figure.add_subplot(111, projection="3d")
    traces: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    cameras = {}
    for row in inference.projected_measurements:
        if row.point is not None:
            traces[row.local_track_id].append(row.point.world_position)
            cameras[row.local_track_id] = row.camera_id
    colors = {"CAM_A": "#176fb2", "CAM_B": "#228453"}
    for track, points in traces.items():
        axis.plot(
            [p[0] for p in points],
            [p[1] for p in points],
            [p[2] for p in points],
            color=colors.get(cameras[track], "#888888"),
            marker=".",
            linewidth=1,
        )
    for gap in inference.snapshot.gaps:
        for candidate in gap.event.candidates:
            route = candidate.polyline
            axis.plot(
                [p[0] for p in route],
                [p[1] for p in route],
                [p[2] for p in route],
                color="#d6811d",
                linestyle="--",
                linewidth=0.8,
                alpha=0.5,
            )
    axis.set(
        xlabel="X (m)",
        ylabel="Y (m)",
        zlabel="Z (m)",
        xlim=(0, 12),
        ylim=(0, 4),
        zlim=(0, 2),
        title="Synthetic RGB → projected tracks and all inferred route alternatives",
    )
    figure.text(
        0.03,
        0.02,
        "Blue/green: pixel-derived local tracks. Orange: INFERRED_GAP alternatives. "
        "Configured engineering geometry; uncertainty retained. No GT overlay.",
        fontsize=8,
    )
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    figure.savefig(png_path, dpi=150)
    plt.close(figure)
    recording = rr.RecordingStream(
        "amidst-simulation-inference", recording_id=receipt.inference_sha256
    )
    recording.save(rrd_path)
    recording.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
    recording.log(
        "notes",
        rr.TextDocument(
            "SYNTHETIC ENGINEERING ONLY. Pixel-derived tracks and ALL inferred alternatives. "
            "No confirmed global identity; no GT overlay; configured floor authority only.",
        ),
        static=True,
    )
    for row in inference.projected_measurements:
        if row.point is None:
            continue
        recording.set_time("synthetic_seconds", duration=row.timestamp)
        entity = "world/projected/track-" + digest(row.local_track_id)[:16]
        color = (23, 111, 178) if row.camera_id == "CAM_A" else (34, 132, 83)
        recording.log(
            entity,
            rr.Points3D(
                [row.point.world_position],
                colors=[color],
                radii=0.05,
                labels=["PROJECTED " + row.camera_id],
            ),
        )
    for gap in inference.snapshot.gaps:
        for candidate in gap.event.candidates:
            recording.log(
                "world/inferred/route-" + digest(candidate.candidate_id)[:16],
                rr.LineStrips3D(
                    [candidate.polyline],
                    colors=[(214, 129, 29)],
                    radii=0.015,
                    labels=["INFERRED_GAP"],
                ),
                static=True,
            )
    recording.flush(timeout_sec=30)
    recording.disconnect()
    result: dict[str, object] = {
        "schema_version": "simulation.presentation.v1",
        "origin": "SYNTHETIC",
        "authority": "FROZEN_PIXEL_INFERENCE_WITH_CONFIGURED_GEOMETRY",
        "run_id": verified.manifest.scope.run_id,
        "mode": receipt.binding.observation_mode,
        "inference_sha256": receipt.inference_sha256,
        "freeze_sha256": receipt.receipt_sha256,
        "gt_overlay": False,
        "all_route_alternatives": True,
        "artifacts": [
            {
                "relative_path": str(path.relative_to(root)),
                "sha256": sha256(path.read_bytes()).hexdigest(),
                "size_bytes": path.stat().st_size,
            }
            for path in (png_path, rrd_path)
        ],
    }
    _write_debug(output / "manifest.json", result)
    return result
