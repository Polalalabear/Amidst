"""Producer-independent inference input; no benchmark truth or evaluation fields."""

from typing import Literal, Self

from pydantic import Field, model_validator

from amidst.domain.common import DomainModel
from amidst.domain.navigation import NavigationGraphConfig
from amidst.domain.observation import Observation
from amidst.domain.reconstruction import ReconstructionPolicy
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.topology import CameraTopologyConfig


class InferenceInput(DomainModel):
    dataset_id: str = Field(min_length=1)
    data_kind: Literal["SYNTHETIC"] = "SYNTHETIC"
    random_seed: int
    start_observation: Observation
    end_observation: Observation
    navigation: NavigationGraphConfig
    topology: CameraTopologyConfig
    movement: MovementConstraints
    search_policy: GraphSearchPolicy
    reconstruction_policy: ReconstructionPolicy = ReconstructionPolicy()

    @model_validator(mode="after")
    def consistent_identity(self) -> Self:
        if self.start_observation.target_id != self.end_observation.target_id:
            raise ValueError("inference endpoints must describe the same target")
        return self
