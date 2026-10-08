"""Server-owned run/mode/stage binding and content-bound inference freeze."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, Field

from amidst.domain.common import DomainModel

Mode = Literal["photos_only", "photos_plus_observations"]
Stage = Literal["INPUT", "RESULTS"]
Tool = Literal[
    "resolve_place", "list_cameras", "query_observations", "query_events",
    "get_event_summary", "get_event_detail", "get_media", "get_replay",
]
TOOLS: tuple[Tool, ...] = (
    "resolve_place", "list_cameras", "query_observations", "query_events",
    "get_event_summary", "get_event_detail", "get_media", "get_replay",
)
Sha = str


def digest(value: object) -> str:
    """Portable canonical JSON digest; locators are never part of public contexts."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


class RunBinding(DomainModel):
    place_id: str
    model_id: str
    model_revision: str
    source_ref: str
    spatial_context_id: str
    run_id: str
    clock_id: str
    observation_mode: Mode
    registry_version: str = "simulation.registry.v1"
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FreezeReceipt(DomainModel):
    schema_version: Literal["simulation.freeze.v1"] = "simulation.freeze.v1"
    binding: RunBinding
    inference_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    measurement_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def create(cls, binding: RunBinding, inference: object, measurements: object) -> FreezeReceipt:
        payload = {
            "schema_version": "simulation.freeze.v1", "binding": binding.model_dump(mode="json"),
            "inference_sha256": digest(inference), "measurement_sha256": digest(measurements),
        }
        return cls.model_validate(payload | {"receipt_sha256": digest(payload)})

    def verify(self, binding: RunBinding, inference: object, measurements: object) -> bool:
        return self == self.create(binding, inference, measurements)


class TaskContext(DomainModel):
    session_ref: str
    place_id: str
    model_id: str
    model_revision: str
    source_ref: str
    spatial_context_id: str
    run_id: str
    clock_id: str
    observation_mode: Mode
    decision_stage: Stage
    registry_version: str
    resource_refs: tuple[str, ...]
    allowed_tools: tuple[Tool, ...]
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["CONFIGURED_ENGINEERING_ONLY"] = "CONFIGURED_ENGINEERING_ONLY"
    freeze_ref: str | None = None


class AccessDenied(ValueError):
    """Safe fixed-message boundary error, independent of caller-supplied payload."""


class SessionGuard:
    """Callers cannot set the mode or promote the stage through query parameters."""

    def __init__(self, binding: RunBinding) -> None:
        self.binding = RunBinding.model_validate(binding.model_dump())
        self.session_ref = "session-" + digest(self.binding)[:24]
        self._stage: Stage = "INPUT"
        self._freeze: FreezeReceipt | None = None

    @property
    def stage(self) -> Stage:
        return self._stage

    def freeze(self, receipt: FreezeReceipt, inference: object, measurements: object) -> None:
        if not receipt.verify(self.binding, inference, measurements):
            raise AccessDenied("FREEZE_BINDING_MISMATCH")
        self._freeze = receipt
        self._stage = "RESULTS"

    def require(self, session_ref: str, tool: Tool) -> None:
        if session_ref != self.session_ref:
            raise AccessDenied("SCOPE_DENIED")
        if tool not in self.allowed_tools():
            raise AccessDenied("STAGE_DENIED")

    def allowed_tools(self) -> tuple[Tool, ...]:
        if self._stage == "RESULTS":
            return TOOLS
        tools: tuple[Tool, ...] = ("resolve_place", "list_cameras", "get_media")
        if self.binding.observation_mode == "photos_plus_observations":
            tools += ("query_observations",)
        return tools

    def context(self, resources: tuple[str, ...]) -> TaskContext:
        binding = self.binding
        return TaskContext(
            session_ref=self.session_ref, place_id=binding.place_id, model_id=binding.model_id,
            model_revision=binding.model_revision, source_ref=binding.source_ref,
            spatial_context_id=binding.spatial_context_id, run_id=binding.run_id,
            clock_id=binding.clock_id, observation_mode=binding.observation_mode,
            decision_stage=self._stage, registry_version=binding.registry_version,
            resource_refs=resources, allowed_tools=self.allowed_tools(),
            freeze_ref=None if self._freeze is None else "freeze-" + self._freeze.receipt_sha256,
        )
