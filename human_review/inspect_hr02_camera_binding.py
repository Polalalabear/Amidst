"""GT-free source-ray evidence for HR02; no decisions or inference are applied.

Run in the unchanged source Blender scene. Public projected points and the
already displayed GAP candidate are hypotheses, not original source 3D truth.
The existing viewport raycaster and forward projector are reused verbatim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"
REVIEW_SHA = "e105c3116ebec64e94667f2f863bb0868f4fc34eeeedf1ced0a0b1a931ee1463"
SCALE = 0.0247
OFFICE = "data/finalization/local_run/dataset/inference/office/"
PUBLIC = "data/finalization/local_run/diagnostics/office/policy_graph_primary/"
ALLOWLIST = frozenset(
    {
        "human_review/review_template.json",
        "human_review/geometry_evidence.json",
        "human_review/frames/motion_context/motion_manifest.json",
        "data/scene_audit/school_v3_semantic_audit.json",
        "configs/architectural_scale_school_v3.json",
        OFFICE + "context.json",
        OFFICE + "observations.json",
        OFFICE + "visibility.json",
        PUBLIC + "projected_frames.json",
    }
)
CAMERA_IDS = ("CAM_1F_AUDITORIUM_FRONT", "CAM_1F_AUDITORIUM_REAR")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def public_path(relative: str, repo_root: Path = ROOT) -> Path:
    root = repo_root.resolve()
    logical = root / relative
    if (
        relative not in ALLOWLIST
        or Path(relative).is_absolute()
        or logical.resolve() != logical
        or not logical.resolve().is_relative_to(root)
    ):
        raise ValueError("HR02 audit reads only its explicit non-symlink public allowlist")
    return logical


def read_public(relative: str, repo_root: Path = ROOT) -> Any:
    return json.loads(public_path(relative, repo_root).read_bytes())


def annotation_membership(
    point: list[float],
    boxes: list[dict[str, Any]],
    scale: float = SCALE,
) -> dict[str, Any]:
    if len(point) != 3 or not all(math.isfinite(p) for p in point):
        raise ValueError("finite three-dimensional camera point required")
    rows = []
    for box in boxes:
        low, high = box["bounds_min"], box["bounds_max"]
        if (
            len(low) != 3
            or len(high) != 3
            or not all(math.isfinite(p) for p in (*low, *high))
            or any(a > b for a, b in zip(low, high, strict=True))
        ):
            raise ValueError("ordered three-dimensional annotation bounds required")
        distance = math.hypot(
            *[max(a - p, 0, p - b) for p, a, b in zip(point, low, high, strict=True)]
        )
        rows.append(
            {
                "object_id": box["object_id"],
                "contains": distance == 0,
                "nearest_distance_bu": distance,
                "nearest_distance_m": distance * scale,
            }
        )
    return {
        "contains": sorted(row["object_id"] for row in rows if row["contains"]),
        "bounds_comparison": rows,
        "ownership_authority": "NOT_CERTIFIED",
    }


def _index(rows: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
    indexed = {(row["frame_id"], row["camera_id"]): row for row in rows}
    expected = {(i, c) for i in range(50) for c in CAMERA_IDS}
    if len(rows) != 100 or set(indexed) != expected:
        raise ValueError("exactly the frozen 50 timestamps and two cameras are required")
    if any(row["timestamp"] != i / 5 for (i, _), row in indexed.items()):
        raise ValueError("public timestamps changed")
    return indexed


def build_public_frames(
    context: dict[str, Any],
    observations: dict[str, Any],
    visibility: list[dict[str, Any]],
    projected: dict[str, Any],
    motion: dict[str, Any],
) -> list[dict[str, Any]]:
    if (
        context["source_asset_sha256"] != SOURCE_SHA
        or observations["source_asset_sha256"] != SOURCE_SHA
        or motion["source_sha256"] != SOURCE_SHA
        or tuple(sorted(c["camera_id"] for c in context["cameras"])) != CAMERA_IDS
        or context["plane"]["zone_id"] != "AREA_1F_OFFICE"
        or any(
            motion.get(k) is not False
            for k in (
                "gt_used",
                "evaluation_files_read",
                "simulation_recipe_read",
                "physical_authority_changed",
                "formal_execution_enabled",
                "new_route_generated",
            )
        )
        or len(motion["frames"]) != 50
    ):
        raise ValueError("unchanged source, public cameras and diagnostic motion required")
    obs, vis = _index(observations["frames"]), _index(visibility)
    proj = _index(projected["dataset"]["samples"])
    frames = []
    for i, old in enumerate(motion["frames"]):
        if old["frame_id"] != i or old["timestamp"] != i / 5:
            raise ValueError("frozen motion ordering/timestamps changed")
        records, points = [], []
        old_records = {row["camera_id"]: row for row in old["camera_evidence"]}
        if set(old_records) != set(CAMERA_IDS):
            raise ValueError("motion camera evidence changed")
        for c in CAMERA_IDS:
            a, b, p, m = obs[i, c], vis[i, c], proj[i, c], old_records[c]
            if (
                a["status"] not in {"OBSERVED", "GAP"}
                or a["status"] != b["status"]
                or a["status"] != p["visibility"]
                or a["status"] != m["visibility"]
                or a["point_2d"] != p["uv"]
                or a["point_2d"] != m["uv"]
                or a["gap_reason"] != p["gap_reason"]
                or a["gap_reason"] != m["gap_reason"]
                or a["occluder_id"] != b["occluder_id"]
                or a["occluder_id"] != p["occluder_id"]
                or a["occluder_id"] != m["occluder_id"]
                or b["reason"] != ("CLEAR" if a["status"] == "OBSERVED" else a["gap_reason"])
                or p["source_asset_sha256"] != SOURCE_SHA
            ):
                raise ValueError("recorded public observations/visibility/projection/motion differ")
            point = p["projected_point"]
            if (a["status"] == "OBSERVED") != (point is not None):
                raise ValueError("projected points require actual public observations")
            if point is not None:
                if point["timestamp"] != i / 5 or point["camera_id"] != c:
                    raise ValueError("projected point identity changed")
                points.append(point["world_position"])
            records.append(
                {
                    "camera_id": c,
                    "status": a["status"],
                    "uv": a["point_2d"],
                    "gap_reason": a["gap_reason"],
                    "occluder_id": a["occluder_id"],
                }
            )
        if len(points) > 1:
            raise ValueError("audit cannot select a new camera pair/hypothesis")
        state = "OBSERVED" if points else "INFERRED_GAP"
        if old["state"] != state:
            raise ValueError("display state differs from frozen public trace")
        landmark = points[0] if points else old["landmark_position_bu"]
        if (
            len(landmark) != 3
            or not all(math.isfinite(p) for p in landmark)
            or math.dist(landmark, old["landmark_position_bu"]) > 0.001
            or math.dist(landmark[:2], old["body_base_bu"][:2]) > 0.001
        ):
            raise ValueError("frozen render point changed beyond existing float32 guard")
        frames.append(
            {
                "frame_id": i,
                "timestamp": i / 5,
                "role": old["role"],
                "landmark_position_bu": list(landmark),
                "foot_position_bu": old["body_base_bu"],
                "old_motion_path": f"../motion_context/motion_{i:03d}.png",
                "public_records": records,
                "position_basis": "EXACT_PUBLIC_PROJECTED_POINT"
                if points
                else "EXISTING_FROZEN_DIRECT_CANDIDATE_NOT_ORIGINAL_SOURCE_POSITION",
            }
        )
    return frames


def _hit_details(raycaster: Any, origin: list[float], target: list[float], name: str) -> Any:
    """Explain an existing raycaster result; do not replace its visibility decision."""
    from mathutils import Vector  # type: ignore[import-not-found]

    distance = math.dist(origin, target)
    direction = [(b - a) / distance for a, b in zip(origin, target, strict=True)]
    found: list[dict[str, Any]] = []
    for mesh in raycaster._meshes:
        if mesh.object_name != name or mesh.inverse is None:
            continue
        local_origin = mesh.inverse @ Vector(origin)
        local_direction = mesh.inverse.to_3x3() @ Vector(direction)
        local_per_world = local_direction.length
        local_direction /= local_per_world
        hit, location, _normal, face = mesh.obj.ray_cast(
            local_origin,
            local_direction,
            distance=(distance + mesh.padding + raycaster.endpoint_tolerance_m) * local_per_world,
            depsgraph=raycaster._depsgraph,
        )
        if not hit:
            continue
        world = [
            sum(float(mesh.matrix[r][k]) * float(location[k]) for k in range(3))
            + float(mesh.matrix[r][3])
            for r in range(3)
        ]
        along = sum((world[k] - origin[k]) * direction[k] for k in range(3))
        if along >= distance - raycaster.endpoint_tolerance_m:
            continue
        vertices = []
        for index in mesh.obj.data.polygons[face].vertices:
            v = mesh.obj.data.vertices[index].co
            vertices.append(
                [
                    sum(float(mesh.matrix[r][k]) * float(v[k]) for k in range(3))
                    + float(mesh.matrix[r][3])
                    for r in range(3)
                ]
            )
        found.append(
            {
                "object_id": name,
                "evaluated_face_index": int(face),
                "face_id_authority": (
                    "EVALUATED_VIEWPORT_POLYGON_NOT_AUTOMATIC_ORIGINAL_FACE_BINDING"
                ),
                "position_bu": world,
                "distance_bu": along,
                "distance_m": along * SCALE,
                "face_vertices_bu": vertices,
            }
        )
    return min(found, key=lambda row: row["distance_bu"]) if found else None


def main() -> None:
    import bpy  # type: ignore[import-not-found]
    from mathutils import Matrix

    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "scripts"))
    from export_blender_pilot import annotation_objects, project  # type: ignore[import-not-found]

    from amidst.simulation.blender_camera import extract_camera_dict
    from amidst.simulation.blender_visibility import BlenderMeshRaycaster

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "human_review/frames/hr02_camera_audit"
    )
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    producer_sha = digest(Path(__file__).resolve())
    out = args.output.resolve()
    if (out / "audit_data.json").exists() or (out / "manifest.json").exists():
        raise FileExistsError("fresh audit evidence output required")
    out.mkdir(parents=True, exist_ok=True)
    template = read_public("human_review/review_template.json")
    protected = {p: digest(public_path(p)) for p in ALLOWLIST}
    for row in template["metadata"]["input_hashes"]:
        path = ROOT / row["path"]
        if any(s in row["path"] for s in ("evaluation/", "simulation/", "ground_truth")):
            raise ValueError("frozen review inputs must remain GT-free")
        if digest(path) != row["sha256"]:
            raise ValueError("frozen review input changed: " + row["path"])
        protected[row["path"]] = row["sha256"]
    if template["review_payload_sha256"] != REVIEW_SHA:
        raise ValueError("review identity changed")
    context = read_public(OFFICE + "context.json")
    observations = read_public(OFFICE + "observations.json")
    motion = read_public("human_review/frames/motion_context/motion_manifest.json")
    frames = build_public_frames(
        context,
        observations,
        read_public(OFFICE + "visibility.json"),
        read_public(PUBLIC + "projected_frames.json"),
        motion,
    )
    if digest(public_path(OFFICE + "observations.json")) != context["observations_sha256"]:
        raise ValueError("public observations/context identity changed")
    audit = read_public("data/scene_audit/school_v3_semantic_audit.json")
    geometry = read_public("human_review/geometry_evidence.json")
    floor_z = geometry["prospective_footpoint_bounds_bu"][0][2]
    if any(frame["foot_position_bu"][2] != floor_z for frame in frames):
        raise ValueError("display feet differ from the frozen proposed support floor")
    scale = read_public("configs/architectural_scale_school_v3.json")
    # Read exact source fingerprint before any scene-dependent queries.
    source = Path(bpy.data.filepath).resolve()
    before = (digest(source), source.stat().st_size, source.stat().st_mtime_ns)
    if (
        before[0] != SOURCE_SHA
        or scale.get("metres_per_blender_unit") != SCALE
        or scale.get("authority") != "APPROVED"
    ):
        raise ValueError("exact source and approved scale required")
    scene = bpy.context.scene
    if scene.name != audit["scene"]["name"]:
        raise ValueError("source scene identity changed")
    scene.frame_set(audit["scene"]["frame"], subframe=audit["scene"]["subframe"])
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.use_border = scene.render.use_crop_to_border = False
    boxes = [
        {
            "object_id": row["object"],
            "bounds_min": row["bounding_box"]["minimum"],
            "bounds_max": row["bounding_box"]["maximum"],
        }
        for row in audit["objects"]
        if row["object"].startswith("AREA_")
    ]
    cameras = []
    for old in sorted(context["cameras"], key=lambda row: row["camera_id"]):
        native = extract_camera_dict(scene, bpy.data.objects[old["camera_id"]])
        if native != old:
            raise ValueError("source normalized calibration differs: " + old["camera_id"])
        position = [old["camera_to_world"][i][3] for i in range(3)]
        membership = annotation_membership(position, boxes)
        office = next(
            r for r in membership["bounds_comparison"] if r["object_id"] == "AREA_1F_OFFICE"
        )
        cameras.append(
            {
                "camera_id": old["camera_id"],
                "calibration": old,
                "position_bu": position,
                "position_m": [p * SCALE for p in position],
                "calibration_identical": True,
                "office_aabb_contains_camera": office["contains"],
                "office_aabb_distance_m": office["nearest_distance_m"],
                "annotation_containments": membership["contains"],
                "ownership_authority": "NOT_CERTIFIED",
            }
        )
    raycaster = BlenderMeshRaycaster(scene, excluded_objects=annotation_objects(bpy, scene))
    mismatches, shifts = [], []
    for frame in frames:
        rows = []
        for camera, recorded in zip(cameras, frame.pop("public_records"), strict=True):
            calibration, origin = camera["calibration"], camera["position_bu"]
            replays = {}
            for label, target in (
                ("landmark", frame["landmark_position_bu"]),
                ("foot", frame["foot_position_bu"]),
            ):
                projected = project(calibration, target, Matrix)
                ray = raycaster(tuple(origin), tuple(target))
                hit = (
                    _hit_details(raycaster, origin, target, ray.occluder_id)
                    if ray.occluder_id
                    else None
                )
                replays[label] = {
                    "pixel": projected["pixel"],
                    "axial_depth_bu": projected["axial_depth"],
                    "in_frustum": projected["reason"] == "IN_FRUSTUM",
                    "fov_reason": projected["reason"],
                    "ray_reason": ray.reason,
                    "occluder_id": ray.occluder_id,
                    "hit": hit,
                    "authority": "SOURCE_RAY_TO_PUBLIC_PROJECTION_OR_CANDIDATE_NOT_ORIGINAL_3D",
                }
            if recorded["status"] == "OBSERVED":
                shifts.append(math.dist(recorded["uv"], replays["foot"]["pixel"]))
                if replays["landmark"]["ray_reason"] != "CLEAR":
                    mismatches.append(
                        {
                            "frame_id": frame["frame_id"],
                            "camera_id": camera["camera_id"],
                            "recorded": "OBSERVED",
                            "replay": replays["landmark"]["ray_reason"],
                        }
                    )
            rows.append(
                {
                    "camera_id": camera["camera_id"],
                    "public_record": recorded,
                    "landmark_replay": replays["landmark"],
                    "foot_replay": replays["foot"],
                }
            )
        frame["cameras"] = rows
        print("HR02 source rays", frame["frame_id"], flush=True)
    landmark_z = context["plane"]["point"][2]
    data = {
        "schema_version": "phase1-hr02-camera-binding-audit-v1",
        "result_type": "DIAGNOSTIC",
        "source_sha256": SOURCE_SHA,
        "review_payload_sha256": REVIEW_SHA,
        "gt_used": False,
        "evaluation_files_read": False,
        "simulation_recipe_read": False,
        "physical_authority_changed": False,
        "formal_execution_enabled": False,
        "human_decisions_applied": False,
        "source_saved": False,
        "source_modified": False,
        "source_scene": audit["scene"],
        "cameras": cameras,
        "annotation_boxes": boxes,
        "frames": frames,
        "images": {},
        "binding": {
            "floor_z_bu": floor_z,
            "landmark_z_bu": landmark_z,
            "offset_bu": landmark_z - floor_z,
            "offset_m": (landmark_z - floor_z) * SCALE,
            "body_height_m": 1.7,
            "body_radius_m": 0.3,
            "clearance_m": 0.05,
            "authority": "PENDING_HR02",
        },
        "diagnostic_protocol": {
            "scale_m_per_bu": SCALE,
            "sampling_hz": 5,
            "timestamps": 50,
            "sourcegeometryscope": "FULL_EVALUATED_VIEWPORT_ALLOWED_MESH",
            "ray_endpoint_tolerance_bu": raycaster.endpoint_tolerance_m,
            "ray_endpoint_tolerance_m": raycaster.endpoint_tolerance_m * SCALE,
            "numeric_policy": "EXISTING_RAYCASTER_NATIVE_BU_UNCHANGED",
            "annotation_meshes_excluded": True,
            "hide_render_materials_do_not_remove_blockers": True,
            "raycast_mesh_instances": len(raycaster._meshes),
            "gap_position_basis": "FROZEN_DIRECT_CANDIDATE_NOT_ORIGINAL_GAP_POSITION",
        },
        "summary": {
            "recorded_counts": dict(
                Counter(r["public_record"]["status"] for f in frames for r in f["cameras"])
            ),
            "replay_counts": dict(
                Counter(r["landmark_replay"]["ray_reason"] for f in frames for r in f["cameras"])
            ),
            "observed_replay_mismatches": mismatches,
            "foot_replay_counts": dict(
                Counter(r["foot_replay"]["ray_reason"] for f in frames for r in f["cameras"])
            ),
            "landmark_clear_foot_occluded": [
                {"frame_id": f["frame_id"], "camera_id": r["camera_id"]}
                for f in frames
                for r in f["cameras"]
                if r["landmark_replay"]["ray_reason"] == "CLEAR"
                and r["foot_replay"]["ray_reason"] == "OCCLUDED"
            ],
            "foot_uv_shift_range_px": [min(shifts), max(shifts)],
            "original_source_point_available": False,
            "all_display_landmarks_in_both_camera_frusta": all(
                r["landmark_replay"]["in_frustum"] for f in frames for r in f["cameras"]
            ),
            "room_ownership": "NOT_CERTIFIED",
            "suggested_review_state": "KEEP_REVIEW",
            "decision_written": False,
        },
        "limitations": [
            "Public pixels and fixed-plane points do not provide original 3D source truth.",
            "Annotation containment is not room ownership or visibility-domain certification.",
            "Only the displayed landmark/foot hypotheses are raycast; no GT trajectory is read.",
            "GAP candidate visibility does not identify the original hidden person's position.",
            "Single-view fallback/LOW_CONFIDENCE follow the existing protocol; "
            "not new human choices.",
        ],
    }
    if before != (digest(source), source.stat().st_size, source.stat().st_mtime_ns):
        raise RuntimeError("source changed during read-only audit")
    if any(digest(ROOT / p) != h for p, h in protected.items()):
        raise RuntimeError("frozen public review inputs changed")
    if digest(Path(__file__).resolve()) != producer_sha:
        raise RuntimeError("producer changed during audit; require a fresh run")
    data_path = out / "audit_data.json"
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    receipt = {
        k: data[k]
        for k in (
            "schema_version",
            "result_type",
            "source_sha256",
            "review_payload_sha256",
            "gt_used",
            "evaluation_files_read",
            "simulation_recipe_read",
            "physical_authority_changed",
            "formal_execution_enabled",
            "human_decisions_applied",
            "source_saved",
            "source_modified",
        )
    }
    receipt.update(
        {
            "data": {"path": data_path.name, "sha256": digest(data_path)},
            "inputs": [{"path": p, "sha256": h} for p, h in sorted(protected.items())],
            "builder_sha256": producer_sha,
            "source_preserved": True,
        }
    )
    (out / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(data["summary"]), flush=True)


if __name__ == "__main__":
    main()
