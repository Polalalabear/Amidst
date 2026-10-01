"""Explicit synthetic scenario data, never imported by graph or reconstruction.

The seed is fixed metadata: generation consumes no randomness. Observations
are configured PROJECTED endpoints, not a claim of Blender projection accuracy.
Ground Truth is generated and published separately from inference input.
"""

from __future__ import annotations

import math
from pathlib import Path

from amidst.domain.common import Provenance, Vec3
from amidst.domain.evaluation import AABBObstacle, ConstraintConfig
from amidst.domain.ground_truth import PathKeyframe, TrajectoryConfig
from amidst.domain.navigation import (
    CrossFloorPolicy,
    NavigationDataKind,
    NavigationEdge,
    NavigationGraphConfig,
    NavigationNode,
    NavigationTransitionType,
)
from amidst.domain.observation import Observation, ProjectedPoint
from amidst.domain.pipeline import InferenceInput
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.topology import (
    CameraTopologyConfig,
    CameraTopologyNode,
    CameraTransition,
    CameraTransitionType,
)
from amidst.simulation.ground_truth import sample_trajectory
from amidst.storage.json_files import write_json

SEED = 20261001
SCENARIO_IDS = ("single_path", "branching_top_k", "temporal_slack", "simplified_stair")


def fixture_constraints() -> ConstraintConfig:
    """An explicit synthetic wall clear of authorized routes, not school geometry."""
    return ConstraintConfig(max_speed_m_s=1.0, obstacles=(AABBObstacle(
        obstacle_id="SYNTHETIC_WALL", minimum=(5, 1, -1), maximum=(15, 4, 2),
    ),))


def _observation(scenario: str, name: str, node: NavigationNode, time: float) -> Observation:
    observation_id = f"{scenario}:obs:{name}"
    camera_id = f"CAM_{name}"
    return Observation(
        observation_id=observation_id,
        target_id="synthetic_person_01",
        camera_id=camera_id,
        start_time=time,
        end_time=time,
        floor_id=node.floor_id,
        projected_path=(ProjectedPoint(
            point_id=f"{observation_id}:point",
            observation_id=observation_id,
            camera_id=camera_id,
            plane_id=f"synthetic_plane:{node.floor_id}",
            timestamp=time,
            world_position=node.position,
            floor_id=node.floor_id,
        ),),
        provenance=Provenance.PROJECTED,
    )


def scenario_inputs() -> tuple[InferenceInput, ...]:
    """Build ordinary topology/navigation configs; no mock-specific search rules."""
    results = []
    for scenario in SCENARIO_IDS:
        nodes: tuple[NavigationNode, ...]
        edges: tuple[NavigationEdge, ...]
        routes: tuple[tuple[str, tuple[str, ...]], ...]
        stair = scenario == "simplified_stair"
        gap = {"single_path": 20.0, "branching_top_k": 40.0,
               "temporal_slack": 180.0, "simplified_stair": 7.0}[scenario]
        if stair:
            nodes = (
                NavigationNode(node_id="A", position=(0, 0, 0), floor_id="1F"),
                NavigationNode(node_id="stair_entry", position=(2, 0, 0), floor_id="1F"),
                NavigationNode(node_id="stair_exit", position=(2, 0, 3), floor_id="2F"),
                NavigationNode(node_id="B", position=(4, 0, 3), floor_id="2F"),
            )
            edges = (
                NavigationEdge(edge_id="entry", from_node_id="A",
                               to_node_id="stair_entry", polyline=((0, 0, 0), (2, 0, 0))),
                NavigationEdge(edge_id="stair_path", from_node_id="stair_entry",
                               to_node_id="stair_exit",
                               polyline=((2, 0, 0), (2, 0, 1.5), (2, 0, 3)),
                               transition_type=NavigationTransitionType.STAIR_UP,
                               stair_id="SYNTHETIC_INTERFACE_ONLY"),
                NavigationEdge(edge_id="exit", from_node_id="stair_exit", to_node_id="B",
                               polyline=((2, 0, 3), (4, 0, 3))),
            )
            routes = (("stair", ("entry", "stair_path", "exit")),)
        else:
            nodes = (
                NavigationNode(node_id="A", position=(0, 0, 0), floor_id="1F"),
                NavigationNode(node_id="B", position=(20, 0, 0), floor_id="1F"),
            )
            polylines: list[tuple[str, tuple[Vec3, ...]]] = [
                ("direct", ((0, 0, 0), (20, 0, 0))),
            ]
            if scenario == "branching_top_k":
                polylines.extend([
                    ("upper", ((0, 0, 0), (0, 5, 0), (20, 5, 0), (20, 0, 0))),
                    ("lower", ((0, 0, 0), (0, -10, 0), (20, -10, 0), (20, 0, 0))),
                ])
            if scenario == "temporal_slack":
                polylines.append(("detour", (
                    (0, 0, 0), (0, 10, 0), (20, 10, 0), (20, 0, 0),
                )))
            edges = tuple(NavigationEdge(
                edge_id=name, from_node_id="A", to_node_id="B", polyline=polyline,
            ) for name, polyline in polylines)
            routes = tuple((edge.edge_id, (edge.edge_id,)) for edge in edges)
        navigation = NavigationGraphConfig(
            graph_id=f"{scenario}:walkable", spatial_context_id=f"SYNTHETIC:{scenario}",
            data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
            cross_floor_policy=(CrossFloorPolicy.EXPLICIT_PARAMETERIZED_STAIRS
                                if stair else CrossFloorPolicy.DISCONNECTED),
            nodes=nodes, edges=edges,
        )
        topology = CameraTopologyConfig(
            topology_id=f"{scenario}:cameras", navigation_graph_id=navigation.graph_id,
            spatial_context_id=navigation.spatial_context_id,
            data_kind=navigation.data_kind,
            nodes=(CameraTopologyNode(camera_id="CAM_A", floor_id=nodes[0].floor_id),
                   CameraTopologyNode(camera_id="CAM_B", floor_id=nodes[-1].floor_id)),
            transitions=tuple(CameraTransition(
                transition_id=name, from_camera_id="CAM_A", to_camera_id="CAM_B",
                transition_type=(CameraTransitionType.STAIR_UP
                                 if stair else CameraTransitionType.ADJACENT),
                navigation_from_node_id="A", navigation_to_node_id="B",
                navigation_edge_ids=edge_ids,
            ) for name, edge_ids in routes),
        )
        results.append(InferenceInput(
            dataset_id=scenario, random_seed=SEED,
            start_observation=_observation(scenario, "A", nodes[0], 10.0),
            end_observation=_observation(scenario, "B", nodes[-1], 10.0 + gap),
            navigation=navigation, topology=topology,
            movement=MovementConstraints(max_speed_m_s=1.0),
            search_policy=GraphSearchPolicy(
                max_candidate_paths=3, max_search_nodes=100, max_search_time_s=60.0,
                max_path_length_m=100.0, max_branch_factor=8, max_detour_ratio=3.0,
            ),
        ))
    return tuple(results)


def ground_truth_config(scenario: InferenceInput) -> TrajectoryConfig:
    """Evaluation-only configured truth: choose rank three for the branching case."""
    route_index = 2 if scenario.dataset_id == "branching_top_k" else 0
    transition = scenario.topology.transitions[route_index]
    by_id = {edge.edge_id: edge for edge in scenario.navigation.edges}
    polyline = list(by_id[transition.navigation_edge_ids[0]].polyline)
    for edge_id in transition.navigation_edge_ids[1:]:
        polyline.extend(by_id[edge_id].polyline[1:])
    lengths = [math.dist(a, b) for a, b in zip(polyline, polyline[1:], strict=False)]
    total = math.fsum(lengths)
    elapsed = 0.0
    start = scenario.start_observation.end_time
    gap = scenario.end_observation.start_time - start
    frames = []
    for index, point in enumerate(polyline):
        if index:
            elapsed += lengths[index - 1]
        floor_id = "2F" if point[2] == 3.0 else "1F"
        frames.append(PathKeyframe(
            timestamp=start + gap * elapsed / total, position=point, floor_id=floor_id,
        ))
    return TrajectoryConfig(
        trajectory_id=f"{scenario.dataset_id}:truth", target_id="synthetic_person_01",
        scene_id=scenario.navigation.spatial_context_id, random_seed=SEED,
        sample_rate_hz=1, keyframes=tuple(frames),
    )


def export_scenarios(destination: Path) -> None:
    for scenario in scenario_inputs():
        folder = destination / scenario.dataset_id
        write_json(folder / "inference.json", scenario.model_dump(mode="json"))
        truth = sample_trajectory(ground_truth_config(scenario))
        write_json(folder / "ground_truth.json", truth.model_dump(mode="json"))
    # Preserve the original fixture serialization; metric tolerances are external config.
    write_json(destination / "constraints.json", fixture_constraints().model_dump(
        mode="json", exclude={"collision_tolerance_m", "speed_relative_tolerance"},
    ))
    write_json(destination / "manifest.json", {
        "data_kind": "SYNTHETIC_TEST_FIXTURE", "random_seed": SEED,
        "scenarios": list(SCENARIO_IDS), "coverage_distance": "ADE",
        "coverage_epsilon_m": 1e-6, "k_routes": 3,
        "collision_geometry": "EXPLICIT_AABB_ONLY",
        "school_or_blender_validation": False,
    })
