"""Small declarative fake graphs shared only by boundary regression tests.

Every node declares its camera/floor, every edge declares its complete geometry,
and authorized=false explicitly keeps an edge outside Camera Topology. This
adapter builds existing production schemas; it adds no inference behavior.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from amidst.domain.pipeline import InferenceInput
from amidst.domain.trajectory import Event, ReconstructionResult
from amidst.pipeline import reconstruct_input

GRAPH_CASES_PATH = Path(__file__).resolve().parents[2] / "data/mock/boundary/graph_cases.json"


def graph_manifest() -> dict[str, Any]:
    return json.loads(GRAPH_CASES_PATH.read_text(encoding="utf-8"))


def graph_case_spec(case_id: str) -> dict[str, Any]:
    return next(case for case in graph_manifest()["scenarios"] if case["id"] == case_id)


def load_graph_case(case_id: str) -> InferenceInput:
    """Convert a readable fixture description to the existing inference contract."""
    spec = graph_case_spec(case_id)
    source = spec["input"]
    nodes = {node["id"]: node for node in source["nodes"]}
    graph_id = f"boundary:{case_id}"
    edges = []
    transitions = []
    for edge in source["edges"]:
        start, end = nodes[edge["from"]], nodes[edge["to"]]
        edges.append({
            "edge_id": edge["id"],
            "from_node_id": start["id"],
            "to_node_id": end["id"],
            "polyline": [start["position"], *edge.get("via", []), end["position"]],
        })
        if edge.get("authorized", True):
            transitions.append({
                "transition_id": f"transition:{edge['id']}",
                "from_camera_id": start["camera"],
                "to_camera_id": end["camera"],
                "transition_type": "ADJACENT",
                "navigation_from_node_id": start["id"],
                "navigation_to_node_id": end["id"],
                "navigation_edge_ids": [edge["id"]],
            })

    def endpoint(side: str) -> dict[str, Any]:
        node = nodes[source[f"{side}_node"]]
        timestamp = source[f"{side}_time_s"]
        sample_times = source.get(f"{side}_sample_times_s", [timestamp])
        observation_id = f"boundary:{case_id}:{side}"
        return {
            "observation_id": observation_id,
            "target_id": "SYNTHETIC_TEST_FIXTURE_TARGET",
            "camera_id": node["camera"],
            "floor_id": node["floor"],
            "start_time": min(sample_times),
            "end_time": max(sample_times),
            "provenance": "PROJECTED",
            "projected_path": [{
                "point_id": f"{observation_id}:point:{index}",
                "observation_id": observation_id,
                "camera_id": node["camera"],
                "plane_id": f"SYNTHETIC_TEST_FIXTURE:{node['floor']}",
                "floor_id": node["floor"],
                "timestamp": sample_time,
                "world_position": node["position"],
            } for index, sample_time in enumerate(sample_times)],
        }

    binding = {
        "spatial_context_id": "SYNTHETIC_TEST_FIXTURE_BOUNDARY",
        "data_kind": "SYNTHETIC_TEST_FIXTURE",
    }
    return InferenceInput.model_validate({
        "dataset_id": graph_id,
        "data_kind": "SYNTHETIC",
        "random_seed": 0,
        "start_observation": endpoint("start"),
        "end_observation": endpoint("end"),
        "navigation": {
            **binding,
            "graph_id": graph_id,
            "nodes": [{
                "node_id": node["id"],
                "position": node["position"],
                "floor_id": node["floor"],
            } for node in nodes.values()],
            "edges": edges,
        },
        "topology": {
            **binding,
            "topology_id": f"{graph_id}:topology",
            "navigation_graph_id": graph_id,
            "nodes": [{
                "camera_id": node["camera"], "floor_id": node["floor"],
            } for node in nodes.values()],
            "transitions": transitions,
        },
        "movement": {"max_speed_m_s": source["max_speed_m_s"]},
        "search_policy": source["search_policy"],
    })


def infer_graph_case(case_id: str) -> tuple[ReconstructionResult, Event]:
    """Use a fresh fixed clock per invocation, including timeout fixtures."""
    source = graph_case_spec(case_id)["input"]
    times = iter(source.get("clock_values_s", []))
    clock: Callable[[], float] = (
        (lambda: next(times)) if source.get("clock_values_s") else (lambda: 0.0)
    )
    return reconstruct_input(
        load_graph_case(case_id), max_paths=source["requested_k"], clock=clock,
    )
