"""Plan distinct, source-bound PILOT locales without saving the Blender scene.

Cached point-grid data supplies search hints only. Every exported route is
revalidated against the current evaluated physical triangles and actual
triangulated WALKABLE annotation, including the full continuous marker envelope.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import sys
from pathlib import Path

ANNOTATION_COLLECTIONS = (
    "Areas",
    "WALKABLE_AREAS",
    "OBSTACLE_AREAS",
    "STAIR_ANNOTATIONS",
    "Stair Reference Surfaces",
    "WALL_ANNOTATIONS",
)
ANNOTATION_PREFIXES = (
    "AREA_", "PORTAL_", "WALK_", "WALKABLE_", "OBSTACLE_", "STAIR_", "WALL_"
)
SITES = (
    {
        "site_id": "classroom101",
        "site_label": "1F CLASS101 classroom",
        "walkable": "WALK_1F_CLASS101",
        "area_id": "AREA_1F_CLASS101",
        "camera_ids": ["CAM_1F_CLASS101", "CAM_1F_CORRIDOR_04"],
    },
    {
        "site_id": "auditorium",
        "site_label": "1F auditorium",
        "walkable": "WALK_1F_AUDITORIUM",
        "area_id": "AREA_1F_AUDITORIUM",
        "camera_ids": ["CAM_1F_AUDITORIUM_FRONT", "CAM_1F_AUDITORIUM_REAR"],
    },
    {
        "site_id": "office",
        "site_label": "1F office",
        "walkable": "WALK_1F_OFFICE",
        "area_id": "AREA_1F_OFFICE",
        "camera_ids": ["CAM_1F_AUDITORIUM_FRONT", "CAM_1F_AUDITORIUM_REAR"],
    },
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument(
        "--search-hints", type=Path, default=Path("/private/tmp/amidst-pilot-search.json")
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--site", action="append", choices=[site["site_id"] for site in SITES],
        help="Plan only this existing locale; repeat to select more than one (default: all)",
    )
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])


def bounds(points):
    return tuple(min(p[a] for p in points) for a in range(3)), tuple(
        max(p[a] for p in points) for a in range(3)
    )


def overlaps(first, second):
    return all(first[1][a] >= second[0][a] and second[1][a] >= first[0][a] for a in range(3))


def verify_immutable_source(path, expected_sha256, expected_size, expected_mtime_ns):
    """Check source identity separately from mutable geometry/raycast variables."""
    asset = Path(path)
    stat = asset.stat()
    if (
        hashlib.sha256(asset.read_bytes()).hexdigest() != expected_sha256
        or stat.st_size != expected_size
        or stat.st_mtime_ns != expected_mtime_ns
    ):
        raise RuntimeError(f"Immutable Blender source changed during planning: {asset}")


def candidates(rows, camera_ids):
    """Rank hint segments, retaining all collision decisions for live geometry."""
    routes = []
    for axis in (0, 1):
        groups = collections.defaultdict(list)
        for row in rows:
            groups[row["position"][1 - axis]].append(row)
        for line in groups.values():
            line.sort(key=lambda row: row["position"][axis])
            for start in range(len(line)):
                for stop in range(start + 2, len(line)):
                    subset = line[start : stop + 1]
                    if any(
                        abs(b["position"][axis] - a["position"][axis] - 20.0) > 0.01
                        for a, b in zip(subset, subset[1:], strict=False)
                    ):
                        continue
                    observed = [
                        any(r["states"][c]["status"] == "visible" for c in camera_ids)
                        for r in subset
                    ]
                    if not observed[0] or not observed[-1]:
                        continue
                    gap_count = observed.count(False)
                    if gap_count and any(
                        observed[
                            min(i for i, v in enumerate(observed) if not v) : max(
                                i for i, v in enumerate(observed) if not v
                            )
                            + 1
                        ]
                    ):
                        continue
                    length = abs(subset[-1]["position"][axis] - subset[0]["position"][axis])
                    active = sum(
                        any(r["states"][c]["status"] == "visible" for r in subset)
                        for c in camera_ids
                    )
                    role = "VISIBLE_GAP_VISIBLE" if gap_count else "FULLY_OBSERVED_CONTROL"
                    # Occlusion demonstration first; prefer both cameras and enough movement.
                    score = (bool(gap_count), active, min(gap_count, 10), length)
                    routes.append((score, subset[0]["position"], subset[-1]["position"], role))
    routes.sort(key=lambda row: row[0], reverse=True)
    return routes


def main():
    import bpy
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    repository = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository / "src"))
    sys.path.insert(0, str(repository / "scripts"))
    from plan_blender_pilot import point_in_xy_triangle, triangle_intersects_box

    from amidst.simulation.blender_camera import extract_camera_dict

    args = parse_args()
    source = Path(bpy.data.filepath).resolve()
    source_stat = source.stat()
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    hints = json.loads(args.search_hints.read_text())
    scene, depsgraph = bpy.context.scene, bpy.context.evaluated_depsgraph_get()
    source_lineage = None
    origin_path = scene.get("phase1_wall_marking_source_path")
    origin_digest = scene.get("phase1_wall_marking_source_sha256")
    if origin_path or origin_digest:
        if not origin_path or not origin_digest:
            raise ValueError("Derived scene must bind both original source path and SHA-256")
        lineage_source = Path(origin_path).resolve()
        origin_stat = lineage_source.stat()
        verified_origin_digest = hashlib.sha256(lineage_source.read_bytes()).hexdigest()
        if verified_origin_digest != origin_digest:
            raise ValueError("Derived scene original source SHA-256 differs from live source")
        source_lineage = {
            "original_source_path": str(lineage_source),
            "original_source_sha256": verified_origin_digest,
            "original_source_size": origin_stat.st_size,
            "original_source_mtime_ns": origin_stat.st_mtime_ns,
            "original_source_identity_verified": True,
            "wall_candidate_sidecar_sha256": scene.get(
                "phase1_wall_marking_candidate_sidecar_sha256"
            ),
            "original_physical_geometry_sha256": scene.get(
                "phase1_wall_marking_physical_geometry_sha256"
            ),
            "wall_semantic_marking_count": scene.get("phase1_wall_marking_count"),
            "wall_semantic_marking_policy": "ANNOTATION_ONLY_PHYSICAL_ROLE_NOT_APPROVED",
        }
    radius, height, probe_height, margin = 6.0, 119.0, 55.0, 0.05
    excluded, excluded_names = set(), []
    for name in ANNOTATION_COLLECTIONS:
        collection = bpy.data.collections.get(name)
        if collection:
            excluded.update(obj.original.as_pointer() for obj in collection.all_objects)
            excluded_names.extend(obj.name for obj in collection.all_objects)
    for obj in scene.objects:
        if obj.type == "MESH" and (
            obj.name.startswith(ANNOTATION_PREFIXES) or obj.get("annotation_only")
        ):
            excluded.add(obj.original.as_pointer())
            excluded_names.append(obj.name)

    contexts = []
    selected_sites = [site for site in SITES if not args.site or site["site_id"] in args.site]
    for site in selected_sites:
        walkable = bpy.data.objects[site["walkable"]].evaluated_get(depsgraph)
        mesh = walkable.to_mesh()
        mesh.calc_loop_triangles()
        world = [walkable.matrix_world @ v.co for v in mesh.vertices]
        walk_triangles = [
            tuple(world[i].copy() for i in triangle.vertices) for triangle in mesh.loop_triangles
        ]
        lo, hi = bounds(world)
        walkable.to_mesh_clear()
        annotation_z = lo[2]
        local_bounds = (
            (lo[0] - radius, lo[1] - radius, annotation_z - 10 + margin),
            (hi[0] + radius, hi[1] + radius, annotation_z + height + margin),
        )
        contexts.append(
            {
                "site": site,
                "annotation_z": annotation_z,
                "walk_triangles": walk_triangles,
                "local_bounds": local_bounds,
                "physical_triangles": [],
            }
        )

    vertices, triangles, triangle_objects, physical_objects = [], [], [], set()
    for instance in depsgraph.object_instances:
        obj = instance.object
        if (
            obj.type != "MESH"
            or not instance.show_self
            or obj.original.as_pointer() in excluded
            or (
                instance.parent is not None
                and instance.parent.original.as_pointer() in excluded
            )
        ):
            continue
        matrix = instance.matrix_world.copy()
        object_bounds = bounds([matrix @ Vector(c) for c in obj.bound_box])
        relevant = [
            context for context in contexts if overlaps(object_bounds, context["local_bounds"])
        ]
        mesh = obj.to_mesh()
        mesh.calc_loop_triangles()
        offset = len(vertices)
        world = [matrix @ v.co for v in mesh.vertices]
        vertices.extend(world)
        for triangle in mesh.loop_triangles:
            triangles.append(tuple(offset + i for i in triangle.vertices))
            triangle_objects.append(obj.original.name)
            if relevant:
                points = tuple(world[i] for i in triangle.vertices)
                triangle_bounds = bounds(points)
                for context in relevant:
                    if overlaps(triangle_bounds, context["local_bounds"]):
                        context["physical_triangles"].append(
                            (points, triangle_bounds, obj.original.name, int(triangle.index))
                        )
        physical_objects.add(obj.original.name)
        obj.to_mesh_clear()
    print(f"PHYSICAL_BVH {len(physical_objects)} objects; {len(triangles)} triangles", flush=True)
    bvh = BVHTree.FromPolygons(vertices, triangles, all_triangles=True, epsilon=0)
    results = []

    for context in contexts:
        site = context["site"]
        rows = [row for row in hints["rows"] if row["walkable"] == site["walkable"]]
        route_options = candidates(rows, site["camera_ids"])
        camera_objects = [bpy.data.objects[c] for c in site["camera_ids"]]
        cameras = [extract_camera_dict(scene, c) for c in camera_objects]
        rejected = collections.Counter()
        failures = []
        selected = None
        for candidate_index, (_, start, end, role) in enumerate(route_options):
            annotation_z = context["annotation_z"]
            plane_xy = [(start[a] + end[a]) / 2 for a in (0, 1)]
            plane_hit, plane_normal, plane_triangle, _ = bvh.ray_cast(
                Vector((*plane_xy, annotation_z + 15)), Vector((0, 0, -1)), 30
            )
            if plane_hit is None or abs(plane_normal.z) < 0.95:
                rejected["INVALID_INDEPENDENT_PLANE_SUPPORT"] += 1
                continue
            floor_z = float(plane_hit.z)
            sweep_min = (
                min(start[0], end[0]) - radius,
                min(start[1], end[1]) - radius,
                floor_z + margin,
            )
            sweep_max = (
                max(start[0], end[0]) + radius,
                max(start[1], end[1]) + radius,
                floor_z + margin + height,
            )
            collisions = []
            for points, triangle_bounds, obj_name, triangle_id in context["physical_triangles"]:
                if overlaps(triangle_bounds, (sweep_min, sweep_max)) and triangle_intersects_box(
                    points, sweep_min, sweep_max
                ):
                    collisions.append({"object": obj_name, "triangle": triangle_id})
                    if len(collisions) == 3:
                        break
            if collisions:
                rejected["CONTINUOUS_MARKER_SWEEP_INTERSECTS_PHYSICAL_MESH"] += 1
                if len(failures) < 12:
                    failures.append(
                        {"start": start, "end": end, "role": role, "collision_examples": collisions}
                    )
                continue
            samples, floor_hits = [], []
            failed = False
            for frame_id in range(50):
                t = frame_id / 5
                xy = [start[a] + (end[a] - start[a]) * t / 10 for a in (0, 1)]
                hits = []
                for dx, dy in (
                    (0, 0),
                    (-radius, -radius),
                    (-radius, radius),
                    (radius, -radius),
                    (radius, radius),
                ):
                    px, py = xy[0] + dx, xy[1] + dy
                    if not any(
                        point_in_xy_triangle((px, py), tri) for tri in context["walk_triangles"]
                    ):
                        rejected["FOOTPRINT_LEAVES_TRIANGULATED_WALKABLE"] += 1
                        failed = True
                        break
                    hit, normal, triangle, _ = bvh.ray_cast(
                        Vector((px, py, annotation_z + 15)), Vector((0, 0, -1)), 30
                    )
                    if hit is None or abs(normal.z) < 0.95 or abs(hit.z - floor_z) > 0.01:
                        rejected["MISSING_OR_NONPLANAR_PHYSICAL_SUPPORT"] += 1
                        failed = True
                        break
                    hits.append(
                        {
                            "position": list(hit),
                            "normal": list(normal),
                            "object": triangle_objects[triangle],
                        }
                    )
                if failed:
                    break
                foot = Vector((xy[0], xy[1], float(hits[0]["position"][2]) + margin))
                probe = foot + Vector((0, 0, probe_height))
                states = []
                for camera, calibration in zip(camera_objects, cameras, strict=True):
                    projected = world_to_camera_view(scene, camera, probe)
                    depth = float(projected.z)
                    uv = (
                        float(projected.x) * calibration["width"],
                        (1 - float(projected.y)) * calibration["height"],
                    )
                    status, reason, occluder, hit_position = "visible", "CLEAR", None, None
                    if depth <= 0:
                        status, reason = "out_of_FOV", "BEHIND_CAMERA"
                    elif not calibration["clip_start"] <= depth <= calibration["clip_end"]:
                        status, reason = (
                            "out_of_FOV",
                            "NEAR_CLIPPED" if depth < calibration["clip_start"] else "FAR_CLIPPED",
                        )
                    elif not (
                        0 <= uv[0] < calibration["width"] and 0 <= uv[1] < calibration["height"]
                    ):
                        status, reason = "out_of_FOV", "OUTSIDE_FOV"
                    else:
                        origin = camera.evaluated_get(depsgraph).matrix_world.translation
                        delta = probe - origin
                        hit, _, triangle, _ = bvh.ray_cast(
                            origin, delta.normalized(), delta.length - 0.001
                        )
                        if hit is not None:
                            status, reason = "occluded", "OCCLUDED"
                            occluder, hit_position = triangle_objects[triangle], list(hit)
                    states.append(
                        {
                            "camera_id": camera.name,
                            "status": status,
                            "depth_scene_units": depth,
                            "projected_pixel": list(uv) if status == "visible" else None,
                            "diagnostic_geometric_pixel": list(uv) if depth > 0 else None,
                            "occlusion_reason": reason,
                            "occluder_object": occluder,
                            "occluder_hit_position": hit_position,
                            "provenance": "SIMULATION_PROJECTED" if status == "visible" else None,
                        }
                    )
                samples.append(
                    {
                        "frame_id": frame_id,
                        "timestamp": t,
                        "floor_id": "1F",
                        "trajectory_id": f"PILOT_{site['site_id'].upper()}_001",
                        "position": list(foot),
                        "foot_position": list(foot),
                        "probe_position": list(probe),
                        "global_gap": all(s["status"] != "visible" for s in states),
                        "physical_support": hits,
                        "camera_visibility": states,
                    }
                )
                floor_hits.extend(hits)
            if failed:
                continue
            gaps = [r["frame_id"] for r in samples if r["global_gap"]]
            if role == "VISIBLE_GAP_VISIBLE" and (
                not gaps
                or samples[0]["global_gap"]
                or samples[-1]["global_gap"]
                or gaps != list(range(min(gaps), max(gaps) + 1))
            ):
                rejected["LIVE_VISIBILITY_NOT_CONTIGUOUS_VGV"] += 1
                continue
            if role == "FULLY_OBSERVED_CONTROL" and gaps:
                rejected["LIVE_VISIBILITY_NOT_FULLY_OBSERVED_CONTROL"] += 1
                continue
            selected = {
                "start": start,
                "end": end,
                "role": role,
                "candidate_index": candidate_index,
                "floor_z": floor_z,
                "plane_hit": plane_hit,
                "plane_normal": plane_normal,
                "plane_triangle": plane_triangle,
                "plane_xy": plane_xy,
                "samples": samples,
                "floor_hits": floor_hits,
                "gaps": gaps,
                "sweep_min": sweep_min,
                "sweep_max": sweep_max,
            }
            break
        if selected is None:
            result = {
                "site_id": site["site_id"],
                "available": False,
                "candidate_count": len(route_options),
                "rejections": dict(rejected),
                "failure_examples": failures,
            }
            results.append(result)
            print(f"SITE_UNAVAILABLE {site['site_id']} {result}", flush=True)
            continue
        start, end, role = selected["start"], selected["end"], selected["role"]
        samples, gaps, floor_hits = selected["samples"], selected["gaps"], selected["floor_hits"]
        length = math.dist(start[:2], end[:2])
        representative = (
            [0, min(gaps) - 1, min(gaps), (min(gaps) + max(gaps)) // 2, max(gaps) + 1]
            if gaps
            else [0, 12, 25, 37, 49]
        )
        coverage = {
            c: collections.Counter(
                s["status"]
                for row in samples
                for s in row["camera_visibility"]
                if s["camera_id"] == c
            )
            for c in site["camera_ids"]
        }
        camera_reason = (
            "Existing camera identifiers only; no camera pose or lens modification. "
            "Both auditorium views selected for auditorium/office; classroom view and adjacent "
            "corridor camera selected for classroom. "
            "Cameras with zero visible landmark samples are explicitly retained as "
            "camera-coverage controls."
        )
        plan = {
            "schema_version": "amidst-blender-pilot-plan-v1",
            "data_kind": "PILOT / SYNTHETIC SAMPLE",
            "site_id": site["site_id"],
            "site_label": site["site_label"],
            "sample_role": role,
            "area_id": site["area_id"],
            "source_asset_name": source.name,
            "source_asset_sha256": source_sha,
            "source_asset_size": source_stat.st_size,
            "source_asset_mtime_ns": source_stat.st_mtime_ns,
            "blender_version": bpy.app.version_string,
            "geometry_policy": "EVALUATED_VIEWPORT_TRIANGLE_BVH_EXCLUDING_ANNOTATION_PROXIES",
            "gt_allowed_uses": ["simulation", "export", "evaluation", "debug_visualization"],
            "gt_forbidden_uses": ["Projection inference", "Graph", "ranking", "reconstruction"],
            "formal_benchmark_executed": False,
            "unit_settings": {
                "system": scene.unit_settings.system,
                "scale_length": scene.unit_settings.scale_length,
                "length_unit": scene.unit_settings.length_unit,
            },
            "coordinate_units": "BLENDER_SCENE_UNITS",
            "stored_metres_per_unit_contract": 1.0,
            "physical_scale_authority": (
                "UNVERIFIED: native scene units and unit settings do not attest realistic "
                "architectural scale"
            ),
            "trajectory_id": samples[0]["trajectory_id"],
            "floor_id": "1F",
            "duration_seconds": 10.0,
            "sampling_fps": 5.0,
            "timestamp_count": 50,
            "time_interval": "[0.0,10.0), timestamps 0.0 through 9.8",
            "camera_ids": site["camera_ids"],
            "camera_selection_reason": camera_reason,
            "camera_coverage": coverage,
            "cameras": cameras,
            "probe_height_units": probe_height,
            "observation_plane_z": selected["floor_z"] + margin + probe_height,
            "projection_plane_basis": {
                "mesh_object_id": triangle_objects[selected["plane_triangle"]],
                "physical_floor_z": selected["floor_z"],
                "independent_mesh_probe_xy": selected["plane_xy"],
                "physical_floor_normal": list(selected["plane_normal"]),
                "foot_clearance_units": margin,
                "landmark_offset_units": probe_height,
                "source_asset_sha256": source_sha,
                "purpose": "PILOT_DIAGNOSTIC_ONLY",
            },
            "target": {
                "kind": "SYNTHETIC_CYLINDER_MARKER_NOT_HUMAN_SCALE_ATTESTATION",
                "height_scene_units": height,
                "radius_scene_units": radius,
                "foot_clearance_scene_units": margin,
            },
            "waypoints": [
                {"timestamp": 0.0, "position": samples[0]["foot_position"]},
                {"timestamp": 10.0, "position": [end[0], end[1], samples[0]["foot_position"][2]]},
            ],
            "trajectory_length_scene_units": length,
            "sampled_length_scene_units": math.dist(
                samples[0]["position"], samples[-1]["position"]
            ),
            "speed_scene_units_per_second": length / 10,
            "floor_support_evidence": {
                "walkable_object": site["walkable"],
                "floor_label_authority": "EXISTING_WALKABLE_METADATA_DIAGNOSTIC",
                "annotation_plane_z": context["annotation_z"],
                "physical_floor_z_min": min(h["position"][2] for h in floor_hits),
                "physical_floor_z_max": max(h["position"][2] for h in floor_hits),
                "annotation_minus_physical_floor_scene_units": context["annotation_z"]
                - selected["floor_z"],
                "physical_support_objects": sorted({h["object"] for h in floor_hits}),
                "support_probes_per_timestamp": 5,
                "target_full_sweep_clear": True,
                "swept_aabb_minimum": list(selected["sweep_min"]),
                "swept_aabb_maximum": list(selected["sweep_max"]),
                "sweep_method": (
                    "EXACT_TRIANGLE_CLIPPING_AGAINST_FULL_CONTINUOUS_ROUTE_SWEPT_AABB; "
                    "conservative radius6/height119 marker envelope"
                ),
                "portal_crossings": [],
                "cross_floor_transitions": [],
                "elevator_transitions": [],
            },
            "search_evidence": {
                "hint_source": "Cached point-grid file; geometry never accepted from hints",
                "hint_file_sha256": hashlib.sha256(args.search_hints.read_bytes()).hexdigest(),
                "candidate_count": len(route_options),
                "selected_candidate_index": selected["candidate_index"],
                "rejections_before_selection": dict(rejected),
                "failure_examples": failures,
                "physical_objects": len(physical_objects),
                "physical_triangles": len(triangles),
            },
            "excluded_annotation_collections": list(ANNOTATION_COLLECTIONS),
            "excluded_annotation_prefixes": list(ANNOTATION_PREFIXES),
            "excluded_annotation_objects": sorted(set(excluded_names)),
            "gap_frame_ids": gaps,
            "representative_frame_ids": representative,
            "samples": samples,
        }
        if source_lineage is not None:
            plan["source_lineage"] = source_lineage
        output = args.output_root / site["site_id"] / "trajectory_plan.json"
        if output.exists() and not args.overwrite:
            raise FileExistsError(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(plan, indent=2, allow_nan=False) + "\n")
        result = {
            "site_id": site["site_id"],
            "available": True,
            "plan_path": str(output.resolve()),
            "sample_role": role,
            "start": start,
            "end": end,
            "length": length,
            "gap_frame_ids": gaps,
            "camera_coverage": coverage,
            "rejections": dict(rejected),
        }
        results.append(result)
        print("PILOT_SITE_OK " + json.dumps(result), flush=True)
    verify_immutable_source(source, source_sha, source_stat.st_size, source_stat.st_mtime_ns)
    if source_lineage is not None:
        verify_immutable_source(
            source_lineage["original_source_path"],
            source_lineage["original_source_sha256"],
            source_lineage["original_source_size"],
            source_lineage["original_source_mtime_ns"],
        )
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "site_planning_results.json").write_text(
        json.dumps(
            {
                "data_kind": "PILOT / SYNTHETIC SAMPLE",
                "source_asset_sha256": source_sha,
                "results": results,
            },
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
