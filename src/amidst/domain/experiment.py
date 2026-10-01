"""Versioned experiment and input-reference contracts, with no inference truth geometry."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from amidst.domain.common import DomainModel
from amidst.domain.stream import AggregationPolicy

Version = Annotated[str, Field(min_length=1)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ArtifactReference(DomainModel):
    """Local path resolved relative to its containing manifest/config file."""

    path: str = Field(min_length=1)
    sha256: Digest

    @model_validator(mode="after")
    def local_file_reference(self) -> Self:
        if "\x00" in self.path or "://" in self.path:
            raise ValueError("artifact references must be local file paths")
        return self


class DatasetCase(DomainModel):
    case_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    spatial_context_id: str = Field(min_length=1)
    source_asset_sha256: Digest | None = None
    pipeline: ArtifactReference
    frames: ArtifactReference
    # Reference metadata only; providers never open these files.
    evaluation_references: tuple[ArtifactReference, ...] = ()
    camera_calibration: ArtifactReference | None = None


class DatasetManifest(DomainModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: str = Field(min_length=1)
    dataset_version: Version
    seed: int
    scene_version: Version
    camera_config_version: Version
    topology_version: Version
    provider_kind: Literal["MOCK_JSON", "BLENDER_SYNTHETIC_JSON"]
    data_kind: Literal["SYNTHETIC"] = "SYNTHETIC"
    cases: tuple[DatasetCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_case_identifiers(self) -> Self:
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("dataset case identities must be unique")
        return self


class ExperimentConfig(DomainModel):
    schema_version: Literal["1.0"] = "1.0"
    experiment_id: str = Field(min_length=1)
    dataset_version: Version
    seed: int
    scene_version: Version
    camera_config_version: Version
    topology_version: Version
    metric_config_version: Version
    pipeline_version: Version
    aggregation_policy: AggregationPolicy = AggregationPolicy()
    dataset_manifest: ArtifactReference
    metric_config: ArtifactReference
    record_rerun: bool = Field(default=False, strict=True)
    debug_ground_truth: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def debug_requires_recording(self) -> Self:
        if self.debug_ground_truth and not self.record_rerun:
            raise ValueError("debug_ground_truth requires Rerun recording")
        return self


class InputFingerprint(DomainModel):
    logical_id: str = Field(min_length=1)
    sha256: Digest
    size_bytes: int = Field(ge=0)


class GitRevision(DomainModel):
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    tracked_dirty: bool
    tracked_diff_sha256: Digest
    untracked_source_fingerprints: tuple[InputFingerprint, ...] = ()
    environment_lock_sha256: Digest
    python_version: str
    pipeline_version: str


class ExperimentRecord(DomainModel):
    """Replay identity; runtime/log metadata is deliberately stored separately."""

    config: ExperimentConfig
    dataset: DatasetManifest
    git: GitRevision
    config_sha256: Digest
    inputs: tuple[InputFingerprint, ...]
