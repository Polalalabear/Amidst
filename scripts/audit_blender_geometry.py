"""Read-only evaluated-mesh diagnostics; candidates are not approved navigation geometry."""

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict, deque

import bpy
from mathutils import Vector


def parse_arguments():
    script_arguments = []
    if "--" in sys.argv:
        script_arguments = sys.argv[sys.argv.index("--") + 1 :]
    parser = argparse.ArgumentParser(
        description="Read-only evaluated geometry probe for school_v2.blend"
    )
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--scope",
        choices=("structural", "all"),
        default="structural",
        help="structural analyzes group_0* meshes; all analyzes every non-Areas mesh",
    )
    parser.add_argument("--area-z-tolerance", type=float, default=8.0)
    parser.add_argument("--grid-size", type=int, default=9)
    return parser.parse_args(script_arguments)


ARGS = parse_arguments()
if ARGS.grid_size < 1:
    raise ValueError("--grid-size must be >= 1")
if ARGS.area_z_tolerance < 0:
    raise ValueError("--area-z-tolerance must be >= 0")


HORIZONTAL_DEGREES = 10.0
HORIZONTAL_NZ = math.cos(math.radians(HORIZONTAL_DEGREES))
LAYER_TOLERANCE = 0.25
AREA_Z_TOLERANCE = ARGS.area_z_tolerance
MIN_PATCH_AREA = 0.05


def round_vec(values, digits=4):
    return [round(float(value), digits) for value in values]


def object_is_annotation(obj):
    return any(collection.name == "Areas" for collection in obj.users_collection)


def clip_polygon_axis_aligned(points, xmin, xmax, ymin, ymax):
    polygon = [(float(point[0]), float(point[1])) for point in points]

    def clip(poly, inside, intersect):
        if not poly:
            return []
        output = []
        previous = poly[-1]
        previous_inside = inside(previous)
        for current in poly:
            current_inside = inside(current)
            if current_inside:
                if not previous_inside:
                    output.append(intersect(previous, current))
                output.append(current)
            elif previous_inside:
                output.append(intersect(previous, current))
            previous = current
            previous_inside = current_inside
        return output

    def vertical_intersection(a, b, x):
        denominator = b[0] - a[0]
        if abs(denominator) < 1e-12:
            return (x, a[1])
        t = (x - a[0]) / denominator
        return (x, a[1] + t * (b[1] - a[1]))

    def horizontal_intersection(a, b, y):
        denominator = b[1] - a[1]
        if abs(denominator) < 1e-12:
            return (a[0], y)
        t = (y - a[1]) / denominator
        return (a[0] + t * (b[0] - a[0]), y)

    polygon = clip(
        polygon,
        lambda p: p[0] >= xmin,
        lambda a, b: vertical_intersection(a, b, xmin),
    )
    polygon = clip(
        polygon,
        lambda p: p[0] <= xmax,
        lambda a, b: vertical_intersection(a, b, xmax),
    )
    polygon = clip(
        polygon,
        lambda p: p[1] >= ymin,
        lambda a, b: horizontal_intersection(a, b, ymin),
    )
    polygon = clip(
        polygon,
        lambda p: p[1] <= ymax,
        lambda a, b: horizontal_intersection(a, b, ymax),
    )
    return polygon


def polygon_area_2d(points):
    if len(points) < 3:
        return 0.0
    twice_area = 0.0
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        twice_area += point[0] * next_point[1] - next_point[0] * point[1]
    return abs(twice_area) * 0.5


def triangle_plane_z_at_xy(vertices, x, y):
    a, b, c = vertices
    denominator = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y)
    if abs(denominator) < 1e-12:
        return None
    alpha = ((b.y - c.y) * (x - c.x) + (c.x - b.x) * (y - c.y)) / denominator
    beta = ((c.y - a.y) * (x - c.x) + (a.x - c.x) * (y - c.y)) / denominator
    gamma = 1.0 - alpha - beta
    if min(alpha, beta, gamma) < -1e-8:
        return None
    return alpha * a.z + beta * b.z + gamma * c.z


def cluster_values(values, tolerance):
    if not values:
        return []
    sorted_values = sorted(values)
    clusters = [[sorted_values[0]]]
    for value in sorted_values[1:]:
        if value - statistics.fmean(clusters[-1]) <= tolerance:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    return clusters


depsgraph = bpy.context.evaluated_depsgraph_get()
triangles = []
patches = []
mesh_object_count = 0
evaluated_triangle_count = 0

for source_obj in bpy.context.scene.objects:
    if (
        source_obj.type != "MESH"
        or object_is_annotation(source_obj)
        or (ARGS.scope == "structural" and not source_obj.name.startswith("group_0"))
    ):
        continue
    mesh_object_count += 1
    evaluated_obj = source_obj.evaluated_get(depsgraph)
    mesh = evaluated_obj.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
    try:
        mesh.calc_loop_triangles()
        matrix_world = evaluated_obj.matrix_world.copy()
        world_vertices = [matrix_world @ vertex.co for vertex in mesh.vertices]
        polygon_triangles = defaultdict(list)
        polygon_area = defaultdict(float)
        polygon_xy_area = defaultdict(float)
        polygon_z_weight = defaultdict(float)
        polygon_bbox = {}
        polygon_normal_z = {}

        for loop_triangle in mesh.loop_triangles:
            evaluated_triangle_count += 1
            vertices = [world_vertices[index] for index in loop_triangle.vertices]
            cross = (vertices[1] - vertices[0]).cross(vertices[2] - vertices[0])
            area_3d = 0.5 * cross.length
            if area_3d <= 1e-12:
                continue
            normal = cross.normalized()
            z_values = [vertex.z for vertex in vertices]
            x_values = [vertex.x for vertex in vertices]
            y_values = [vertex.y for vertex in vertices]
            xy_area = polygon_area_2d([(vertex.x, vertex.y) for vertex in vertices])
            slope_degrees = math.degrees(math.acos(min(1.0, abs(normal.z))))
            triangle = {
                "object": source_obj.name,
                "polygon_index": int(loop_triangle.polygon_index),
                "vertices": vertices,
                "normal_z": float(normal.z),
                "slope_degrees": float(slope_degrees),
                "area_3d": float(area_3d),
                "xy_area": float(xy_area),
                "z_mean": float(statistics.fmean(z_values)),
                "z_min": float(min(z_values)),
                "z_max": float(max(z_values)),
                "bbox": (min(x_values), max(x_values), min(y_values), max(y_values)),
                "centroid": tuple(
                    float(statistics.fmean(vertex[axis] for vertex in vertices))
                    for axis in range(3)
                ),
            }
            triangles.append(triangle)
            if normal.z >= HORIZONTAL_NZ and max(z_values) - min(z_values) <= 0.05:
                polygon_index = int(loop_triangle.polygon_index)
                polygon_triangles[polygon_index].append(triangle)
                polygon_area[polygon_index] += area_3d
                polygon_xy_area[polygon_index] += xy_area
                polygon_z_weight[polygon_index] += area_3d * statistics.fmean(z_values)
                if polygon_index not in polygon_bbox:
                    polygon_bbox[polygon_index] = [
                        min(x_values),
                        max(x_values),
                        min(y_values),
                        max(y_values),
                    ]
                else:
                    bbox = polygon_bbox[polygon_index]
                    bbox[0] = min(bbox[0], min(x_values))
                    bbox[1] = max(bbox[1], max(x_values))
                    bbox[2] = min(bbox[2], min(y_values))
                    bbox[3] = max(bbox[3], max(y_values))
                polygon_normal_z[polygon_index] = max(
                    polygon_normal_z.get(polygon_index, -1.0), normal.z
                )

        candidate_indices = set(polygon_triangles)
        edge_to_polygons = defaultdict(list)
        for polygon_index in candidate_indices:
            polygon = mesh.polygons[polygon_index]
            for edge_key in polygon.edge_keys:
                edge_to_polygons[tuple(sorted(edge_key))].append(polygon_index)

        adjacency = defaultdict(set)
        for connected in edge_to_polygons.values():
            for polygon_index in connected:
                adjacency[polygon_index].update(
                    other for other in connected if other != polygon_index
                )

        pending = set(candidate_indices)
        while pending:
            start = pending.pop()
            component = {start}
            queue = deque([start])
            while queue:
                current = queue.popleft()
                current_z = polygon_z_weight[current] / polygon_area[current]
                for neighbor in adjacency[current]:
                    if neighbor not in pending:
                        continue
                    neighbor_z = polygon_z_weight[neighbor] / polygon_area[neighbor]
                    if abs(neighbor_z - current_z) <= LAYER_TOLERANCE:
                        pending.remove(neighbor)
                        component.add(neighbor)
                        queue.append(neighbor)

            total_area = sum(polygon_area[index] for index in component)
            if total_area < MIN_PATCH_AREA:
                continue
            bbox = [
                min(polygon_bbox[index][0] for index in component),
                max(polygon_bbox[index][1] for index in component),
                min(polygon_bbox[index][2] for index in component),
                max(polygon_bbox[index][3] for index in component),
            ]
            weighted_z = sum(polygon_z_weight[index] for index in component) / total_area
            patches.append(
                {
                    "object": source_obj.name,
                    "collections": sorted(c.name for c in source_obj.users_collection),
                    "polygon_count": len(component),
                    "area": float(total_area),
                    "z": float(weighted_z),
                    "bbox_xy": bbox,
                    "normal_z_min": min(polygon_normal_z[index] for index in component),
                    "representative_polygon_indices": sorted(component)[:12],
                }
            )
    finally:
        evaluated_obj.to_mesh_clear()


horizontal_triangles = [
    triangle
    for triangle in triangles
    if triangle["normal_z"] >= HORIZONTAL_NZ and triangle["z_max"] - triangle["z_min"] <= 0.05
]

weighted_layer_bins = defaultdict(
    lambda: {"area": 0.0, "triangles": 0, "objects": set(), "faces": []}
)
for triangle in horizontal_triangles:
    key = round(triangle["z_mean"] / LAYER_TOLERANCE) * LAYER_TOLERANCE
    weighted_layer_bins[key]["area"] += triangle["area_3d"]
    weighted_layer_bins[key]["triangles"] += 1
    weighted_layer_bins[key]["objects"].add(triangle["object"])
    weighted_layer_bins[key]["faces"].append(
        (
            triangle["area_3d"],
            triangle["object"],
            triangle["polygon_index"],
            triangle["centroid"],
        )
    )

z_layers = []
for z, row in weighted_layer_bins.items():
    z_layers.append(
        {
            "z": round(z, 4),
            "upward_horizontal_area": round(row["area"], 4),
            "triangle_count": row["triangles"],
            "object_count": len(row["objects"]),
            "sample_objects": sorted(row["objects"])[:12],
            "representative_faces": [
                {
                    "object": object_name,
                    "polygon_index": polygon_index,
                    "world_centroid": round_vec(centroid, 6),
                    "triangle_area": round(area, 6),
                }
                for area, object_name, polygon_index, centroid in sorted(
                    row["faces"], reverse=True
                )[:5]
            ],
        }
    )
z_layers.sort(key=lambda row: (-row["upward_horizontal_area"], row["z"]))


def annotation_bounds(obj):
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return {
        "xmin": min(point.x for point in points),
        "xmax": max(point.x for point in points),
        "ymin": min(point.y for point in points),
        "ymax": max(point.y for point in points),
        "zmin": min(point.z for point in points),
        "zmax": max(point.z for point in points),
    }


area_rows = []
area_objects = [obj for obj in bpy.context.scene.objects if obj.name.startswith("AREA_")]
for area_obj in sorted(area_objects, key=lambda obj: obj.name):
    bounds = annotation_bounds(area_obj)
    box_xy_area = (bounds["xmax"] - bounds["xmin"]) * (bounds["ymax"] - bounds["ymin"])
    matching = defaultdict(lambda: {"area": 0.0, "objects": Counter(), "faces": []})
    for triangle in horizontal_triangles:
        if abs(triangle["z_mean"] - bounds["zmin"]) > AREA_Z_TOLERANCE:
            continue
        txmin, txmax, tymin, tymax = triangle["bbox"]
        if (
            txmax < bounds["xmin"]
            or txmin > bounds["xmax"]
            or tymax < bounds["ymin"]
            or tymin > bounds["ymax"]
        ):
            continue
        clipped = clip_polygon_axis_aligned(
            triangle["vertices"],
            bounds["xmin"],
            bounds["xmax"],
            bounds["ymin"],
            bounds["ymax"],
        )
        clipped_area = polygon_area_2d(clipped)
        if clipped_area <= 1e-9:
            continue
        layer_key = round(triangle["z_mean"], 2)
        matching[layer_key]["area"] += clipped_area
        matching[layer_key]["objects"][triangle["object"]] += clipped_area
        matching[layer_key]["faces"].append(
            (
                clipped_area,
                triangle["object"],
                triangle["polygon_index"],
                triangle["centroid"],
            )
        )

    layers = []
    for layer_z, layer in matching.items():
        layers.append(
            {
                "z": layer_z,
                "clipped_xy_area": round(layer["area"], 4),
                "raw_box_coverage_ratio": round(
                    layer["area"] / box_xy_area if box_xy_area else 0.0, 6
                ),
                "top_objects": [
                    {"name": name, "clipped_xy_area": round(area, 4)}
                    for name, area in layer["objects"].most_common(8)
                ],
                "representative_faces": [
                    {
                        "object": object_name,
                        "polygon_index": polygon_index,
                        "world_centroid": round_vec(centroid, 6),
                        "clipped_xy_area": round(area, 6),
                    }
                    for area, object_name, polygon_index, centroid in sorted(
                        layer["faces"], reverse=True
                    )[:5]
                ],
            }
        )
    layers.sort(key=lambda row: (-row["clipped_xy_area"], row["z"]))
    area_rows.append(
        {
            "area": area_obj.name,
            "box_xy_area": round(box_xy_area, 4),
            "box_zmin": round(bounds["zmin"], 4),
            "box_zmax": round(bounds["zmax"], 4),
            "horizontal_layers_near_lower_bound": layers,
        }
    )


def stair_region_analysis(area_obj):
    bounds = annotation_bounds(area_obj)
    relevant = []
    for triangle in triangles:
        txmin, txmax, tymin, tymax = triangle["bbox"]
        if (
            txmax < bounds["xmin"]
            or txmin > bounds["xmax"]
            or tymax < bounds["ymin"]
            or tymin > bounds["ymax"]
            or triangle["z_max"] < bounds["zmin"] - 2.0
            or triangle["z_min"] > bounds["zmax"] + 10.0
        ):
            continue
        clipped = clip_polygon_axis_aligned(
            triangle["vertices"],
            bounds["xmin"],
            bounds["xmax"],
            bounds["ymin"],
            bounds["ymax"],
        )
        clipped_area = polygon_area_2d(clipped)
        if clipped_area <= 1e-7:
            continue
        relevant.append((triangle, clipped_area))

    horizontal_by_z = defaultdict(
        lambda: {
            "area": 0.0,
            "objects": Counter(),
            "faces": [],
            "normal_signs": Counter(),
        }
    )
    sloped_by_object = defaultdict(
        lambda: {
            "area": 0.0,
            "slopes": [],
            "zmin": math.inf,
            "zmax": -math.inf,
            "faces": [],
        }
    )
    for triangle, clipped_area in relevant:
        if (
            abs(triangle["normal_z"]) >= HORIZONTAL_NZ
            and triangle["z_max"] - triangle["z_min"] <= 0.05
        ):
            z_key = round(triangle["z_mean"] / 0.05) * 0.05
            horizontal_by_z[z_key]["area"] += clipped_area
            horizontal_by_z[z_key]["objects"][triangle["object"]] += clipped_area
            horizontal_by_z[z_key]["faces"].append(
                (
                    clipped_area,
                    triangle["object"],
                    triangle["polygon_index"],
                    triangle["centroid"],
                )
            )
            horizontal_by_z[z_key]["normal_signs"][
                "up" if triangle["normal_z"] > 0 else "down"
            ] += 1
        if 5.0 < triangle["slope_degrees"] <= 55.0:
            row = sloped_by_object[triangle["object"]]
            row["area"] += clipped_area
            row["slopes"].append(triangle["slope_degrees"])
            row["zmin"] = min(row["zmin"], triangle["z_min"])
            row["zmax"] = max(row["zmax"], triangle["z_max"])
            row["faces"].append(
                (
                    clipped_area,
                    triangle["polygon_index"],
                    triangle["centroid"],
                    triangle["slope_degrees"],
                )
            )

    horizontal_levels = []
    for z, row in horizontal_by_z.items():
        if row["area"] < 0.01:
            continue
        horizontal_levels.append(
            {
                "z": round(z, 4),
                "clipped_xy_area": round(row["area"], 4),
                "top_objects": [
                    {"name": name, "clipped_xy_area": round(area, 4)}
                    for name, area in row["objects"].most_common(8)
                ],
                "normal_sign_triangle_counts": dict(row["normal_signs"]),
                "representative_faces": [
                    {
                        "object": object_name,
                        "polygon_index": polygon_index,
                        "world_centroid": round_vec(centroid, 6),
                        "clipped_xy_area": round(area, 6),
                    }
                    for area, object_name, polygon_index, centroid in sorted(
                        row["faces"], reverse=True
                    )[:5]
                ],
            }
        )
    horizontal_levels.sort(key=lambda row: row["z"])

    sloped_surfaces = []
    for object_name, row in sloped_by_object.items():
        if row["area"] < 0.01:
            continue
        sloped_surfaces.append(
            {
                "object": object_name,
                "clipped_xy_area": round(row["area"], 4),
                "slope_min_degrees": round(min(row["slopes"]), 4),
                "slope_median_degrees": round(statistics.median(row["slopes"]), 4),
                "slope_max_degrees": round(max(row["slopes"]), 4),
                "z_min": round(row["zmin"], 4),
                "z_max": round(row["zmax"], 4),
                "representative_faces": [
                    {
                        "polygon_index": polygon_index,
                        "world_centroid": round_vec(centroid, 6),
                        "clipped_xy_area": round(area, 6),
                        "slope_degrees": round(slope, 6),
                    }
                    for area, polygon_index, centroid, slope in sorted(row["faces"], reverse=True)[
                        :5
                    ]
                ],
            }
        )
    sloped_surfaces.sort(key=lambda row: (-row["clipped_xy_area"], row["object"]))

    sample_grid = []
    for x_index in range(ARGS.grid_size):
        x = bounds["xmin"] + (x_index + 0.5) * (bounds["xmax"] - bounds["xmin"]) / ARGS.grid_size
        for y_index in range(ARGS.grid_size):
            y = (
                bounds["ymin"]
                + (y_index + 0.5) * (bounds["ymax"] - bounds["ymin"]) / ARGS.grid_size
            )
            hits = []
            for triangle, _ in relevant:
                if abs(triangle["normal_z"]) < 0.05:
                    continue
                txmin, txmax, tymin, tymax = triangle["bbox"]
                if not (txmin - 1e-8 <= x <= txmax + 1e-8 and tymin - 1e-8 <= y <= tymax + 1e-8):
                    continue
                z = triangle_plane_z_at_xy(triangle["vertices"], x, y)
                if z is not None and bounds["zmin"] - 2.0 <= z <= bounds["zmax"] + 10.0:
                    hits.append(z)
            if hits:
                sample_grid.append(max(hits))
    sampled_clusters = cluster_values(sample_grid, 0.5)
    return {
        "area": area_obj.name,
        "bounds": {key: round(value, 4) for key, value in bounds.items()},
        "intersecting_triangle_count": len(relevant),
        "upward_horizontal_levels": horizontal_levels,
        "ascending_surfaces": sloped_surfaces[:30],
        "grid_samples_with_surface": len(sample_grid),
        "grid_top_surface_height_clusters": [
            {
                "z_mean": round(statistics.fmean(cluster), 4),
                "z_min": round(min(cluster), 4),
                "z_max": round(max(cluster), 4),
                "sample_count": len(cluster),
            }
            for cluster in sampled_clusters
        ],
    }


stair_rows = [
    stair_region_analysis(bpy.data.objects[name])
    for name in ("AREA_STAIR01", "AREA_STAIR02")
    if name in bpy.data.objects
]

camera_rows = []
for obj in sorted(
    (
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "CAMERA" and obj.name.startswith("CAM_")
    ),
    key=lambda obj: obj.name,
):
    camera_rows.append(
        {
            "name": obj.name,
            "z": round(float(obj.matrix_world.translation.z), 4),
        }
    )

camera_groups = {}
for floor_token, floor_z in (("CAM_1F_", 15.0), ("CAM_2F_", 160.0)):
    zs = [row["z"] for row in camera_rows if row["name"].startswith(floor_token)]
    if zs:
        camera_groups[floor_token.rstrip("_")] = {
            "count": len(zs),
            "z_min": round(min(zs), 4),
            "z_median": round(statistics.median(zs), 4),
            "z_max": round(max(zs), 4),
            "height_above_annotation_lower_bound_min": round(min(zs) - floor_z, 4),
            "height_above_annotation_lower_bound_median": round(statistics.median(zs) - floor_z, 4),
            "height_above_annotation_lower_bound_max": round(max(zs) - floor_z, 4),
        }

top_patches = sorted(patches, key=lambda row: (-row["area"], row["object"]))[:120]
for patch in top_patches:
    patch["area"] = round(patch["area"], 4)
    patch["z"] = round(patch["z"], 4)
    patch["bbox_xy"] = round_vec(patch["bbox_xy"])
    patch["normal_z_min"] = round(patch["normal_z_min"], 6)

payload = {
    "analysis_parameters": {
        "annotation_collection_excluded": "Areas",
        "mesh_name_scope": (
            "group_0* structural meshes"
            if ARGS.scope == "structural"
            else "all non-Areas mesh objects"
        ),
        "near_horizontal_max_degrees": HORIZONTAL_DEGREES,
        "connected_patch_z_tolerance": LAYER_TOLERANCE,
        "area_lower_bound_z_tolerance": AREA_Z_TOLERANCE,
        "evaluated_meshes": True,
        "sampling": {
            "method": f"fixed {ARGS.grid_size}x{ARGS.grid_size} cell-centre grid",
            "randomness_used": False,
            "seed": None,
        },
    },
    "mesh_object_count_excluding_annotations": mesh_object_count,
    "evaluated_triangle_count": evaluated_triangle_count,
    "upward_horizontal_triangle_count": len(horizontal_triangles),
    "dominant_upward_horizontal_z_layers": z_layers[:80],
    "largest_connected_upward_horizontal_patches": top_patches,
    "area_lower_bound_surface_evidence": area_rows,
    "stair_region_evidence": stair_rows,
    "camera_z_summary": camera_groups,
    "camera_count": len(camera_rows),
}

print("FLOOR_GEOMETRY_PROBE_JSON_BEGIN")
output_path = ARGS.output
with open(output_path, "w", encoding="utf-8") as output_file:
    json.dump(payload, output_file, ensure_ascii=False, indent=2, sort_keys=True)
print(
    json.dumps(
        {
            "output_path": output_path,
            "mesh_object_count_excluding_annotations": mesh_object_count,
            "evaluated_triangle_count": evaluated_triangle_count,
            "upward_horizontal_triangle_count": len(horizontal_triangles),
            "dominant_layers": z_layers[:12],
            "stair_region_evidence": stair_rows,
            "camera_z_summary": camera_groups,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
)
print("FLOOR_GEOMETRY_PROBE_JSON_END")
