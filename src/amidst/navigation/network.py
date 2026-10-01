"""Cross-validation between camera topology and walkable navigation geometry."""

from __future__ import annotations

from amidst.domain.navigation import NavigationTransitionType
from amidst.domain.topology import CameraTransitionType
from amidst.navigation.graph import NavigationError, NavigationFailure, NavigationGraph
from amidst.navigation.topology import CameraTopologyGraph


class NavigationNetwork:
    def __init__(self, navigation: NavigationGraph, topology: CameraTopologyGraph) -> None:
        if navigation.config.data_kind != topology.config.data_kind:
            raise NavigationError(
                NavigationFailure.INVALID_CONFIGURATION,
                "topology and navigation data kinds must match",
            )
        if navigation.config.graph_id != topology.config.navigation_graph_id:
            raise NavigationError(
                NavigationFailure.INVALID_CONFIGURATION,
                "topology must reference the same navigation graph",
            )
        if navigation.config.spatial_context_id != topology.config.spatial_context_id:
            raise NavigationError(
                NavigationFailure.INVALID_CONFIGURATION,
                "topology and navigation spatial contexts must match",
            )
        if navigation.config.source_asset_sha256 != topology.config.source_asset_sha256:
            raise NavigationError(
                NavigationFailure.INVALID_CONFIGURATION,
                "topology and navigation source asset bindings must match",
            )
        for transition in topology.config.transitions:
            try:
                nav_start = navigation.node(transition.navigation_from_node_id)
                nav_end = navigation.node(transition.navigation_to_node_id)
            except NavigationError as error:
                raise NavigationError(
                    NavigationFailure.INVALID_CONFIGURATION,
                    "camera transition references an unknown navigation node",
                ) from error
            camera_start = topology.node(transition.from_camera_id)
            camera_end = topology.node(transition.to_camera_id)
            if (
                nav_start.floor_id != camera_start.floor_id
                or nav_end.floor_id != camera_end.floor_id
            ):
                raise NavigationError(
                    NavigationFailure.INVALID_CONFIGURATION,
                    "camera transition navigation anchors must match camera floors",
                )
            try:
                route = navigation.path_from_edge_ids(
                    nav_start.node_id, transition.navigation_edge_ids
                )
            except NavigationError as error:
                raise NavigationError(
                    NavigationFailure.INVALID_CONFIGURATION,
                    "camera transition references an invalid walkable path",
                ) from error
            if route.node_ids[-1] != nav_end.node_id:
                raise NavigationError(
                    NavigationFailure.INVALID_CONFIGURATION,
                    "camera transition path does not end at its declared navigation anchor",
                )
            stair_up = NavigationTransitionType.STAIR_UP in route.transition_types
            stair_down = NavigationTransitionType.STAIR_DOWN in route.transition_types
            if transition.transition_type == CameraTransitionType.STAIR_UP:
                if not stair_up or stair_down or nav_end.position[2] <= nav_start.position[2]:
                    raise NavigationError(
                        NavigationFailure.INVALID_CONFIGURATION,
                        "STAIR_UP camera transition requires a matching ascending route",
                    )
            elif transition.transition_type == CameraTransitionType.STAIR_DOWN:
                if not stair_down or stair_up or nav_end.position[2] >= nav_start.position[2]:
                    raise NavigationError(
                        NavigationFailure.INVALID_CONFIGURATION,
                        "STAIR_DOWN camera transition requires a matching descending route",
                    )
            elif stair_up or stair_down:
                raise NavigationError(
                    NavigationFailure.INVALID_CONFIGURATION,
                    "same-floor camera transition cannot depend on a stair route",
                )
        self.navigation = navigation
        self.topology = topology
