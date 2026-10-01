"""Swappable producer/service/repository contracts; no Phase 2 implementations."""

from __future__ import annotations

from typing import Protocol

from amidst.domain.common import Vec3
from amidst.domain.evidence import ObservationFrame
from amidst.domain.navigation import NavigationPath
from amidst.domain.observation import Observation, ProjectedPoint
from amidst.domain.topology import CameraTransition
from amidst.domain.trajectory import Event, ReconstructionResult


class ObservationProvider(Protocol):
    def get_observations(
        self, camera_id: str, time_range: tuple[float, float]
    ) -> tuple[Observation, ...]: ...


class ProjectionService(Protocol):
    def project_frame(self, frame: ObservationFrame) -> ProjectedPoint: ...


class NavigationService(Protocol):
    def locate_node(self, position: Vec3, floor_id: str) -> str | None: ...

    def minimum_path(
        self, start_node_id: str, end_node_id: str
    ) -> NavigationPath | None: ...


class CameraTopologyService(Protocol):
    def outgoing_transitions(self, camera_id: str) -> tuple[CameraTransition, ...]: ...

    def minimum_hop_transition_path(
        self, start_camera_id: str, end_camera_id: str
    ) -> tuple[str, ...] | None: ...


class TrajectoryGenerator(Protocol):
    def propose_feasible_trajectories(
        self, start: Observation, end: Observation, max_paths: int = 3
    ) -> ReconstructionResult: ...


class GapReasoner(Protocol):
    def reconstruct(self, event: Event) -> Event: ...


class EventRepository(Protocol):
    def save(self, event: Event) -> None: ...

    def get(self, event_id: str) -> Event | None: ...


class VisualizationAdapter(Protocol):
    def log_event(self, event: Event) -> None: ...
