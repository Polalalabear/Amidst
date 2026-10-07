"""Versioned source-only new-scope preparation, preview, human application and load.

Example (all paths are explicit, and each output directory must be new)::

    python -m amidst.finalization.scoped_authority_cli prepare \
        --discovery source_supported_proposal.json --scope-id corridor-island-v1 \
        --floor original_floor.json --surface-semantics proposed_semantics.json \
        --pins independently_pinned_inputs.json --source school_v3.blend \
        --evidence source_evidence.json.gz --runtime physical_policy_runtime.json \
        --numerics physical_collision_numerics.json --output new_review_packet

Preview and apply use --proposal; apply also needs --decision and independent
--expected-proposal-sha256/--expected-decision-sha256. There is no approve command.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from amidst.finalization.scoped_authority import (
    BoundedSurfaceSemantics,
    ScopeAuthorityPins,
    ScopeCameraLandmarkBinding,
    ScopeHumanDecision,
    ScopeProposal,
    ScopeUnionCertificate,
    apply_scope_approval,
    load_scoped_authority,
    preview_scope_numeric,
    proposal_from_source_discovery,
    validate_scope_proposal,
)
from amidst.obstacle_volume_authority import content_sha256
from amidst.physical_collision import CollisionNumerics
from amidst.physical_policy_contract import load_physical_policy_contract
from amidst.scene_geometry import FloorAuthority


def _read(path: Path) -> Any:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write(path: Path, payload: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def _proposed_semantics(
    document: Any,
) -> BoundedSurfaceSemantics | dict[
    str, BoundedSurfaceSemantics | tuple[BoundedSurfaceSemantics, ...] | None,
]:
    if isinstance(document, dict) and "profiles_by_cell_index" in document:
        if set(document) != {"profiles_by_cell_index"} or not isinstance(
            document["profiles_by_cell_index"], dict,
        ):
            raise ValueError("per-cell profile file requires only profiles_by_cell_index mapping")
        profiles: dict[
            str, BoundedSurfaceSemantics | tuple[BoundedSurfaceSemantics, ...] | None,
        ] = {}
        for key, value in document["profiles_by_cell_index"].items():
            if isinstance(value, list):
                profiles[key] = tuple(BoundedSurfaceSemantics.model_validate_json(json.dumps(p))
                                      for p in value)
            else:
                profiles[key] = None if value is None else (
                    BoundedSurfaceSemantics.model_validate_json(json.dumps(value))
                )
        return profiles
    return BoundedSurfaceSemantics.model_validate_json(json.dumps(document))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "inspect", "preview", "apply", "verify"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--numerics", type=Path, required=True)
    parser.add_argument("--pins", type=Path, required=True,
                        help="independent original approvals, never extracted from proposal")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--discovery", type=Path)
    parser.add_argument("--scope-id")
    parser.add_argument("--floor", type=Path)
    parser.add_argument("--surface-semantics", type=Path)
    parser.add_argument("--camera-bindings", type=Path)
    parser.add_argument("--camera-export", type=Path)
    parser.add_argument("--proposal", type=Path)
    parser.add_argument("--decision", type=Path)
    parser.add_argument("--certificate", type=Path)
    parser.add_argument("--expected-proposal-sha256")
    parser.add_argument("--expected-decision-sha256")
    parser.add_argument("--expected-certificate-sha256")
    args = parser.parse_args(argv)
    for name, path in vars(args).items():
        if name != "output" and isinstance(path, Path) and any(
            part.lower() in {"evaluation", "ground_truth", "simulation"} for part in path.parts
        ):
            parser.error("new scope authority inputs must come from the source-only partition")
    if args.output.exists():
        parser.error("output must be a fresh versioned directory; existing bytes are preserved")
    if args.stage == "prepare" and not all((
        args.discovery, args.scope_id, args.floor, args.surface_semantics,
    )):
        parser.error(
            "prepare needs discovery, scope-id, original floor and explicit proposed semantics",
        )
    if args.stage != "prepare" and args.proposal is None:
        parser.error("this stage requires --proposal")
    if args.stage in ("apply", "verify") and not all((
        args.decision, args.expected_proposal_sha256, args.expected_decision_sha256,
    )):
        parser.error(
            "apply/verify need human receipt and independently supplied proposal/decision hashes",
        )
    if args.stage == "verify" and not all((args.certificate, args.expected_certificate_sha256)):
        parser.error("verify requires certificate and independent certificate hash")

    pins = ScopeAuthorityPins.model_validate_json(json.dumps(_read(args.pins)))
    if _file_sha256(args.source) != pins.source_sha256:
        raise ValueError("actual preserved source bytes differ from original source approval")
    evidence = _read(args.evidence)
    contract = load_physical_policy_contract(args.runtime)
    numerics = CollisionNumerics.model_validate_json(json.dumps(_read(args.numerics)))
    camera_export = None if args.camera_export is None else _read(args.camera_export)
    if args.stage == "prepare":
        camera_bindings = () if args.camera_bindings is None else tuple(
            ScopeCameraLandmarkBinding.model_validate_json(json.dumps(value))
            for value in _read(args.camera_bindings)
        )
        proposal = proposal_from_source_discovery(
            _read(args.discovery), evidence, scope_id=args.scope_id, pins=pins,
            floor=FloorAuthority.model_validate_json(json.dumps(_read(args.floor))),
            proposed_surface_semantics=_proposed_semantics(_read(args.surface_semantics)),
            camera_landmark_bindings=camera_bindings,
        )
    else:
        proposal = ScopeProposal.model_validate_json(json.dumps(_read(args.proposal)))
    proposal_hash = content_sha256(proposal.model_dump(mode="json"))
    validate_scope_proposal(proposal, evidence, contract, numerics, expected_pins=pins,
                            camera_export=camera_export)
    documents: dict[str, Any] = {"proposal.json": proposal.model_dump(mode="json")}
    if args.stage == "prepare":
        # A template is deliberately blocked and never constitutes approval.
        pending = ScopeHumanDecision(
            proposal_content_sha256=proposal_hash, decision="PENDING",
            approval_origin="DIRECT_HUMAN_DECISION", reviewer_id="PENDING_HUMAN_REVIEW",
            human_approval_id="PENDING_NO_APPROVAL_EXISTS",
            decision_timestamp=datetime.now(UTC),
            direct_human_decision_text="PENDING: no direct human decision has been supplied.",
        )
        documents["decision_template.json"] = pending.model_dump(mode="json")
        result: dict[str, Any] = {
            "status": "HUMAN_REVIEW", "proposal_content_sha256": proposal_hash,
            "new_human_approval_exists": False, "authority_applied": False,
            "formal_execution_enabled": False,
            "required_human_semantics": [
                "EXACT_BOUND_CONTACT_PERMISSION_FOR_NAMED_SOURCE_SUPPORT_FACES",
                "SURFACE_ONLY_COMPONENT_INTERIOR_AND_EXACT_ZERO_AREA_SEAMS_IN_PROPOSED_GUARDS",
                "EXACT_BOUND_SOURCE_OBSTACLE_SURFACE_OWNERSHIP_WITHOUT_SOLID_INTERIOR_UPGRADE",
                "SOURCE_FACE_MOVEMENT_OBSTACLE_OWNERSHIP_IN_EACH_EXPLICIT_PROPOSED_BOUND"
                if any(b.source_face_movement_obstacle_bounds_bu is not None
                       for b in proposal.obstacle_bindings)
                else "OBSTACLE_OWNERSHIP_REMAINS_WITHIN_EXISTING_PROPOSED_GUARDS_AND_UNION_ONLY",
                "SOURCE_CALIBRATION_AND_SAME_XY_LANDMARK_BINDING" if camera_bindings
                else "PROJECTION_AUTHORITY_NOT_REQUESTED_PHYSICAL_SCOPE_ONLY",
            ], "numeric_certification": "NOT_RUN", "case_readiness": "NOT_RUN",
            "proposed_source_face_movement_obstacle_ownership": [
                {"binding_id": b.binding_id,
                 "binding_content_sha256": content_sha256(b.model_dump(mode="json")),
                 "bounds_bu": b.source_face_movement_obstacle_bounds_bu,
                 "whole_object_approved": False, "solid_interior_approved": False}
                for b in proposal.obstacle_bindings
                if b.source_face_movement_obstacle_bounds_bu is not None
            ],
        }
    elif args.stage == "inspect":
        result = {"status": "VALID_SOURCE_BOUND_PROPOSAL_PENDING_HUMAN_REVIEW",
                  "proposal_content_sha256": proposal_hash, "formal_execution_enabled": False}
    elif args.stage == "preview":
        result = preview_scope_numeric(proposal, evidence, contract, numerics,
                                       expected_pins=pins, camera_export=camera_export)
    else:
        decision = ScopeHumanDecision.model_validate_json(json.dumps(_read(args.decision)))
        if args.stage == "apply":
            certificate, result = apply_scope_approval(
                proposal, decision, evidence, contract, numerics, expected_pins=pins,
                expected_proposal_content_sha256=args.expected_proposal_sha256,
                expected_decision_content_sha256=args.expected_decision_sha256,
                camera_export=camera_export,
            )
            if certificate is not None:
                documents["certificate.json"] = certificate.model_dump(mode="json")
        else:
            certificate = ScopeUnionCertificate.model_validate_json(
                json.dumps(_read(args.certificate)),
            )
            if certificate.proposal_content_sha256 != args.expected_proposal_sha256 or (
                certificate.human_decision_content_sha256 != args.expected_decision_sha256
            ):
                raise ValueError("verify independent original proposal/human receipt mismatch")
            load_scoped_authority(
                proposal, decision, certificate, evidence, contract, numerics, expected_pins=pins,
                expected_certificate_content_sha256=args.expected_certificate_sha256,
                camera_export=camera_export,
            )
            result = {"status": "PASS_LOCAL_UNION_REGENERATED", "case_readiness": "NOT_RUN",
                      "formal_execution_enabled": False}
        documents["human_decision.json"] = decision.model_dump(mode="json")
    documents["result.json"] = result
    args.output.mkdir(parents=True, exist_ok=False)
    for name, document in documents.items():
        _write(args.output / name, document)
    inputs = {
        name: {"file_sha256": _file_sha256(path), "bytes": path.stat().st_size}
        for name, path in vars(args).items() if isinstance(path, Path) and path.is_file()
    }
    producer = Path(__file__)
    authority_producer = producer.with_name("scoped_authority.py")
    semantic_producer = producer.with_name("scoped_semantic_cells.py")
    _write(args.output / "manifest.json", {
        "schema_version": "phase1-new-local-scope-stage-manifest-v1", "stage": args.stage,
        "status": result["status"], "scope_id": proposal.scope_id,
        "source_sha256": pins.source_sha256, "proposal_content_sha256": proposal_hash,
        "pins": pins.model_dump(mode="json"), "input_files": inputs,
        "producer_files": {p.name: _file_sha256(p)
                           for p in (producer, authority_producer, semantic_producer)},
        "artifacts": {name: _file_sha256(args.output / name) for name in documents},
        "formal_execution_enabled": False, "original_approvals_modified": False,
        "source_geometry_modified": False, "gt_used": False,
    })
    print(json.dumps({"output": str(args.output), "status": result["status"],
                      "proposal_content_sha256": proposal_hash}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
