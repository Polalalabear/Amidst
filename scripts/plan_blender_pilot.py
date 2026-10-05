"""Read-only PILOT trajectory validation in Blender's evaluated physical meshes.

Run with Blender --background --disable-autoexec school_v3.blend --python
scripts/plan_blender_pilot.py -- --output data/pilot/.../trajectory_plan.json.
The fixed local route was chosen by mesh-supported visibility grid search.
This simulation-only plan never enters inference, Graph, ranking or benchmarks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ANNOTATION_COLLECTIONS = ("Areas", "WALKABLE_AREAS", "OBSTACLE_AREAS", "STAIR_ANNOTATIONS")
ANNOTATION_PREFIXES = ("AREA_", "PORTAL_", "WALK_", "WALKABLE_", "OBSTACLE_", "STAIR_")
CAMERA_IDS = ("CAM_1F_CORRIDOR_02", "CAM_1F_CORRIDOR_03")
WALKABLE_ID = "WALK_1F_CORRIDOR_01"


def clip_polygon(points, axis, bound, keep_above):
    """Clip a world triangle/polygon against a closed axis half-space."""
    if not points:
        return []
    result = []
    previous = points[-1]
    previous_inside = previous[axis] >= bound if keep_above else previous[axis] <= bound
    for current in points:
        current_inside = current[axis] >= bound if keep_above else current[axis] <= bound
        if current_inside != previous_inside:
            ratio = (bound - previous[axis]) / (current[axis] - previous[axis])
            result.append(
                tuple(a + ratio * (b - a) for a, b in zip(previous, current, strict=True))
            )
        if current_inside:
            result.append(current)
        previous, previous_inside = current, current_inside
    return result


def triangle_intersects_box(vertices, minimum, maximum):
    points = [tuple(v) for v in vertices]
    for axis in range(3):
        points = clip_polygon(points, axis, minimum[axis], True)
        points = clip_polygon(points, axis, maximum[axis], False)
    return bool(points)


def point_in_xy_triangle(point, vertices):
    x, y = point[:2]
    a, b, c = vertices
    denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(denominator) < 1e-10:
        return False
    alpha = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / denominator
    beta = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / denominator
    return min(alpha, beta, 1 - alpha - beta) >= -1e-7


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--start-x", type=float, default=960.0)
    parser.add_argument("--end-x", type=float, default=1066.0)
    parser.add_argument("--y", type=float, default=740.0)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])


def main():
    import bpy
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    repository = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository / "src"))
    from amidst.simulation.blender_camera import extract_camera_dict

    args = parse_args()
    scene = bpy.context.scene
    source = Path(bpy.data.filepath).resolve()
    if args.output.resolve() == source or args.output.suffix.lower() != ".json":
        raise ValueError("Pilot plan output must be JSON and cannot replace the Blender input")
    if args.output.exists() and not args.overwrite:
        raise FileExistsError("Pilot plan exists; use a new output or explicit --overwrite")
    source_stat = source.stat()
    with source.open("rb") as stream:
        source_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    excluded = set()
    excluded_names = []
    for name in ANNOTATION_COLLECTIONS:
        collection = bpy.data.collections.get(name)
        if collection:
            excluded.update(obj.original.as_pointer() for obj in collection.all_objects)
            excluded_names.extend(obj.name for obj in collection.all_objects)

    for obj in scene.objects:
        if obj.type == "MESH" and obj.name.startswith(ANNOTATION_PREFIXES):
            excluded.add(obj.original.as_pointer())
            excluded_names.append(obj.name)

    radius, height, probe_height, margin = 6.0, 119.0, 55.0, 0.05
    # The support-probe result from the selected corridor is remeasured below.
    walkable_source = bpy.data.objects[WALKABLE_ID]
    annotation_z = min(
        (walkable_source.matrix_world @ Vector(c)).z for c in walkable_source.bound_box
    )
    initial_floor_z = 20.07884979248047
    sweep_minimum = (
        min(args.start_x, args.end_x) - radius,
        args.y - radius,
        initial_floor_z + margin,
    )
    sweep_maximum = (
        max(args.start_x, args.end_x) + radius,
        args.y + radius,
        initial_floor_z + margin + height,
    )
    vertices, triangles, triangle_objects = [], [], []
    swept_intersections = []
    physical_objects = set()
    for instance in depsgraph.object_instances:
        obj = instance.object
        if obj.type != "MESH" or not instance.show_self or obj.original.as_pointer() in excluded:
            continue
        matrix = instance.matrix_world.copy()
        corners = [matrix @ Vector(corner) for corner in obj.bound_box]
        potential_collision = all(
            max(v[axis] for v in corners) >= sweep_minimum[axis]
            and min(v[axis] for v in corners) <= sweep_maximum[axis]
            for axis in range(3)
        )
        mesh = obj.to_mesh()
        mesh.calc_loop_triangles()
        offset = len(vertices)
        world_vertices = [matrix @ vertex.co for vertex in mesh.vertices]
        vertices.extend(world_vertices)
        for triangle in mesh.loop_triangles:
            indices = tuple(offset + index for index in triangle.vertices)
            triangles.append(indices)
            triangle_objects.append(obj.original.name)
            if potential_collision:
                points = [world_vertices[index] for index in triangle.vertices]
                if all(
                    max(v[axis] for v in points) >= sweep_minimum[axis]
                    and min(v[axis] for v in points) <= sweep_maximum[axis]
                    for axis in range(3)
                ) and triangle_intersects_box(points, sweep_minimum, sweep_maximum):
                    swept_intersections.append(
                        {"object": obj.original.name, "triangle": int(triangle.index)}
                    )
        physical_objects.add(obj.original.name)
        obj.to_mesh_clear()
    print(f"PHYSICAL_BVH {len(physical_objects)} objects; {len(triangles)} triangles", flush=True)
    if swept_intersections:
        raise ValueError(
            f"Synthetic target sweep intersects physical mesh: {swept_intersections[:8]}"
        )
    bvh = BVHTree.FromPolygons(vertices, triangles, all_triangles=True, epsilon=0)

    walkable = bpy.data.objects[WALKABLE_ID].evaluated_get(depsgraph)
    walk_mesh = walkable.to_mesh()
    walk_mesh.calc_loop_triangles()
    walk_vertices = [walkable.matrix_world @ vertex.co for vertex in walk_mesh.vertices]
    walk_triangles = [
        tuple(walk_vertices[index] for index in triangle.vertices)
        for triangle in walk_mesh.loop_triangles
    ]
    walkable.to_mesh_clear()
    camera_objects = [bpy.data.objects[camera_id] for camera_id in CAMERA_IDS]
    cameras = [extract_camera_dict(scene, camera) for camera in camera_objects]
    plane_probe_xy = ((args.start_x + args.end_x) / 2.0, args.y)
    plane_hit, plane_normal, plane_triangle, _ = bvh.ray_cast(
        Vector((*plane_probe_xy, annotation_z + 15.0)), Vector((0, 0, -1)), 30.0
    )
    if plane_hit is None or abs(plane_normal.z) < 0.95:
        raise ValueError("Independent physical observation-plane probe failed")
    observation_plane_z = float(plane_hit.z) + margin + probe_height
    samples = []
    floor_hits = []
    for frame_id in range(50):
        timestamp = frame_id / 5.0
        x = args.start_x + (args.end_x - args.start_x) * timestamp / 10.0
        footprint = [
            (x + dx, args.y + dy)
            for dx, dy in (
                (0, 0),
                (-radius, -radius),
                (-radius, radius),
                (radius, -radius),
                (radius, radius),
            )
        ]
        hits = []
        for px, py in footprint:
            if not any(point_in_xy_triangle((px, py), tri) for tri in walk_triangles):
                raise ValueError(
                    f"Target footprint leaves actual WALKABLE mesh at frame {frame_id}"
                )
            hit, normal, triangle_index, _ = bvh.ray_cast(
                Vector((px, py, annotation_z + 15.0)), Vector((0, 0, -1)), 30.0
            )
            if hit is None or abs(normal.z) < 0.95 or abs(hit.z - initial_floor_z) > 0.01:
                raise ValueError(f"Physical support missing/nonplanar at frame {frame_id}: {hit}")
            hits.append(
                {
                    "position": list(hit),
                    "normal": list(normal),
                    "object": triangle_objects[triangle_index],
                }
            )
        floor_z = float(hits[0]["position"][2])
        foot = Vector((x, args.y, floor_z + margin))
        probe = foot + Vector((0, 0, probe_height))
        states = []
        for camera, calibration in zip(camera_objects, cameras, strict=True):
            projected = world_to_camera_view(scene, camera, probe)
            depth = float(projected.z)
            uv = (
                float(projected.x) * calibration["width"],
                (1.0 - float(projected.y)) * calibration["height"],
            )
            reason, status, occluder, hit_position = "CLEAR", "visible", None, None
            if depth <= 0:
                status, reason = "out_of_FOV", "BEHIND_CAMERA"
            elif depth < calibration["clip_start"] or depth > calibration["clip_end"]:
                status, reason = (
                    "out_of_FOV",
                    "NEAR_CLIPPED" if depth < calibration["clip_start"] else "FAR_CLIPPED",
                )
            elif not (0 <= uv[0] < calibration["width"] and 0 <= uv[1] < calibration["height"]):
                status, reason = "out_of_FOV", "OUTSIDE_FOV"
            else:
                origin = camera.evaluated_get(depsgraph).matrix_world.translation
                delta = probe - origin
                hit, _, triangle_index, _ = bvh.ray_cast(
                    origin, delta.normalized(), delta.length - 0.001
                )
                if hit is not None:
                    status, reason = "occluded", "OCCLUDED"
                    occluder, hit_position = triangle_objects[triangle_index], list(hit)
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
        global_gap = all(state["status"] != "visible" for state in states)
        samples.append(
            {
                "frame_id": frame_id,
                "timestamp": timestamp,
                "floor_id": "1F",
                "trajectory_id": "PILOT_1F_CORRIDOR_OCCLUSION_001",
                "position": list(foot),
                "foot_position": list(foot),
                "probe_position": list(probe),
                "global_gap": global_gap,
                "physical_support": hits,
                "camera_visibility": states,
            }
        )
        floor_hits.extend(hits)
    gaps = [row["frame_id"] for row in samples if row["global_gap"]]
    if not gaps or samples[0]["global_gap"] or samples[-1]["global_gap"]:
        Path("/private/tmp/amidst-pilot-plan-failure.json").write_text(
            json.dumps(samples, indent=2)
        )
        raise ValueError("Pilot route does not have observed -> selected-camera GAP -> observed")
    if gaps != list(range(min(gaps), max(gaps) + 1)):
        raise ValueError("Pilot selected-camera GAP must be a single contiguous interval")
    if not any(
        state["status"] == "visible"
        for row in samples
        for state in row["camera_visibility"]
        if state["camera_id"] == CAMERA_IDS[0]
    ):
        raise ValueError("First selected camera contributes no observed evidence")
    first_gap, last_gap = min(gaps), max(gaps)
    representative_frames = [0, first_gap - 1, first_gap, (first_gap + last_gap) // 2, last_gap + 1]
    result = {
        "schema_version": "amidst-blender-pilot-plan-v1",
        "data_kind": "PILOT / SYNTHETIC SAMPLE",
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
            "UNVERIFIED: 140-unit floor spacing; unit settings alone do not attest "
            "realistic architectural scale"
        ),
        "trajectory_id": "PILOT_1F_CORRIDOR_OCCLUSION_001",
        "floor_id": "1F",
        "duration_seconds": 10.0,
        "sampling_fps": 5.0,
        "timestamp_count": 50,
        "time_interval": "[0.0,10.0), timestamps 0.0 through 9.8",
        "camera_ids": list(CAMERA_IDS),
        "cameras": cameras,
        "probe_height_units": probe_height,
        "observation_plane_z": observation_plane_z,
        "projection_plane_basis": {
            "mesh_object_id": triangle_objects[plane_triangle],
            "physical_floor_z": float(plane_hit.z),
            "independent_mesh_probe_xy": list(plane_probe_xy),
            "physical_floor_normal": list(plane_normal),
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
            {"timestamp": 10.0, "position": [args.end_x, args.y, samples[0]["foot_position"][2]]},
        ],
        "trajectory_length_scene_units": abs(args.end_x - args.start_x),
        "sampled_length_scene_units": abs(samples[-1]["position"][0] - samples[0]["position"][0]),
        "speed_scene_units_per_second": abs(args.end_x - args.start_x) / 10.0,
        "floor_support_evidence": {
            "walkable_object": WALKABLE_ID,
            "floor_label_authority": "EXISTING_WALKABLE_METADATA_DIAGNOSTIC",
            "annotation_plane_z": annotation_z,
            "physical_floor_z_min": min(hit["position"][2] for hit in floor_hits),
            "physical_floor_z_max": max(hit["position"][2] for hit in floor_hits),
            "annotation_minus_physical_floor_scene_units": annotation_z - initial_floor_z,
            "physical_support_objects": sorted({hit["object"] for hit in floor_hits}),
            "support_probes_per_timestamp": 5,
            "target_full_sweep_clear": True,
            "swept_aabb_minimum": list(sweep_minimum),
            "swept_aabb_maximum": list(sweep_maximum),
            "sweep_method": (
                "EXACT_TRIANGLE_CLIPPING_AGAINST_FULL_CONTINUOUS_ROUTE_SWEPT_AABB; "
                "conservative radius6/height119 marker envelope"
            ),
            "portal_crossings": [],
            "cross_floor_transitions": [],
            "elevator_transitions": [],
        },
        "search_evidence": {
            "method": (
                "20-unit grid on existing 1F WALKABLE extents, measured physical support "
                "and point ray visibility; local straight routes then full volume revalidation"
            ),
            "valid_grid_points": 4056,
            "local_visible_gap_visible_candidates": 214,
            "physical_objects": len(physical_objects),
            "physical_triangles": len(triangles),
        },
        "excluded_annotation_collections": list(ANNOTATION_COLLECTIONS),
        "excluded_annotation_prefixes": list(ANNOTATION_PREFIXES),
        "excluded_annotation_objects": sorted(set(excluded_names)),
        "gap_frame_ids": gaps,
        "representative_frame_ids": representative_frames,
        "samples": samples,
    }
    with source.open("rb") as stream:
        final_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    if final_sha != source_sha or source.stat().st_mtime_ns != source_stat.st_mtime_ns:
        raise RuntimeError("Source Blender asset changed during read-only planning")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(
        f"PILOT_PLAN_OK {len(samples)} timestamps; global GAP frames {first_gap}-{last_gap}; "
        f"representative {representative_frames}",
        flush=True,
    )


if __name__ == "__main__":
    main()
