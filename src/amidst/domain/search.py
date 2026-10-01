"""Hard movement and bounded-search contracts; search algorithms live outside domain."""

from typing import Annotated

from pydantic import Field, FiniteFloat

from amidst.domain.common import DomainModel, PositiveFinite

PositiveCount = Annotated[int, Field(gt=0)]
DetourRatio = Annotated[FiniteFloat, Field(ge=1)]


class MovementConstraints(DomainModel):
    """Physical constraints applied before a trajectory becomes a candidate."""

    max_speed_m_s: PositiveFinite


class GraphSearchPolicy(DomainModel):
    """Finite, deterministic bounds for Phase 1 candidate enumeration."""

    max_candidate_paths: PositiveCount = 3
    max_search_nodes: PositiveCount = 10_000
    max_path_length_m: PositiveFinite = 1_000.0
    max_search_time_s: PositiveFinite = 1.0
    max_branch_factor: PositiveCount = 32
    max_detour_ratio: DetourRatio = 2.0
