"""Add a GT-free node/edge locator to the existing source-model motion frames.

Raw navigation is copied unchanged. The floor overlay is a display-only, pending
HR-02 coordinate conversion; it neither prunes the graph nor certifies routes.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "human_review"
OUT = HERE / "frames/topology_context"
PIPELINE_RELATIVE = (
    "data/finalization/local_run/diagnostics/office/policy_graph_primary/pipeline_config.json"
)
MOTION_RELATIVE = "human_review/frames/motion_context/motion_manifest.json"
DIGESTS_RELATIVE = PIPELINE_RELATIVE.replace("pipeline_config.json", "digests.json")
TOPOLOGY_RELATIVE = PIPELINE_RELATIVE.replace("pipeline_config.json", "topology_evidence.json")
CANDIDATES_RELATIVE = PIPELINE_RELATIVE.replace("pipeline_config.json", "candidates.json")
SOURCE_SHA256 = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"
REVIEW_HASH = "e105c3116ebec64e94667f2f863bb0868f4fc34eeeedf1ced0a0b1a931ee1463"
PUBLIC_JSON = frozenset(
    (
        PIPELINE_RELATIVE,
        DIGESTS_RELATIVE,
        MOTION_RELATIVE,
        "human_review/frames/visual_manifest.json",
        "human_review/review_template.json",
        "human_review/geometry_evidence.json",
    )
)
NODE_IDS = ("projected_departure", "projected_recovery")
EDGE_IDS = ("pilot_route:direct", "pilot_route:left", "pilot_route:right")
COLORS = ("#172b38", "#172b38", "#172b38")
PIPELINE_OUTPUT_SHA256 = {
    "pipeline_config.json": "492591e47c48642e157621c9c05adf111f3c6909d671d84e248c4ae0807c80e1",
    "topology_evidence.json": "1bc6f6c108d1fc3775f3c0836132138bf852bcabd1bb9489deef6b4f298dbcf9",
    "candidates.json": "0212756864986ee5044313058144c7e3fcb56c72e68ebd30b7062e508b9c9b02",
}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def public_path(path: Path, *, repo_root: Path = ROOT) -> Path:
    try:
        relative = path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError as error:
        raise ValueError("topology input must stay inside its public repository") from error
    if relative not in PUBLIC_JSON:
        raise ValueError("topology view accepts only explicit public source/review JSON")
    return path


def read_public(path: Path, *, repo_root: Path = ROOT) -> dict[str, Any]:
    """Reject every non-allowlisted input before opening source bytes."""
    public_path(path, repo_root=repo_root)
    return cast(dict[str, Any], json.loads(path.read_text()))


def validate_navigation(navigation: dict[str, Any]) -> dict[str, Any]:
    """Keep the current two-node, three-parallel-edge graph contract intact."""
    if navigation.get("source_asset_sha256") != SOURCE_SHA256:
        raise ValueError("navigation source hash differs from school_v3")
    nodes, edges = navigation.get("nodes", []), navigation.get("edges", [])
    if tuple(row["node_id"] for row in nodes) != NODE_IDS:
        raise ValueError("topology view must preserve exactly the existing two graph nodes")
    if tuple(row["edge_id"] for row in edges) != EDGE_IDS:
        raise ValueError("topology view must preserve all three configured parallel edges")
    for node in nodes:
        if len(node["position"]) != 3 or not all(math.isfinite(v) for v in node["position"]):
            raise ValueError("graph positions must be finite 3D public coordinates")
    for index, edge in enumerate(edges):
        if edge["from_node_id"] != NODE_IDS[0] or edge["to_node_id"] != NODE_IDS[1]:
            raise ValueError("all existing edges must remain directed N1 to N2")
        if len(edge["polyline"]) != (2 if index == 0 else 4):
            raise ValueError("existing edge polyline vertices must remain unchanged")
        if edge["polyline"][0] != nodes[0]["position"]:
            raise ValueError("edge departure differs from its original graph node")
        if edge["polyline"][-1] != nodes[1]["position"]:
            raise ValueError("edge recovery differs from its original graph node")
        for point in edge["polyline"]:
            if len(point) != 3 or not all(math.isfinite(v) for v in point):
                raise ValueError("polyline vertices must be finite public 3D coordinates")
    return navigation


def project_point(
    point: list[float], review_camera: dict[str, Any], width: int = 960, height: int = 600
) -> list[float]:
    """Blender Euler XYZ: inverse of Rz @ Ry @ Rx, orthographic square pixels."""
    x, y, z = review_camera["rotation_euler_radians"]
    cx, sx, cy, sy, cz, sz = (
        math.cos(x),
        math.sin(x),
        math.cos(y),
        math.sin(y),
        math.cos(z),
        math.sin(z),
    )
    rotation = (
        (cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx),
        (sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx),
        (-sy, cy * sx, cy * cx),
    )
    delta = [a - b for a, b in zip(point, review_camera["position_bu"], strict=True)]
    local = [sum(rotation[j][i] * delta[j] for j in range(3)) for i in range(2)]
    pixels_per_bu = width / review_camera["ortho_scale_bu"]
    return [width / 2 + local[0] * pixels_per_bu, height / 2 - local[1] * pixels_per_bu]


def floor_position(point: list[float], offset_bu: float) -> list[float]:
    return [point[0], point[1], point[2] - offset_bu]


def frozen_files() -> list[Path]:
    core = [
        HERE / "decisions.json",
        HERE / "review_template.json",
        HERE / "frames/visual_manifest.json",
        HERE / "frames/player.html",
        HERE / "frames/player_template.html",
        HERE / "build_frame_player.py",
        HERE / "build_spatial_guide.py",
        HERE / "frames/spatial_context/guide.html",
        HERE / "frames/spatial_context/guide_template.html",
        HERE / "frames/spatial_context/spatial_context_manifest.json",
        HERE / "frames/motion_context/motion_manifest.json",
        HERE / "frames/motion_context/gif_manifest.json",
        HERE / "frames/motion_context/player.html",
    ]
    images = sorted(path for path in (HERE / "frames").rglob("*.png") if OUT not in path.parents)
    gifs = sorted((HERE / "frames").rglob("*.gif"))
    return [path for path in [*core, *images, *gifs] if path.is_file()]


def relative_path(path: Path, output: Path) -> str:
    return Path(os.path.relpath(path, output.parent)).as_posix()


def verified_original_inputs(template: dict[str, Any]) -> list[dict[str, str]]:
    immutable = copy.deepcopy(template)
    immutable.pop("review_payload_sha256", None)
    immutable["metadata"].pop("reviewer", None)
    immutable["metadata"].pop("submitted_at", None)
    for item in immutable["items"]:
        item.pop("decision", None)
        item.pop("selected_option", None)
    canonical = json.dumps(
        immutable, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    actual = hashlib.sha256(canonical.encode()).hexdigest()
    if template.get("review_payload_sha256") != REVIEW_HASH or actual != REVIEW_HASH:
        raise ValueError("topology display requires the unchanged four-question payload")
    rows = cast(list[dict[str, str]], template["metadata"]["input_hashes"])
    if len(rows) != 29:
        raise ValueError("the existing 29 frozen review inputs must remain unchanged")
    paths = []
    for row in rows:
        relative = Path(row["path"])
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or any(value in relative.parts for value in ("evaluation", "simulation"))
            or "ground_truth" in relative.name
        ):
            raise ValueError("review-input hashing cannot access GT or simulation recipes")
        resolved = (ROOT / relative).resolve()
        if ROOT.resolve() not in resolved.parents:
            raise ValueError("review input escapes its repository")
        paths.append((resolved, row["sha256"]))
    for path, expected in paths:
        if digest(path) != expected:
            raise ValueError("frozen review-input hash changed: " + path.name)
    return rows


def validate_motion(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != "phase1-human-review-body-motion-v1":
        raise ValueError("unsupported frozen motion manifest")
    if manifest.get("result_type") != "DIAGNOSTIC":
        raise ValueError("topology must remain diagnostic")
    for key in (
        "gt_used",
        "evaluation_files_read",
        "simulation_recipe_read",
        "source_saved",
        "source_modified",
        "physical_authority_changed",
        "formal_execution_enabled",
    ):
        if manifest.get(key) is not False:
            raise ValueError("topology evidence contract violation: " + key)
    if manifest.get("source_preserved") is not True or manifest["source_sha256"] != SOURCE_SHA256:
        raise ValueError("topology requires the preserved source-model evidence")
    if len(manifest["frames"]) != 50 or manifest["fps"] != 5:
        raise ValueError("topology references the existing 50 motion frames at 5 Hz")


def build_topology(
    pipeline_config_path: Path, motion_manifest_path: Path, output_path: Path
) -> dict[str, Any]:
    """Write only the new topology HTML, exact display data, and hash receipt."""
    public_path(pipeline_config_path)
    public_path(motion_manifest_path)
    digests = read_public(ROOT / DIGESTS_RELATIVE)
    graph_inputs = [
        (pipeline_config_path, "pipeline_config.json"),
        (ROOT / TOPOLOGY_RELATIVE, "topology_evidence.json"),
        (ROOT / CANDIDATES_RELATIVE, "candidates.json"),
    ]
    for path, name in graph_inputs:
        expected = PIPELINE_OUTPUT_SHA256[name]
        if digests["outputs"][name] != expected or digest(path) != expected:
            raise ValueError("pipeline source differs from its existing digest receipt: " + name)
    config = read_public(pipeline_config_path)
    navigation = validate_navigation(config["pipeline"]["navigation"])
    motion = read_public(motion_manifest_path)
    validate_motion(motion)
    original = read_public(HERE / "frames/visual_manifest.json")
    geometry = read_public(HERE / "geometry_evidence.json")
    if any(source.get("gt_used") is not False for source in (original, geometry)):
        raise ValueError("topology display cannot consume GT evidence")
    inputs = verified_original_inputs(read_public(HERE / "review_template.json"))
    protected = {path: digest(path) for path in frozen_files()}
    camera = motion["review_camera"]
    width, height = motion["render_policy"]["width"], motion["render_policy"]["height"]
    offset = original["proposed_exact_landmark_offset_bu"]
    floor_z = original["approved_support_z_bu"]
    nodes = []
    for index, node in enumerate(navigation["nodes"]):
        point = node["position"]
        floor_point = floor_position(point, offset)
        if not math.isclose(floor_point[2], floor_z, abs_tol=1e-10):
            raise ValueError("pending HR-02 graph overlay does not contact the approved floor")
        nodes.append(
            {
                "alias": f"N{index + 1}",
                "id": node["node_id"],
                "raw_position_bu": point,
                "floor_position_bu": floor_point,
                "raw_pixel": project_point(point, camera, width, height),
                "floor_pixel": project_point(floor_point, camera, width, height),
            }
        )
    paths = {row["route"][0]: row for row in geometry["paths"]}
    edges = []
    for index, edge in enumerate(navigation["edges"]):
        floor = [floor_position(point, offset) for point in edge["polyline"]]
        witness = paths[edge["edge_id"]]
        if witness["source_landmark_polyline_bu"] != edge["polyline"]:
            raise ValueError("physical diagnostic witness differs from the original graph edge")
        if witness["prospective_foot_polyline_bu"] != floor:
            raise ValueError(
                "existing pending floor witness differs from its coordinate conversion"
            )
        floor = witness["prospective_foot_polyline_bu"]
        support = witness["support_eligible_for_prospective_scope"]
        edges.append(
            {
                "alias": f"E{index + 1}",
                "id": edge["edge_id"],
                "color": COLORS[index],
                "from_node": "N1",
                "to_node": "N2",
                "raw_polyline_bu": edge["polyline"],
                "floor_polyline_bu": floor,
                "raw_pixels": [project_point(p, camera, width, height) for p in edge["polyline"]],
                "floor_pixels": [project_point(p, camera, width, height) for p in floor],
                "interior_vertices": [
                    {
                        "alias": f"E{index + 1}.v{i + 1}",
                        "role": "POLYLINE_VERTEX_NOT_NODE",
                        "raw_position_bu": point,
                        "floor_position_bu": floor[i + 1],
                    }
                    for i, point in enumerate(edge["polyline"][1:-1])
                ],
                "raw_graph_edge_retained": True,
                "floor_diagnostic_status": "NOT_CERTIFIED" if support else "AUTO_REJECT_SUPPORT",
                "support_checks": witness["support_checks"],
                "physical_route_approved": False,
            }
        )
    frames = []
    for index, frame in enumerate(motion["frames"]):
        if frame["frame_id"] != index or frame["timestamp"] != index / 5:
            raise ValueError("topology playback must keep the exact frozen timestamps")
        name = frame["path"]
        if name != f"motion_{index:03d}.png":
            raise ValueError("topology references only the existing motion PNG filenames")
        path = motion_manifest_path.parent / name
        if digest(path) != frame["sha256"]:
            raise ValueError("frozen motion image hash mismatch")
        frames.append(
            {
                "path": relative_path(path, output_path),
                "sha256": frame["sha256"],
                "frame_id": index,
                "timestamp": frame["timestamp"],
                "role": frame["role"],
            }
        )
    data = {
        "schema_version": "phase1-human-review-topology-view-v1",
        "result_type": "DIAGNOSTIC",
        "gt_used": False,
        "evaluation_files_read": False,
        "simulation_recipe_read": False,
        "source_opened_by_builder": False,
        "physical_authority_changed": False,
        "formal_execution_enabled": False,
        "raw_graph_changed": False,
        "source_sha256": SOURCE_SHA256,
        "review_payload_sha256": REVIEW_HASH,
        "graph_id": navigation["graph_id"],
        "raw_navigation": navigation,
        "nodes": nodes,
        "edges": edges,
        "review_camera": camera,
        "conversion": {
            "authority": "PENDING_HR02_SEMANTIC_BINDING",
            "offset_bu": offset,
            "offset_m": original["proposed_exact_landmark_offset_m"],
            "floor_z_bu": floor_z,
            "xy_preserved": True,
            "raw_graph_changed": False,
        },
        "node_count": 2,
        "edge_count": 3,
        "interior_vertex_count": 4,
        "width": width,
        "height": height,
        "fps": 5,
        "frames": frames,
        "model_frame": frames[25],
        "old_motion_player": relative_path(HERE / "frames/motion_context/player.html", output_path),
        "old_guide": relative_path(HERE / "frames/spatial_context/guide.html", output_path),
        "inputs": [
            *inputs,
            {"path": PIPELINE_RELATIVE, "sha256": digest(pipeline_config_path)},
            {"path": MOTION_RELATIVE, "sha256": digest(motion_manifest_path)},
            {"path": DIGESTS_RELATIVE, "sha256": digest(ROOT / DIGESTS_RELATIVE)},
            {"path": TOPOLOGY_RELATIVE, "sha256": digest(ROOT / TOPOLOGY_RELATIVE)},
        ],
        "pipeline_output_digests_verified": {
            name: digests["outputs"][name] for _path, name in graph_inputs
        },
    }
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    safe_encoded = encoded.replace("</", "<\\/").replace("\u2028", "\\u2028")
    safe_encoded = safe_encoded.replace("\u2029", "\\u2029")
    template = (OUT / "template.html").read_text()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(template.replace("__TOPOLOGY_DATA__", safe_encoded))
    data_path = output_path.parent / "topology_data.json"
    data_path.write_text(encoded + "\n")
    if any(digest(path) != expected for path, expected in protected.items()):
        raise RuntimeError("topology generation changed existing review evidence")
    receipt = {
        "schema_version": "phase1-human-review-topology-manifest-v1",
        "result_type": "DIAGNOSTIC",
        "gt_used": False,
        "evaluation_files_read": False,
        "simulation_recipe_read": False,
        "source_opened_by_builder": False,
        "physical_authority_changed": False,
        "formal_execution_enabled": False,
        "raw_graph_changed": False,
        "new_route_generated": False,
        "source_sha256": SOURCE_SHA256,
        "review_payload_sha256": REVIEW_HASH,
        "graph_id": navigation["graph_id"],
        "node_count": 2,
        "edge_count": 3,
        "interior_vertex_count": 4,
        "conversion": data["conversion"],
        "inputs": data["inputs"],
        "builder_sha256": digest(Path(__file__).resolve()),
        "template_sha256": digest(OUT / "template.html"),
        "view": {"path": output_path.name, "sha256": digest(output_path)},
        "data": {"path": data_path.name, "sha256": digest(data_path)},
        "preserved_original_files": {
            path.relative_to(ROOT).as_posix(): value for path, value in protected.items()
        },
    }
    manifest_path = output_path.parent / "topology_manifest.json"
    manifest_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    return {
        "view": str(output_path),
        "manifest": str(manifest_path),
        "node_count": 2,
        "edge_count": 3,
        "interior_vertex_count": 4,
        "raw_graph_changed": False,
        "gt_used": False,
        "protected_original_file_count": len(protected),
        "view_sha256": digest(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-config", type=Path, default=ROOT / PIPELINE_RELATIVE)
    parser.add_argument("--motion-manifest", type=Path, default=ROOT / MOTION_RELATIVE)
    parser.add_argument("--output", type=Path, default=OUT / "view.html")
    args = parser.parse_args()
    print(json.dumps(build_topology(args.pipeline_config, args.motion_manifest, args.output)))


if __name__ == "__main__":
    main()
