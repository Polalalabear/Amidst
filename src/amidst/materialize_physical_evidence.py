"""Explicit, source-bound replay of the lightweight physical-policy checkpoint.

This command never downloads evidence. It runs the unchanged historical producers
in an isolated workspace and installs generated blobs only after all bindings and
research results agree with the committed artifact contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from amidst.obstacle_volume_authority import content_sha256
from amidst.physical_policy_validation import read_document, source_fingerprint, write_document

DEFAULT_MANIFEST = Path(
    "data/scene_audit/phase1_physical_policy_approval_20261006/artifact_manifest.json"
)
RAW_FILENAMES = frozenset(
    {
        "source_evidence.json.gz",
        "obstacle_collider_details.json.gz",
        "geometry.json.gz",
        "floor_support_details.json.gz",
    }
)
POLICY_OUTPUTS = frozenset(
    {
        "body_clearance_policy.json",
        "floor_authority_map.json",
        "floor_support_details.json.gz",
        "obstacle_collider_authority.json",
        "obstacle_collider_details.json.gz",
        "portal_clearance.json",
        "stair_authority.json",
        "local_physical_scopes.json",
        "geometry.json.gz",
        "physical_authority.json",
        "collision_pruning_results.json",
        "walkable_clearance_1F.json",
        "walkable_clearance_2F.json",
    }
)


class MaterializationError(ValueError):
    """An explicit prerequisite or immutable evidence binding was not satisfied."""


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _document(path: Path, role: str) -> dict[str, Any]:
    if not path.is_file():
        raise MaterializationError(f"missing prerequisite {role}: {path}")
    try:
        return read_document(path)
    except (ValueError, OSError, EOFError) as exc:
        raise MaterializationError(f"invalid {role}: {path}: {exc}") from exc


def _relative_path(root: Path, filename: Any) -> Path:
    if not isinstance(filename, str) or not filename:
        raise MaterializationError("manifest filename must be a nonempty relative path")
    path = Path(filename)
    if path.is_absolute() or ".." in path.parts:
        raise MaterializationError(f"manifest path must stay within repository: {filename}")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise MaterializationError(f"manifest path resolves outside repository: {filename}")
    return root / path


def load_manifest(path: Path, root: Path) -> dict[str, Any]:
    contract = _document(path, "canonical artifact manifest")
    if contract.get("schema_version") != "physical-evidence-materialization-v1":
        raise MaterializationError("unsupported artifact materialization manifest schema")
    try:
        source = contract["source_scene"]
        producer = contract["producer"]
        artifacts = contract["artifacts"]
        required = (
            source["sha256"],
            source["size"],
            source["original_mtime_ns"],
            producer["commit"],
            producer["file_sha256"],
            producer["blender_version"],
            producer["blender_build_hash"],
            producer["dependency_lock_sha256"],
            contract["historical_manifest"],
            contract["historical_manifest_sha256"],
            contract["full_evidence_commit"],
            contract["expected_research_results"],
        )
        if not required or not isinstance(artifacts, list) or not artifacts:
            raise MaterializationError("artifact manifest requires nonempty artifact records")
        _relative_path(root, source["filename"])
        _relative_path(root, contract["validation_config"])
        names = []
        raw_names = set()
        for artifact in artifacts:
            name = artifact["filename"]
            _relative_path(root, name)
            names.append(name)
            if (
                Path(name).name == "collision_pruning_results.json"
                and "semantic_sha256" not in artifact
            ):
                raise MaterializationError("collision artifact requires runtime-free semantic hash")
            for field in (
                "sha256",
                "content_sha256",
                "source_scene_sha256",
                "generating_command",
                "config",
                "producer_commit",
                "semantic_role",
                "tracked",
            ):
                if field not in artifact:
                    raise MaterializationError(f"artifact record missing {field}: {name}")
            if artifact["source_scene_sha256"] != source["sha256"]:
                raise MaterializationError(f"artifact belongs to a different source scene: {name}")
            if Path(name).name in RAW_FILENAMES:
                raw_names.add(Path(name).name)
                if artifact["tracked"] is not False:
                    raise MaterializationError(f"raw evidence must be untracked: {name}")
        if {Path(name).name for name in names} != POLICY_OUTPUTS | {"source_evidence.json.gz"}:
            raise MaterializationError(
                "manifest must bind the complete physical-policy artifact set"
            )
        if len(names) != len(set(names)):
            raise MaterializationError("artifact manifest contains duplicate filenames")
        if raw_names != RAW_FILENAMES:
            raise MaterializationError(
                "manifest must bind exactly all four generated raw artifacts"
            )
    except (KeyError, TypeError, AttributeError) as exc:
        raise MaterializationError(f"malformed artifact materialization manifest: {exc}") from exc
    return contract


def verify_artifact(path: Path, artifact: dict[str, Any], *, semantic: bool = False) -> str:
    document = _document(path, "physical evidence artifact")
    if semantic and path.name == "collision_pruning_results.json":
        document = {key: value for key, value in document.items() if key != "runtime_seconds"}
        expected = artifact["semantic_sha256"]
    else:
        if file_sha256(path) != artifact["sha256"]:
            raise MaterializationError(f"artifact byte SHA-256 mismatch: {artifact['filename']}")
        expected = artifact["content_sha256"]
    actual = content_sha256(document)
    if actual != expected:
        raise MaterializationError(f"artifact content SHA-256 mismatch: {artifact['filename']}")
    return actual


def verify_bindings(root: Path, contract: dict[str, Any]) -> None:
    for filename, expected in (
        ("uv.lock", contract["producer"]["dependency_lock_sha256"]),
        (contract["historical_manifest"], contract["historical_manifest_sha256"]),
    ):
        path = _relative_path(root, filename)
        if not path.is_file():
            raise MaterializationError(f"missing prerequisite immutable binding: {path}")
        if file_sha256(path) != expected:
            raise MaterializationError(f"immutable binding SHA-256 mismatch: {filename}")
    for filename, expected in contract["producer"]["file_sha256"].items():
        path = _relative_path(root, filename)
        if not path.is_file():
            raise MaterializationError(f"missing prerequisite historical producer: {path}")
        if file_sha256(path) != expected:
            raise MaterializationError(f"historical producer SHA-256 mismatch: {filename}")
    raw_paths = {record["filename"] for record in contract["artifacts"] if not record["tracked"]}
    for category in ("input_content_sha256", "config_content_sha256"):
        for filename, expected in contract.get(category, {}).items():
            if filename in raw_paths:
                continue
            document = _document(_relative_path(root, filename), category)
            if content_sha256(document) != expected:
                raise MaterializationError(f"{category} mismatch: {filename}")
    for artifact in contract["artifacts"]:
        if artifact["tracked"]:
            verify_artifact(_relative_path(root, artifact["filename"]), artifact)


def _source_binding(source: Path, contract: dict[str, Any]) -> dict[str, Any]:
    if not source.is_file():
        raise MaterializationError(
            f"missing external source scene prerequisite: {source}; provide --source-scene "
            "with the preserved scene specified by the manifest (no download is attempted)"
        )
    fingerprint = source_fingerprint(source)
    expected = contract["source_scene"]
    if any(fingerprint[key] != expected[key] for key in ("sha256", "size")):
        raise MaterializationError("external source scene SHA-256 or size differs from manifest")
    return fingerprint


def research_results(output: Path) -> dict[str, Any]:
    body = _document(output / "body_clearance_policy.json", "body clearance summary")
    floor = _document(output / "floor_authority_map.json", "floor authority summary")
    obstacle = _document(output / "obstacle_collider_authority.json", "obstacle summary")
    portal = _document(output / "portal_clearance.json", "portal summary")
    stair = _document(output / "stair_authority.json", "stair summary")
    authority = _document(output / "physical_authority.json", "physical authority summary")
    collision = _document(output / "collision_pruning_results.json", "collision diagnostic")
    return {
        "architectural_scale": body["scale_authority"],
        "physical_policy": body["policy_metres"]["authority"],
        "floor_supported_subdomains": floor["approved_supported_subdomain_count"],
        "obstacle_approved_components": obstacle["approved_component_count"],
        "obstacles_with_approved_components": obstacle["obstacles_with_approved_components"],
        "obstacle_annotation_count": obstacle["obstacle_count"],
        "portal_conflicts": portal["human_review_count"],
        "portal_authority": portal["actual_aperture_authority"],
        "stair_authority": {row["stair_id"]: row["authority"] for row in stair["stairs"]},
        "overall": authority["level"],
        "collision_before": collision["before_count"],
        "collision_after": collision["after_pruning_count"],
    }


def _verify_results(output: Path, contract: dict[str, Any]) -> dict[str, Any]:
    actual = research_results(output)
    if actual != contract["expected_research_results"]:
        raise MaterializationError(f"research-result equivalence failed: {actual}")
    return actual


def _link(workspace: Path, relative: str, target: Path) -> None:
    destination = _relative_path(workspace, relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(target.resolve())


def _run(command: list[str], workspace: Path, *, environment: dict[str, str] | None = None) -> None:
    try:
        subprocess.run(command, cwd=workspace, env=environment, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MaterializationError(
            f"explicit evidence producer failed: {command[0]}: {exc}"
        ) from exc


def _check_blender(blender: Path, producer: dict[str, Any]) -> None:
    try:
        version = subprocess.run(
            [str(blender.resolve()), "--version"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MaterializationError(f"cannot inspect Blender prerequisite: {blender}") from exc
    if producer["blender_version"] not in version or producer["blender_build_hash"] not in version:
        raise MaterializationError("Blender version/build differs from historical producer")


def _workspace(root: Path, workspace: Path, contract: dict[str, Any], source: Path) -> None:
    config_path = contract["validation_config"]
    config = _document(root / config_path, "physical policy validation config")
    atlas_path = config["source_evidence"]
    files = {config_path, config["source_exporter"]}
    files.update(contract["producer"]["file_sha256"])
    files.update(contract.get("input_content_sha256", {}))
    files.update(contract.get("config_content_sha256", {}))
    for filename in sorted(files):
        if filename != atlas_path:
            _link(workspace, filename, root / filename)
    _link(workspace, config["source_blend"], source)
    try:
        git_dir = subprocess.run(
            ["git", "rev-parse", "--absolute-git-dir"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MaterializationError("materialization requires the checkpoint Git checkout") from exc
    (workspace / ".git").write_text(f"gitdir: {git_dir}\n")


def materialize(
    root: Path,
    manifest_path: Path,
    *,
    source_scene: Path | None = None,
    blender: Path | None = None,
    atlas: Path | None = None,
    verify_only: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = manifest_path if manifest_path.is_absolute() else root / manifest_path
    contract = load_manifest(manifest_path, root)
    verify_bindings(root, contract)
    source = (source_scene or (root / contract["source_scene"]["filename"])).resolve()
    before = _source_binding(source, contract)
    records = {Path(record["filename"]).name: record for record in contract["artifacts"]}
    artifact_dir = (root / records["source_evidence.json.gz"]["filename"]).parent
    if verify_only:
        for name in RAW_FILENAMES:
            verify_artifact(root / records[name]["filename"], records[name])
        results = _verify_results(artifact_dir, contract)
        if before != _source_binding(source, contract):
            raise MaterializationError("external source scene changed during verification")
        return {"status": "VERIFIED", "source_observed": before, "research_results": results}
    if atlas is None and (blender is None or not blender.is_file()):
        raise MaterializationError(
            "missing Blender prerequisite: provide --blender /absolute/path/to/blender "
            "or explicitly supply --atlas; no download or implicit test generation occurs"
        )
    if atlas is not None and not atlas.is_file():
        raise MaterializationError(
            f"missing explicitly supplied source atlas prerequisite: {atlas}"
        )
    with tempfile.TemporaryDirectory(prefix="amidst-physical-materialization-") as directory:
        workspace = Path(directory)
        _workspace(root, workspace, contract, source)
        config = _document(root / contract["validation_config"], "validation config")
        if atlas is None:
            assert blender is not None
            _check_blender(blender, contract["producer"])
            atlas = workspace / "exported_source_evidence.json"
            print("Generating source atlas with the unchanged Blender exporter.", flush=True)
            _run(
                [
                    str(blender.resolve()),
                    "--background",
                    "--factory-startup",
                    "--disable-autoexec",
                    "--python-exit-code",
                    "2",
                    str(source),
                    "--python",
                    str(root / config["source_exporter"]),
                    "--",
                    "--audit",
                    config["audit"],
                    "--config",
                    config["source_selection_config"],
                    "--expected-source-sha256",
                    contract["source_scene"]["sha256"],
                    "--output",
                    str(atlas),
                ],
                workspace,
            )
        evidence = _document(atlas, "source atlas")
        if evidence.get("blender_version") != contract["producer"]["blender_version"]:
            raise MaterializationError(
                "source atlas Blender version differs from historical producer"
            )
        # Replay metadata uses the historical timestamp; the source itself is never touched.
        evidence["source_mtime_ns"] = contract["source_scene"]["original_mtime_ns"]
        atlas_destination = workspace / config["source_evidence"]
        atlas_destination.parent.mkdir(parents=True, exist_ok=True)
        write_document(atlas_destination, evidence)
        verify_artifact(atlas_destination, records["source_evidence.json.gz"])
        output = workspace / "policy-replay"
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(root / "src")
        print("Replaying source-bound physical policy validation.", flush=True)
        _run(
            [
                sys.executable,
                "-m",
                "amidst.physical_policy_validation",
                "--config",
                contract["validation_config"],
                "--output",
                str(output),
            ],
            workspace,
            environment=environment,
        )
        for name in POLICY_OUTPUTS:
            verify_artifact(output / name, records[name], semantic=True)
        results = _verify_results(output, contract)
        after = _source_binding(source, contract)
        if before != after:
            raise MaterializationError("external source scene changed during materialization")
        verify_bindings(root, contract)
        hashes = {}
        for name in sorted(RAW_FILENAMES):
            produced = atlas_destination if name == "source_evidence.json.gz" else output / name
            destination = _relative_path(root, records[name]["filename"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(produced, destination)
            hashes[name] = file_sha256(destination)
        receipt = {
            "schema_version": "physical-evidence-materialization-receipt-v1",
            "status": "MATERIALIZED_AND_RESEARCH_EQUIVALENT",
            "full_evidence_commit": contract["full_evidence_commit"],
            "canonical_manifest_sha256": file_sha256(manifest_path),
            "source_observed_before": before,
            "source_observed_after": after,
            "historical_atlas_source_mtime_ns": contract["source_scene"]["original_mtime_ns"],
            "artifact_byte_sha256": hashes,
            "research_results": results,
            "replay_manifest": _document(output / "manifest.json", "replay manifest"),
        }
        write_document(artifact_dir / "materialization_receipt.json", receipt)
        return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source-scene", type=Path)
    parser.add_argument("--blender", type=Path)
    parser.add_argument(
        "--atlas", type=Path, help="explicit existing source atlas instead of Blender"
    )
    parser.add_argument(
        "--verify-only", action="store_true", help="read-only; never generate evidence"
    )
    args = parser.parse_args()
    try:
        result = materialize(
            args.repo_root,
            args.manifest,
            source_scene=args.source_scene,
            blender=args.blender,
            atlas=args.atlas,
            verify_only=args.verify_only,
        )
    except MaterializationError as exc:
        parser.exit(2, f"physical evidence prerequisite/binding error: {exc}\n")
    print(
        json.dumps(
            {"status": result["status"], "research_results": result["research_results"]},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
