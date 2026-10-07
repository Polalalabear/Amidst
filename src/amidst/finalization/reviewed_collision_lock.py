"""Opaque, source-bound known-collider lineage around the unchanged V2 lock.

The extension does not grant new geometry authority or expose reference values.
Its consumers must still load the existing purpose-gated physical provider.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from amidst.domain.common import DomainModel
from amidst.finalization.route_inventory import ReviewedCaseInferenceLockV2
from amidst.obstacle_volume_authority import content_sha256
from amidst.scene_geometry import Digest


class ReviewedKnownCollisionBinding(DomainModel):
    context_path: str = Field(min_length=1)
    physical_manifest_file_sha256: Digest
    source_sha256: Digest
    scope_ids: tuple[str, ...] = Field(min_length=1)
    purpose: Literal["KNOWN_COLLISION_PRUNING"] = "KNOWN_COLLISION_PRUNING"
    coverage: Literal["PARTIAL_KNOWN_COLLIDERS"] = "PARTIAL_KNOWN_COLLIDERS"
    new_semantic_authority_granted: Literal[False] = False
    complete_school_collision_claimed: Literal[False] = False

    @model_validator(mode="after")
    def bounded_binding(self) -> Self:
        path = Path(self.context_path)
        if path.is_absolute() or ".." in path.parts or any(
            part.lower() in {"evaluation", "ground_truth", "simulation", ".git"}
            for part in path.parts
        ):
            raise ValueError("collision context must be a safe public repository-relative input")
        if len(set(self.scope_ids)) != len(self.scope_ids) or any(
            not identity.strip() for identity in self.scope_ids
        ):
            raise ValueError("collision scope identities must be nonblank and unique")
        return self


class ReviewedCollisionInferenceLock(DomainModel):
    schema_version: Literal["phase1-reviewed-case-inference-lock-v3"]
    base_inference_lock: ReviewedCaseInferenceLockV2
    base_inference_lock_file_sha256: Digest
    base_inference_lock_content_sha256: Digest
    known_collision: ReviewedKnownCollisionBinding
    status: Literal["FROZEN_BEFORE_NEW_EXPORT_AND_INFERENCE"]
    original_hr01_hr04_profiles_modified: Literal[False] = False
    old_outputs_relabelled_or_overwritten: Literal[False] = False

    @model_validator(mode="after")
    def preserve_base(self) -> Self:
        if content_sha256(self.base_inference_lock.model_dump(mode="json")) != (
            self.base_inference_lock_content_sha256
        ):
            raise ValueError("collision extension changed its frozen V2 base")
        if self.known_collision.source_sha256 != (
            self.base_inference_lock.base_inference_config.source_sha256
        ):
            raise ValueError("collision extension source differs from inference authority")
        return self


class FrozenReviewedCollisionBinding(DomainModel):
    schema_version: Literal["phase1-reviewed-inference-collision-binding-v1"]
    inference_lock_file_sha256: Digest
    inference_lock_content_sha256: Digest
    binding: ReviewedKnownCollisionBinding
    consumer: dict[str, Any]
    domain_body_guard_retained_for_all_variants: Literal[True]
    independent_evaluation_collision_checks_retained: Literal[True]
    ground_truth_read: Literal[False]


def load_reviewed_collision_lock(
    path: Path, *, repo_root: Path,
) -> ReviewedCollisionInferenceLock:
    """Verify exact V2 ancestry; the consumer separately verifies physical inputs."""
    lock = ReviewedCollisionInferenceLock.model_validate_json(path.read_bytes())
    historical = repo_root / "configs/finalization/reviewed_case_inference_lock_v2.json"
    raw = historical.read_bytes()
    if hashlib.sha256(raw).hexdigest() != lock.base_inference_lock_file_sha256 or (
        json.loads(raw) != lock.base_inference_lock.model_dump(mode="json")
    ):
        raise ValueError("collision extension does not preserve the original V2 lock bytes")
    context = (repo_root / lock.known_collision.context_path).resolve()
    if not context.is_relative_to(repo_root.resolve()):
        raise ValueError("collision context escapes repository through a symlink")
    return lock


def load_frozen_collision_binding(
    directory: Path, freeze: Mapping[str, Any], *, repo_root: Path,
    expected_source_sha256: str,
) -> FrozenReviewedCollisionBinding:
    """Reconstruct lineage from the exact strict lock frozen alongside inference."""
    artifacts = freeze["artifacts"]
    for name in ("collision_authority.json", "collision_inference_lock.json"):
        path = directory / name
        if name not in artifacts or (
            hashlib.sha256(path.read_bytes()).hexdigest() != artifacts[name]
        ):
            raise ValueError("collision lineage is absent or differs from inference freeze")
    document = FrozenReviewedCollisionBinding.model_validate_json(
        (directory / "collision_authority.json").read_bytes(),
    )
    lock_path = directory / "collision_inference_lock.json"
    lock = load_reviewed_collision_lock(lock_path, repo_root=repo_root)
    if (
        hashlib.sha256(lock_path.read_bytes()).hexdigest() != freeze["config_sha256"]
        or document.inference_lock_file_sha256 != freeze["config_sha256"]
        or document.inference_lock_content_sha256 != content_sha256(
            lock.model_dump(mode="json"),
        )
        or document.binding != lock.known_collision
        or document.binding.source_sha256 != expected_source_sha256
    ):
        raise ValueError("evaluation collision binding differs from the exact frozen config/source")
    return document
