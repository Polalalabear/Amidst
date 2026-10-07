"""Purpose-gated, nonempty source collider bundles for additive reviewed inference.

Each original approved scope remains intact. Combining its consumers is a stable
conjunction of known collision tests, never a new complete free-space authority.
The caller's separate reviewed body/domain provider remains mandatory.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

from amidst.domain.trajectory import Event
from amidst.obstacle_volume_authority import content_sha256
from amidst.physical_authority import (
    PhysicalAuthorityResolution,
    PhysicalPurpose,
    ReadOnlyPhysicalAuthorityProvider,
    canonical_geometry_sha256,
)
from amidst.physical_collision import (
    CollisionNumerics,
    CylinderCollisionConsumer,
    PhysicalPathDecision,
)
from amidst.physical_policy_contract import PhysicalPolicyContract
from amidst.scene_geometry import (
    Authority,
    Coordinate,
    GeometryAuthorityError,
    SceneGeometrySnapshot,
)


def _safe(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts or any(
        part.lower() in {"ground_truth", "evaluation", "simulation"} for part in path.parts
    ):
        raise ValueError("collision authority accepts only public source-bound repository inputs")
    result = (root / path).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError("collision authority path escapes repository")
    return result


def _read(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    value = json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)
    if not isinstance(value, dict):
        raise ValueError("collision authority input must contain a JSON object")
    return value


@dataclass(frozen=True, slots=True)
class _PreparedCollisionSnapshot:
    """Private operation-local consumers built after all original authority gates.

    A public run/evaluation cannot accept this snapshot in place of its bundle.
    Every new operation must validate the current provider again. The validated
    frozen geometry models and core triangle arrays are detached during hydration.
    """

    consumers: tuple[CylinderCollisionConsumer, ...]
    _receipt: dict[str, Any]

    def receipt(self) -> dict[str, Any]:
        return deepcopy(self._receipt)

    def validate(self, polyline_m: tuple[Coordinate, ...]) -> PhysicalPathDecision:
        tested = 0
        for consumer in self.consumers:
            decision = consumer.validate(polyline_m)
            tested += decision.tested_triangles
            if decision.state != "RETAINED":
                return PhysicalPathDecision(decision.state, decision.reasons, tested, False)
        return PhysicalPathDecision("RETAINED", (), tested, False)


@dataclass(frozen=True, slots=True)
class ReviewedCollisionBundle:
    provider: ReadOnlyPhysicalAuthorityProvider
    contract: PhysicalPolicyContract
    numerics: CollisionNumerics
    scope_ids: tuple[str, ...]
    floor_ids: tuple[str, ...]
    expected_geometry_sha256: str
    expected_resolution_content_sha256: str
    manifest_sha256: str
    local_certificate_content_sha256: str
    semantic_receipt_content_sha256: str

    def consumers(self) -> tuple[CylinderCollisionConsumer, ...]:
        """Revalidate original provider gates and build fresh, unmodified core consumers."""
        for digest in (
            self.expected_geometry_sha256, self.expected_resolution_content_sha256,
            self.manifest_sha256, self.local_certificate_content_sha256,
            self.semantic_receipt_content_sha256,
        ):
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise ValueError("reviewed collision authority requires canonical SHA-256 bindings")
        checked = ReadOnlyPhysicalAuthorityProvider(
            self.provider.geometry, self.provider.resolution,
            self.contract.scale.source_asset_sha256, self.expected_geometry_sha256,
        )
        if content_sha256(checked.resolution.model_dump(mode="json")) != (
            self.expected_resolution_content_sha256
        ):
            raise ValueError("reviewed collision resolution content hash mismatch")
        if not self.scope_ids or tuple(sorted(set(self.scope_ids))) != self.scope_ids:
            raise ValueError("reviewed collision scopes must be nonempty, unique and canonical")
        if not self.floor_ids or tuple(sorted(set(self.floor_ids))) != self.floor_ids:
            raise ValueError("reviewed collision floor scope must be explicit and canonical")
        result = []
        for identity in self.scope_ids:
            inputs = checked.require_scope(
                identity, purpose=PhysicalPurpose.KNOWN_COLLISION_PRUNING,
            )
            if not set(inputs.scope.floor_ids) <= set(self.floor_ids):
                raise ValueError("reviewed collision purpose scope exceeds approved local floors")
            if not inputs.colliders:
                raise ValueError("reviewed collision ablation cannot use an empty collider scope")
            if any(surface.semantic_authority != Authority.APPROVED
                   or surface.physical_authority != Authority.APPROVED
                   for surface in inputs.colliders):
                raise ValueError("reviewed collision requires explicit approved collider semantics")
            result.append(CylinderCollisionConsumer(inputs, self.contract, self.numerics))
        return tuple(result)

    def validate_bindings(
        self, *, source_sha256: str, local_certificate_content_sha256: str,
        semantic_receipt_content_sha256: str, floor_ids: tuple[str, ...],
        contract: PhysicalPolicyContract,
    ) -> _PreparedCollisionSnapshot:
        if (
            self.provider.geometry.source_sha256 != source_sha256
            or self.contract != contract
            or self.local_certificate_content_sha256 != local_certificate_content_sha256
            or self.semantic_receipt_content_sha256 != semantic_receipt_content_sha256
            or self.floor_ids != tuple(sorted(set(floor_ids)))
        ):
            raise ValueError(
                "reviewed collision source/policy/local-scope/semantic receipt mismatch",
            )
        return self.prepare()

    def validate(self, polyline_m: tuple[Coordinate, ...]) -> PhysicalPathDecision:
        return self.prepare().validate(polyline_m)

    def receipt(self) -> dict[str, Any]:
        return self.prepare().receipt()

    def prepare(self) -> _PreparedCollisionSnapshot:
        """Revalidate once and retain consumers/receipt only for this operation."""
        consumers = self.consumers()
        colliders = {surface.surface_id for consumer in consumers
                     for surface, _ in consumer.meshes}
        receipt = {
            "schema_version": "phase1-reviewed-collision-consumer-v1",
            "source_sha256": self.provider.geometry.source_sha256,
            "geometry_content_sha256": self.expected_geometry_sha256,
            "physical_authority_content_sha256": self.expected_resolution_content_sha256,
            "manifest_sha256": self.manifest_sha256,
            "purpose": PhysicalPurpose.KNOWN_COLLISION_PRUNING.value,
            "original_approved_scope_ids": self.scope_ids, "floor_ids": self.floor_ids,
            "nonempty_approved_collider_count": len(colliders),
            "local_certificate_content_sha256": self.local_certificate_content_sha256,
            "semantic_receipt_content_sha256": self.semantic_receipt_content_sha256,
            "numerics_content_sha256": content_sha256(self.numerics.model_dump(mode="json")),
            "known_collision_coverage": "PARTIAL",
            "complete_free_space_or_physical_metric_authority": False,
            "body_domain_guard_removed_by_ablation": False,
            "roles_inferred_from_names": False, "ground_truth_read": False,
        }
        return _PreparedCollisionSnapshot(consumers, receipt)


def collision_bundle_from_provider(
    provider: ReadOnlyPhysicalAuthorityProvider, contract: PhysicalPolicyContract,
    numerics: CollisionNumerics, *, floor_ids: tuple[str, ...],
    local_certificate_content_sha256: str, semantic_receipt_content_sha256: str,
    scope_ids: tuple[str, ...] | None = None, manifest_sha256: str,
) -> ReviewedCollisionBundle:
    """Select existing approved purpose scopes without geometry/name-based approval."""
    floor_ids = tuple(sorted(set(floor_ids)))
    selected = tuple(sorted(scope_ids if scope_ids is not None else (
        scope.scope_id for scope in provider.get_scopes(
            purpose=PhysicalPurpose.KNOWN_COLLISION_PRUNING,
        )
        if scope.authority == Authority.APPROVED and set(scope.floor_ids) <= set(floor_ids)
    )))
    if not selected:
        raise GeometryAuthorityError(("NO_APPROVED_NONEMPTY_COLLISION_PRUNING_SCOPE",))
    bundle = ReviewedCollisionBundle(
        provider, contract, CollisionNumerics.model_validate(numerics), selected, floor_ids,
        canonical_geometry_sha256(provider.geometry),
        content_sha256(provider.resolution.model_dump(mode="json")), manifest_sha256,
        local_certificate_content_sha256, semantic_receipt_content_sha256,
    )
    bundle.consumers()
    return bundle


def load_reviewed_collision_bundle(
    context_path: Path, *, repo_root: Path, expected_manifest_sha256: str,
    expected_source_sha256: str, contract: PhysicalPolicyContract, floor_ids: tuple[str, ...],
    local_certificate_content_sha256: str, semantic_receipt_content_sha256: str,
    scope_ids: tuple[str, ...] | None = None,
) -> ReviewedCollisionBundle:
    """Hydration is separate; missing, changed or review-only collider inputs fail closed."""
    context_path = _safe(repo_root, str(context_path.resolve().relative_to(repo_root.resolve())))
    context = _read(context_path)
    manifest_path = _safe(repo_root, context["physical_authority_manifest"])
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_manifest_sha256:
        raise ValueError("reviewed collision manifest SHA-256 mismatch")
    manifest = json.loads(raw)
    if (
        context.get("schema_version") != "school-physical-context-v1"
        or manifest.get("schema_version") != "physical-policy-review-manifest-v1"
        or context["source_sha256"] != expected_source_sha256
        or contract.scale.source_asset_sha256 != expected_source_sha256
        or manifest["source_preserved"] is not True
        or manifest["source_before"] != manifest["source_after"]
        or manifest["source_before"]["sha256"] != expected_source_sha256
        or manifest["summary"]["gt_used"] is not False
    ):
        raise ValueError("reviewed collision manifest/source preservation binding differs")
    geometry_path = _safe(repo_root, context["geometry"])
    resolution_path = _safe(repo_root, context["physical_authority"])
    geometry_doc, resolution_doc = _read(geometry_path), _read(resolution_path)
    for path, doc in ((geometry_path, geometry_doc), (resolution_path, resolution_doc)):
        if content_sha256(doc) != manifest["artifact_content_sha256"][path.name]:
            raise ValueError("reviewed collision source artifact content hash mismatch")
    geometry = SceneGeometrySnapshot.model_validate_json(json.dumps(geometry_doc))
    resolution = PhysicalAuthorityResolution.model_validate_json(json.dumps(resolution_doc))
    provider = ReadOnlyPhysicalAuthorityProvider(
        geometry, resolution, expected_source_sha256, manifest["geometry_model_sha256"],
    )
    numerics_doc = _read(repo_root / "configs/physical_collision_numerics_v1.json")
    if content_sha256(numerics_doc) != (
        manifest["input_content_sha256"]["collision_numerics_config"]
    ):
        raise ValueError("reviewed collision numerical policy hash mismatch")
    return collision_bundle_from_provider(
        provider, contract, CollisionNumerics.model_validate_json(json.dumps(numerics_doc)),
        floor_ids=floor_ids, local_certificate_content_sha256=local_certificate_content_sha256,
        semantic_receipt_content_sha256=semantic_receipt_content_sha256,
        scope_ids=scope_ids, manifest_sha256=expected_manifest_sha256,
    )


def evaluate_reviewed_known_collisions(
    event: Event, bundle: ReviewedCollisionBundle,
) -> dict[str, Any]:
    """Independently test every emitted timed segment, including collision ablations.

    This partial collider measure never replaces complete body/domain evaluation.
    No inference mask is read here: a disabled pruning stage cannot disable it.
    """
    prepared = bundle.prepare()
    consumers = prepared.consumers
    count, rejected, unvalidated, tested = 0, 0, 0, 0
    failures = []
    for hypothesis in event.trajectories:
        for start, end in pairwise(hypothesis.timed_points):
            count += 1
            points = (start.world_position, end.world_position)
            for consumer in consumers:
                decision = consumer.validate(points)
                tested += decision.tested_triangles
                if decision.state != "RETAINED":
                    rejected += decision.state == "REJECTED"
                    unvalidated += decision.state == "UNVALIDATED"
                    failures.append({
                        "hypothesis_id": hypothesis.hypothesis_id,
                        "scope_id": consumer.inputs.scope.scope_id,
                        "state": decision.state, "reasons": decision.reasons,
                    })
                    break
    return {
        "schema_version": "phase1-reviewed-known-collision-evaluation-v1",
        "status": "AVAILABLE" if count and not unvalidated else (
            "N/A_UNVALIDATED_SEGMENTS" if unvalidated else "N/A_NO_TIMED_SEGMENTS"
        ), "authority": prepared.receipt(), "segment_count": count,
        "known_collision_segment_count": rejected, "unvalidated_segment_count": unvalidated,
        "known_collision_rate": rejected / count if count and not unvalidated else None,
        "tested_triangles": tested, "complete_physical_validation": False,
        "inference_ablation_affects_evaluator": False, "failures": failures,
    }
