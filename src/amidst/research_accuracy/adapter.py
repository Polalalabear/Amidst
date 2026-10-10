"""Frozen v2 artifacts adapted to existing scoped tools, without shared UI changes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from amidst.engineering.access import Mode, SessionGuard
from amidst.engineering.local_association import resource_scope
from amidst.engineering.local_pilot import _load, _media_root
from amidst.engineering.local_service import LocalPilotService
from amidst.engineering.registry import RegistryStore, opaque_ref, scope_parts
from amidst.research_accuracy.behavior import event_support_state
from amidst.research_accuracy.run import Variant, frozen, load


def load_service(
    output: Path,
    *,
    variant: Variant = "end_to_end",
    mode: Mode = "photos_only",
    input_stage: bool = False,
) -> LocalPilotService:
    package, registry, manifest, _ = load(output)
    state = frozen(output, variant, mode, manifest, package, registry)
    source = Path(manifest["source_locator"])
    _, _, topology, original = _load(source)
    scope = resource_scope(package.scope)
    guard = SessionGuard(state.receipt.binding)
    if not input_stage:
        guard.freeze(state.receipt, state.inference, state.perception.model_dump(mode="json"))
    cameras = {c.camera_id: c.camera_ref for c in registry.cameras}
    links = original["frame_links"]
    pixels = {p.observation_id: p for p in state.perception.measurements}
    projections = {p.observation_id: p for p in state.inference.projected_measurements}
    prefix = (
        manifest["experiment_id"],
        variant,
        mode,
        state.receipt.binding.config_sha256,
        *scope_parts(scope),
    )
    observations = []
    for mapping in state.inference.local_record_maps:
        rows = [pixels[p] for p in mapping.original_pixel_observation_ids]
        observations.append(
            {
                "observation_ref": opaque_ref("observation", *prefix, mapping.segment_id),
                "local_track_ref": opaque_ref("track", *prefix, mapping.local_track_id),
                "camera_refs": [cameras[rows[0].camera_id]],
                "camera_ids": [rows[0].camera_id],
                "time_range": [rows[0].timestamp, rows[-1].timestamp],
                "media_refs": [links[p.frame_ref] for p in rows],
                "region_ids": list(
                    dict.fromkeys(r for p in rows for r in projections[p.observation_id].region_ids)
                ),
                "measurements": [
                    {
                        "frame_ref": links[p.frame_ref],
                        "timestamp": p.timestamp,
                        "bbox": p.bbox_xyxy,
                        "point_2d": p.contact_pixel,
                        "visible_features": p.appearance,
                    }
                    for p in rows
                ],
                "projected_path": [
                    point.world_position
                    for p in rows
                    if (point := projections[p.observation_id].point) is not None
                ],
                "origin": "SYNTHETIC",
                "image_measurement": True,
                "authority": "RGB_PIXELS_WITH_SYNTHETIC_CONFIG",
                "uncertainty": "Local camera identities remain provisional; no global ID solver.",
            }
        )
    events: list[dict[str, Any]] = []
    for event in state.events.events:
        row = event.model_dump(mode="json")
        for key in ("scope", "local_track_ids", "segment_ids"):
            row.pop(key)
        row.update(
            {
                "experiment_id": manifest["experiment_id"],
                "variant": variant,
                "support_state": event_support_state(event),
                "local_track_refs": [
                    opaque_ref("track", *prefix, t) for t in event.local_track_ids
                ],
                "segment_refs": [opaque_ref("segment", *prefix, s) for s in event.segment_ids],
                "event_ref": opaque_ref("event", *prefix, event.event_id),
                "camera_ids": list(dict.fromkeys(f.camera_id for f in event.source_frames)),
                "media_refs": [links[f.frame_ref] for f in event.source_frames],
                "source_frames": [
                    {
                        "frame_ref": links[f.frame_ref],
                        "camera_id": f.camera_id,
                        "timestamp": f.timestamp,
                        "evidence_state": "PROJECTED",
                    }
                    for f in event.source_frames
                ],
                "association_refs": [
                    opaque_ref("association", *prefix, a) for a in event.association_refs
                ],
                "association_states": [
                    {
                        "association_ref": opaque_ref("association", *prefix, a.hypothesis_id),
                        "kind": a.kind,
                        "status": a.status,
                        "reason": a.reason,
                    }
                    for a in event.association_states
                ],
            }
        )
        row["detail_ref"] = row["replay_ref"] = row["event_ref"]
        row["camera_refs"] = [cameras[c] for c in row["camera_ids"]]
        events.append(row)
    return LocalPilotService(
        RegistryStore(registry, _media_root(source, original)),
        scope,
        guard,
        tuple(observations),
        tuple(events),
        topology,
    )


def adapter_contract(output: Path) -> dict[str, Any]:
    _, _, manifest, _ = load(output)
    return {
        "schema_version": "accuracy.adapter.v2",
        "experiment_id": manifest["experiment_id"],
        "config_sha256": manifest["config_sha256"],
        "source_run_id": manifest["source_run_id"],
        "frozen_artifact_reads_only": True,
        "factory": "amidst.research_accuracy.adapter.load_service",
        "explicit_support_states": ["SUPPORTED", "UNKNOWN", "GAP_ALTERNATIVES"],
        "scores_are_probabilities": False,
        "formal_phase1_acceptance": False,
        "read_modes": ["photos_only", "photos_plus_observations"],
        "runtime_evaluation_payload": False,
        "event_refs_bound_to_experiment_variant": True,
    }


if __name__ == "__main__":
    import sys

    print(json.dumps(adapter_contract(Path(sys.argv[1])), indent=2))
