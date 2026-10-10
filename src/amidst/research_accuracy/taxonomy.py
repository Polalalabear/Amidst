"""Post-freeze, scoped baseline error taxonomy; evaluation/debug use only.

No runtime module imports this helper. It reads the two explicit four-camera v1
freezes and their isolated baseline replays, validates receipts, then opens truth
to reproduce bounded error counts and opaque evidence references. No RGB image is
decoded, no global camera/pair search is performed, and no policy is selected.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from amidst.engineering.access import digest
from amidst.engineering.local_association import InferenceBundle
from amidst.engineering.local_behavior import LocalBehaviorBundle
from amidst.engineering.local_evaluation import ResearchTruth, _labels
from amidst.engineering.local_pilot import _load, _save, frozen_mode
from amidst.engineering.perception import PerceptionResult


def _examples(
    perception: PerceptionResult,
    inference: InferenceBundle,
    events: LocalBehaviorBundle,
    measurement_labels: dict[str, str | None],
    segment_labels: dict[str, str | None],
) -> tuple[dict[str, list[dict[str, Any]]], int]:
    merged = [
        {
            "observation_ref": row.observation_id,
            "frame_ref": row.frame_ref,
            "camera_id": row.camera_id,
            "timestamp": row.timestamp,
        }
        for row in perception.measurements
        if row.status == "MERGED_OR_PARTIAL"
    ]
    fragmented = [
        {"track_ref": row.local_track_id, "missing_timestamps": list(row.missing_timestamps)}
        for row in perception.tracks
        if row.status == "FRAGMENTED"
    ]
    switches: list[dict[str, Any]] = []
    for track in perception.tracks:
        known = [
            identity
            for identity in track.observation_ids
            if measurement_labels[identity] is not None
        ]
        for first, second in zip(known, known[1:], strict=False):
            if measurement_labels[first] != measurement_labels[second]:
                switches.append(
                    {
                        "track_ref": track.local_track_id,
                        "observation_refs": [first, second],
                    }
                )
    confused = []
    for row in inference.association_hypotheses:
        if len(row.segment_ids) != 2 or row.status != "PROVISIONAL":
            continue
        first, second = row.segment_ids
        if (
            segment_labels[first] is not None
            and segment_labels[second] is not None
            and segment_labels[first] != segment_labels[second]
        ):
            confused.append(
                {
                    "hypothesis_ref": row.hypothesis_id,
                    "segment_refs": list(row.segment_ids),
                }
            )

    def behavioral(kinds: set[str]) -> list[dict[str, Any]]:
        return [
            {
                "event_ref": row.event_id,
                "kind": row.kind,
                "time_range": list(row.time_range),
                "frame_refs": [frame.frame_ref for frame in row.source_frames],
            }
            for row in events.events
            if row.kind in kinds
        ][:5]

    return {
        "pixel_merges": merged[:5],
        "fragmentation": fragmented[:5],
        "ID_switches": switches[:8],
        "appearance_confusion": confused[:5],
        "door_approach_vs_crossing": behavioral({"ENTER_DOOR", "EXIT_DOOR"}),
        "corner_turnback": behavioral({"TURN_CORNER", "LOST_NEAR_CORNER"}),
        "dwell_vs_possible_loitering": behavioral({"DWELL", "POSSIBLE_LOITERING"}),
    }, len(confused)


def rebuild_taxonomy(
    source_root: Path,
    baseline_root: Path,
    output: Path,
    receipt: Path,
) -> dict[str, Any]:
    """Reproduce the original taxonomy without modifying historical inference or truth."""
    states = {}
    # Validate every source freeze and replay before either split's truth is opened.
    for split in ("development", "test"):
        source = source_root / split / "checkpoints/final"
        replay = baseline_root / split
        package, _, _, manifest = _load(source)
        if package.split != split:
            raise ValueError("taxonomy source split binding mismatch")
        old_pixel, old_inference, old_events, freeze = frozen_mode(source, "photos_only", manifest)
        pixel = PerceptionResult.model_validate_json(
            (replay / "perception_photos_only.json").read_bytes()
        )
        inference = InferenceBundle.model_validate_json(
            (replay / "inference_photos_only.json").read_bytes()
        )
        events = LocalBehaviorBundle.model_validate_json(
            (replay / "events_photos_only.json").read_bytes()
        )
        summary = json.loads((replay / "evaluation_photos_only.json").read_bytes())
        replay_receipt = json.loads((replay / "baseline_receipt.json").read_bytes())
        mode_receipt = replay_receipt["modes"]["photos_only"]
        if (
            pixel != old_pixel
            or inference != old_inference
            or events != old_events
            or not freeze.verify(freeze.binding, inference, pixel.model_dump(mode="json"))
            or digest(summary) != mode_receipt["evaluation_sha256"]
            or summary["inference_sha256"] != freeze.inference_sha256
            or summary["freeze_sha256"] != freeze.receipt_sha256
            or summary["dataset_sha256"] != package.dataset_sha256
            or summary["run_id"] != package.run_id
            or summary["model_id"] != package.model_id
            or summary["split"] != split
            or replay_receipt["source_manifest_sha256"] != digest(manifest)
            or mode_receipt["inference_sha256"] != freeze.inference_sha256
            or mode_receipt["pixel_sha256"] != digest(pixel)
            or mode_receipt["events_sha256"] != digest(events)
        ):
            raise ValueError("taxonomy frozen replay/evaluation receipt mismatch")
        states[split] = (package, manifest, pixel, inference, events, freeze, summary)
    detailed: dict[str, Any] = {
        "schema_version": "accuracy.error-taxonomy.v1",
        "version": "v2-baseline",
        "scope": "E1_FOUR_CAMERA_FROZEN_SOURCE",
        "formal_acceptance": False,
        "splits": {},
    }
    for split, state in states.items():
        package, manifest, pixel, inference, events, freeze, summary = state
        truth_bytes = package.simulation_export_path.read_bytes()
        from hashlib import sha256

        truth = ResearchTruth.model_validate_json(truth_bytes)
        expected_frames = {
            frame.media_ref: (frame.camera_id, frame.timestamp) for frame in package.frames
        }
        if (
            truth.boundary != "EVALUATION_DEBUG_ONLY"
            or truth.split != split
            or truth.model_id != package.model_id
            or truth.run_id != package.run_id
            or truth.dataset_sha256 != package.dataset_sha256
            or truth.config_sha256 != package.config_sha256
            or summary["evaluation_truth_sha256"] != sha256(truth_bytes).hexdigest()
            or len(truth.ground_truth) != len(expected_frames)
            or {row.frame_ref: (row.camera_id, row.timestamp) for row in truth.ground_truth}
            != expected_frames
        ):
            raise ValueError("taxonomy truth source/dataset/config binding mismatch")
        measurement_labels, segment_labels, pixels, _ = _labels(pixel, inference, truth)
        if pixels != summary["pixels_and_local_identity"]:
            raise ValueError("taxonomy bounded pixel labels differ from frozen baseline evaluation")
        examples, confused_count = _examples(
            pixel, inference, events, measurement_labels, segment_labels
        )
        multiplicity: Counter[str] = Counter()
        for track in pixel.tracks:
            known = {
                measurement_labels[identity]
                for identity in track.observation_ids
                if measurement_labels[identity] is not None
            }
            multiplicity.update(identity for identity in known if identity is not None)
        detailed["splits"][split] = {
            "source_manifest_sha256": digest(manifest),
            "source_freeze_sha256": freeze.receipt_sha256,
            "dataset_sha256": package.dataset_sha256,
            "inference_sha256": freeze.inference_sha256,
            "counts": {
                "pixel_merged_or_partial": sum(
                    row.status == "MERGED_OR_PARTIAL" for row in pixel.measurements
                ),
                "fragmented_tracks": sum(row.status == "FRAGMENTED" for row in pixel.tracks),
                "ID_switches": pixels["within_local_track_id_switches"],
                "wrong_known_provisional_pairs": confused_count,
            },
            "pixels": pixels,
            "space_time_prior": summary["fixed_pool_feature_ablations"],
            "visible_behavior": summary["behavior"]["groups"]["visible_supported"],
            "scoped_examples": examples,
            "fragmentation_evaluation_only": {
                "known_actor_track_multiplicity": dict(Counter(multiplicity.values())),
                "condition": "Produced bounded-labeled tracks; mixed tracks counted for each "
                "known identity, not full actor recall",
            },
        }
    curated = {
        **detailed,
        "splits": {
            split: {key: value for key, value in row.items() if key != "scoped_examples"}
            for split, row in detailed["splits"].items()
        },
    }
    # The shared immutable writer rejects conflicts and leaves identical files untouched.
    _save(output, detailed)
    _save(receipt, curated)
    return curated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    result = rebuild_taxonomy(args.source_root, args.baseline_root, args.output, args.receipt)
    print(json.dumps({"schema_version": result["schema_version"], "reproduced": True}))


if __name__ == "__main__":
    main()
