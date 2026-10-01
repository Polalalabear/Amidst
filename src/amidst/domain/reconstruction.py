"""Deterministic timing policy, separate from the reconstruction algorithm."""

from pydantic import Field

from amidst.domain.common import DomainModel, PositiveFinite
from amidst.domain.trajectory import NonNegativeFinite


class ReconstructionPolicy(DomainModel):
    direct_path_slack_tolerance_s: NonNegativeFinite = 1.0
    endpoint_tolerance_m: PositiveFinite = 1e-6
    include_dwell_hypotheses: bool = Field(default=True, strict=True)
