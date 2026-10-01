"""Directed camera-topology schemas separate from walkable navigation geometry."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from amidst.domain.common import DomainModel
from amidst.domain.navigation import NavigationDataKind


class CameraTransitionType(StrEnum):
    ADJACENT = "ADJACENT"
    OVERLAPPING_FOV = "OVERLAPPING_FOV"
    SAME_ZONE = "SAME_ZONE"
    STAIR_UP = "STAIR_UP"
    STAIR_DOWN = "STAIR_DOWN"


class CameraTopologyNode(DomainModel):
    camera_id: str = Field(min_length=1)
    floor_id: str = Field(min_length=1)
    zone_id: str | None = None


class CameraTransition(DomainModel):
    transition_id: str = Field(min_length=1)
    from_camera_id: str = Field(min_length=1)
    to_camera_id: str = Field(min_length=1)
    transition_type: CameraTransitionType
    navigation_from_node_id: str = Field(min_length=1)
    navigation_to_node_id: str = Field(min_length=1)
    navigation_edge_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def not_a_self_transition(self) -> Self:
        if self.from_camera_id == self.to_camera_id:
            raise ValueError("fixed same-camera transitions are not allowed")
        if len(set(self.navigation_edge_ids)) != len(self.navigation_edge_ids):
            raise ValueError("camera transition navigation edges must be unique")
        return self


class CameraTopologyConfig(DomainModel):
    topology_id: str = Field(min_length=1)
    navigation_graph_id: str = Field(min_length=1)
    spatial_context_id: str = Field(min_length=1)
    data_kind: NavigationDataKind
    source_asset_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    nodes: tuple[CameraTopologyNode, ...] = Field(min_length=1)
    transitions: tuple[CameraTransition, ...] = ()

    @model_validator(mode="after")
    def consistent_topology(self) -> Self:
        if self.data_kind == NavigationDataKind.CONFIGURED and self.source_asset_sha256 is None:
            raise ValueError("CONFIGURED topology requires a source asset SHA-256")
        camera_ids = [node.camera_id for node in self.nodes]
        transition_ids = [transition.transition_id for transition in self.transitions]
        if len(set(camera_ids)) != len(camera_ids):
            raise ValueError("camera topology node identities must be unique")
        if len(set(transition_ids)) != len(transition_ids):
            raise ValueError("camera transition identities must be unique")
        nodes = {node.camera_id: node for node in self.nodes}
        for transition in self.transitions:
            if transition.from_camera_id not in nodes or transition.to_camera_id not in nodes:
                raise ValueError("camera transition endpoint does not exist")
            start, end = nodes[transition.from_camera_id], nodes[transition.to_camera_id]
            crosses_floor = start.floor_id != end.floor_id
            stair = transition.transition_type in {
                CameraTransitionType.STAIR_UP,
                CameraTransitionType.STAIR_DOWN,
            }
            if crosses_floor != stair:
                raise ValueError("cross-floor camera transitions require an explicit stair type")
            if transition.transition_type == CameraTransitionType.SAME_ZONE and (
                start.zone_id is None or start.zone_id != end.zone_id
            ):
                raise ValueError("SAME_ZONE transition requires matching non-null zones")
        return self
