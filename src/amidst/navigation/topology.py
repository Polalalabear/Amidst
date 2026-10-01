"""Stable directed camera-topology queries."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from pydantic import ValidationError

from amidst.domain.topology import (
    CameraTopologyConfig,
    CameraTopologyNode,
    CameraTransition,
)


class TopologyFailure(StrEnum):
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    UNKNOWN_CAMERA = "UNKNOWN_CAMERA"


class TopologyError(ValueError):
    def __init__(self, failure: TopologyFailure, message: str) -> None:
        super().__init__(message)
        self.failure = failure


class CameraTopologyGraph:
    def __init__(self, config: CameraTopologyConfig) -> None:
        try:
            validated = CameraTopologyConfig.model_validate(config.model_dump(mode="python"))
        except ValidationError as error:
            raise TopologyError(
                TopologyFailure.INVALID_CONFIGURATION,
                "camera topology does not satisfy its domain contract",
            ) from error
        nodes = {node.camera_id: node for node in validated.nodes}
        outgoing: dict[str, list[CameraTransition]] = {camera_id: [] for camera_id in nodes}
        for transition in validated.transitions:
            outgoing[transition.from_camera_id].append(transition)
        self.config = validated
        self._nodes: Mapping[str, CameraTopologyNode] = MappingProxyType(nodes)
        self._outgoing: Mapping[str, tuple[CameraTransition, ...]] = MappingProxyType(
            {
                camera_id: tuple(
                    sorted(camera_transitions, key=lambda transition: transition.transition_id)
                )
                for camera_id, camera_transitions in outgoing.items()
            }
        )

    def node(self, camera_id: str) -> CameraTopologyNode:
        try:
            return self._nodes[camera_id]
        except KeyError as error:
            raise TopologyError(
                TopologyFailure.UNKNOWN_CAMERA, f"unknown topology camera: {camera_id}"
            ) from error

    def outgoing_transitions(self, camera_id: str) -> tuple[CameraTransition, ...]:
        self.node(camera_id)
        return self._outgoing[camera_id]
