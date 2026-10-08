"""Explicit mock producer and storage selection; production backends remain gated."""

from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from amidst.domain.common import DomainModel
from amidst.domain.experiment import ArtifactReference
from amidst.domain.stream import AggregationPolicy
from amidst.experiments.versioning import read_local_bytes


class ServiceConfig(DomainModel):
    schema_version: Literal["phase2.integration.v1"] = "phase2.integration.v1"
    mode: Literal["MOCK_INTEGRATION_ONLY"] = "MOCK_INTEGRATION_ONLY"
    provider_kind: Literal["MOCK_JSON"] = "MOCK_JSON"
    dataset_manifest: ArtifactReference
    aggregation_policy: AggregationPolicy = AggregationPolicy()
    repository_kind: Literal["MEMORY", "LOCAL_JSON", "POSTGRESQL"] = "MEMORY"
    repository_path: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def local_path_required(self) -> Self:
        if (self.repository_kind == "LOCAL_JSON") != (self.repository_path is not None):
            raise ValueError("repository_path is required only for LOCAL_JSON")
        if self.repository_path is not None and (
            "://" in self.repository_path or "\x00" in self.repository_path
        ):
            raise ValueError("repository_path must be a local file")
        return self


def load_service_config(path: Path) -> ServiceConfig:
    """Relative artifact and local-store paths are resolved by the composition root."""
    return ServiceConfig.model_validate_json(read_local_bytes(path))
