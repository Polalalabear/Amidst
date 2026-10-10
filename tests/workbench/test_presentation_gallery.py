"""Gallery tests use tiny local fixtures, never Blender, GT exports or archive readers."""

from __future__ import annotations

import io
import json
from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image

from amidst.engineering.access import FreezeReceipt, RunBinding, digest
from amidst.workbench import presentation_gallery as module
from amidst.workbench.presentation_gallery import Gallery, GalleryError

_E0 = "data/engineering/local_run/simulation_v2/presentation/inference.png"
_RECOVERY = "data/finalization/reviewed_run_recovery_20261008/evaluation"


def _png(root: Path, relative: str, color: str = "blue") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buffer, format="PNG")
    payload = buffer.getvalue()
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def _family(gallery: Gallery, key: str) -> dict:
    row = next(row for row in gallery.list()["items"] if row["family_id"] == key)
    return gallery.detail(row["family_ref"])


def _preview(root: Path) -> dict:
    paths = [f"frames/motion_context/motion_{i:03}.png" for i in range(50)]
    paths += ["frames/hr02_camera_audit/wide.png", "frames/hr02_camera_audit/side.png"]
    paths += [f"frames/hr02_camera_audit/camera_{camera}_frame{frame:03}.png"
              for camera in ("FRONT", "REAR") for frame in (20, 25, 45)]
    entries = []
    for relative in paths:
        payload = _png(root, "human_review/" + relative)
        entries.append({"path": relative, "sha256": sha256(payload).hexdigest(),
                        "bytes": len(payload)})
    value = {"schema_version": "phase1-playback-build-v1", "mode": "VIEW_ONLY",
             "research_rerun": False, "frame_count": 50, "media_count": 58,
             "source_sha256": "a" * 64, "media_files": entries}
    path = root / "human_review/playback/build_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


def test_fifteen_families_and_unknown_sources_remain_explicit(tmp_path: Path) -> None:
    gallery = Gallery(tmp_path)
    listing = gallery.list()
    assert len(listing["items"]) == 15 and listing["complete"]
    assert listing["audience"] == "HUMAN_RESEARCH_DIAGNOSTIC"
    assert _family(gallery, "projection-upgrade")["status"] == "NOT_MATERIALIZED"
    assert _family(gallery, "reviewed-recovery-demos")["model_id"] is None
    assert _family(gallery, "school-downstream")["status"] == "CANONICAL_ROOT_UNAVAILABLE"
    encoded = json.dumps(listing)
    assert str(tmp_path) not in encoded and "ground_truth" not in encoded
    assert all(row["normal_presentation_allowed"] is False for row in listing["items"])
    listing["items"][0]["counts"]["images"] = 999
    assert gallery.list()["items"][0]["counts"]["images"] == 0


def _save_json(root: Path, relative: str, value: dict) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True))


def _accuracy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    manifest = {
        "schema_version": "accuracy.frozen-run.v2", "version": "local-camera-accuracy-v2",
        "experiment_id": "accuracy-test-v2-final", "source_run_id": "local-camera-test-v1",
        "split": "test", "clock_id": "synthetic-seconds-v1", "unit": "METRES_SYNTHETIC_SECONDS",
        "external_model_calls": False, "formal_phase1_acceptance": False,
        "source_sha256": "a" * 64, "dataset_sha256": "b" * 64, "config_sha256": "c" * 64,
        "context_sha256": "d" * 64, "variants": {}, "source_locator": str(tmp_path / "PRIVATE"),
    }
    for variant in module._ACCURACY_VARIANTS:
        manifest["variants"][variant] = {}
        for mode in module._ACCURACY_MODES:
            config = digest({"run_config": manifest["config_sha256"],
                             "experiment_id": manifest["experiment_id"], "variant": variant})
            binding = RunBinding(
                place_id="synthetic-local-camera", model_id="synthetic-local-camera-v1",
                model_revision="1", source_ref="source:" + "a" * 64,
                spatial_context_id="context:synthetic-local-camera-v1",
                run_id="local-camera-test-v1", clock_id="synthetic-seconds-v1",
                observation_mode=mode, registry_version="local-camera-accuracy-v2",
                dataset_sha256="b" * 64, config_sha256=config, producer_sha256="e" * 64,
                registry_sha256="f" * 64, media_sha256="1" * 64,
            )
            receipt = FreezeReceipt.create(binding, {"test": variant}, {"pixel": "RGB"})
            manifest["variants"][variant][mode] = {
                "receipt_sha256": receipt.receipt_sha256, "binding_config_sha256": config,
            }
            _save_json(tmp_path, f"{module._ACCURACY}/{variant}/{mode}/receipt.json",
                       receipt.model_dump(mode="json"))
    _save_json(tmp_path, module._ACCURACY + "/manifest.json", manifest)
    cards = []
    for kind, state in sorted(module._ACCURACY_CARDS):
        relative = "cards_review/" + kind.lower() + "_" + state.lower() + ".png"
        payload = _png(tmp_path, module._ACCURACY + "/" + relative)
        cards.append({
            "kind": kind, "support_state": state, "path": relative,
            "sha256": sha256(payload).hexdigest(), "event_ref": "event:" + "0" * 24,
            "source_frames": [{"camera_id": "WEST", "frame_ref": "media:" + "1" * 24,
                               "evidence_state": "PROJECTED", "timestamp": i * .4}
                              for i in range(3)],
            "replay_path": "LOCAL_ONLY_DEBUG_UNOPENED.replay.json",
        })
    evidence = {
        "schema_version": "accuracy.review-cards.v2", "actual_source_rgb": True,
        "gt_overlay": False, "clock_and_unit": "SYNTHETIC_SECONDS_METRES", "cards": cards,
        "indexed_query_telemetry": {"mode": "photos_only"},
        "contract": {"experiment_id": manifest["experiment_id"],
                     "source_run_id": manifest["source_run_id"],
                     "config_sha256": manifest["config_sha256"],
                     "read_modes": list(module._ACCURACY_MODES),
                     "event_refs_bound_to_experiment_variant": True},
    }
    _save_json(tmp_path, module._ACCURACY + "/cards_review/receipt.json", evidence)
    comparison = {}
    for variant in ("baseline", "features_full", "end_to_end"):
        comparison[variant] = {
            "same_baseline_pool": variant != "end_to_end", "tracks": 18, "ID_switches": 8,
            "pairs": 115, "eligible_pair_positives": 15, "pair_precision": .35,
            "pair_recall": .46, "rank_recall_at_k": {"1": .4, "3": 1., "5": 1.},
            "contact_recall": .9, "ground_RMS_m": .3, "unknown_count": 0,
            "visible_candidate_count": 18, "private_identity_map": "NEVER_RETURN",
        }
    published = {
        "schema_version": "accuracy.curated-validation.v2",
        "experiments": {"test": {k: v for k, v in manifest.items() if k != "source_locator"}
                        | {"manifest_sha256": digest(manifest), "comparison_sha256": "2" * 64}},
        "evidence": evidence, "adapter_validation": {"variant": "end_to_end"},
        "comparison": {"test": comparison}, "private_path": str(tmp_path / "PRIVATE"),
    }
    _pin_accuracy(tmp_path, monkeypatch, published)
    return published


def _pin_accuracy(root: Path, monkeypatch: pytest.MonkeyPatch, published: dict) -> None:
    _save_json(root, module._ACCURACY_CURATED, published)
    checksum = sha256((root / module._ACCURACY_CURATED).read_bytes()).hexdigest()
    monkeypatch.setattr(module, "_ACCURACY_CURATED_SHA256", checksum)


def test_png_refs_are_opaque_scoped_and_revalidated(tmp_path: Path) -> None:
    payload = _png(tmp_path, _E0)
    gallery = Gallery(tmp_path)
    image = _family(gallery, "e0-simulation")["images"][0]
    assert image["media_ref"].startswith("gallery-image:")
    assert image["width"] == image["height"] == 8
    assert gallery.media(image["media_ref"]) == ("image/png", payload)
    for ref in ("../private/file.png", "gallery-image:foreign", "gallery-family:foreign"):
        with pytest.raises(GalleryError, match="GALLERY_MEDIA_SCOPE_DENIED"):
            gallery.media(ref)
        with pytest.raises(GalleryError, match="GALLERY_FAMILY_SCOPE_DENIED"):
            gallery.detail(ref)
    _png(tmp_path, _E0, "red")
    with pytest.raises(GalleryError, match="GALLERY_MEDIA_CONTENT_CHANGED"):
        gallery.media(image["media_ref"])
    assert gallery.detail(_family(gallery, "e0-simulation")["family_ref"])["images"][0] == image


def test_run_directory_presence_does_not_establish_materialized_results(tmp_path: Path) -> None:
    path = tmp_path / "data/pilot/phase1_projection_model_upgrade_20261006/verified_run"
    path.mkdir(parents=True)
    family = _family(Gallery(tmp_path), "projection-upgrade")
    assert family["artifacts"][0]["status"] == "PRESENT"
    assert family["status"] == "NOT_MATERIALIZED" and family["counts"]["images"] == 0


@pytest.mark.parametrize("ancestor", (False, True))
def test_symlinks_are_rejected_before_any_outside_bytes_are_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ancestor: bool
) -> None:
    repo, outside = tmp_path / "repo", tmp_path / "outside"
    repo.mkdir()
    _png(outside, "inference.png")
    path = repo / _E0
    path.parent.mkdir(parents=True)
    if ancestor:
        path.parent.rmdir()
        path.parent.symlink_to(outside, target_is_directory=True)
    else:
        path.symlink_to(outside / "inference.png")
    original = Path.open

    def confined(target: Path, *args, **kwargs):
        assert not target.is_relative_to(outside)
        return original(target, *args, **kwargs)

    monkeypatch.setattr(Path, "open", confined)
    family = _family(Gallery(repo), "e0-simulation")
    assert family["images"] == []
    assert "GALLERY_REFERENCE_DENIED" in family["issues"]


def test_media_rejects_symlink_replacement_after_assembly(tmp_path: Path) -> None:
    _png(tmp_path, _E0)
    gallery = Gallery(tmp_path)
    ref = _family(gallery, "e0-simulation")["images"][0]["media_ref"]
    alternate = tmp_path / "other.png"
    _png(tmp_path, "other.png")
    path = tmp_path / _E0
    path.unlink()
    path.symlink_to(alternate)
    with pytest.raises(GalleryError, match="GALLERY_REFERENCE_DENIED"):
        gallery.media(ref)


def test_original_preview_fifty_frames_verified_without_copy_or_render(tmp_path: Path) -> None:
    manifest = _preview(tmp_path)
    before = {root: root.read_bytes() for root in (tmp_path / "human_review").rglob("*.png")}
    gallery = Gallery(tmp_path)
    family = _family(gallery, "human-review-preview")
    frames = [row for row in family["images"] if row["sequence_index"] is not None]
    assert len(frames) == 50
    assert {row["sequence_index"] for row in frames} == set(range(50))
    assert family["verified_preview_frames"] == family["preview_frame_count"] == 50
    assert family["missing_preview_frame_indices"] == []
    assert family["source_sha256"] == manifest["source_sha256"]
    assert all(row["gt_overlay"] is False for row in frames)
    for row in (frames[0], frames[-1]):
        assert sha256(gallery.media(row["media_ref"])[1]).hexdigest() == row["sha256"]
    assert all(root.read_bytes() == payload for root, payload in before.items())


@pytest.mark.parametrize("poison", ("escape", "hash", "duplicate"))
def test_preview_manifest_escape_hash_and_duplicate_refs_fail_closed(
    tmp_path: Path, poison: str
) -> None:
    manifest = _preview(tmp_path)
    if poison == "escape":
        manifest["media_files"][0]["path"] = "../../outside/AUDIT_SENTINEL.png"
    elif poison == "duplicate":
        manifest["media_files"][0]["path"] = manifest["media_files"][1]["path"]
    else:
        manifest["media_files"][0]["sha256"] = "f" * 64
    (tmp_path / "human_review/playback/build_manifest.json").write_text(json.dumps(manifest))
    family = _family(Gallery(tmp_path), "human-review-preview")
    if poison == "hash":
        assert family["verified_preview_frames"] == 49
        assert family["missing_preview_frame_indices"] == [0]
        assert family["counts"]["missing"] == 2  # one preview plus absent topology PNG
    else:
        assert family["images"] == []
    assert "AUDIT_SENTINEL" not in json.dumps(family)


def test_curated_csv_preserves_blocked_na_and_bounds_rows_without_identity_fields(
    tmp_path: Path,
) -> None:
    path = tmp_path / f"{_RECOVERY}/benchmark_table.csv"
    path.parent.mkdir(parents=True)
    header = "case_id,method_id,k,result_type,status,ade_m,termination_reason,actor_identity\n"
    path.write_text(header + "case2,shortest_path,1,N/A,BLOCKED,,,AUDIT_PERSON\n" * 130)
    family = _family(Gallery(tmp_path), "recovery-benchmark")
    table = family["tables"][0]
    assert table["status"] == "AVAILABLE" and not table["complete"]
    assert len(table["rows"]) == 128
    assert "BLOCKED" in table["rows"][0] and "N/A" in table["rows"][0]
    assert "actor_identity" not in table["columns"]
    assert "AUDIT_PERSON" not in json.dumps(family)


def test_private_locator_in_curated_cell_is_not_returned(tmp_path: Path) -> None:
    path = tmp_path / f"{_RECOVERY}/benchmark_table.csv"
    path.parent.mkdir(parents=True)
    path.write_text("case_id,status,termination_reason\ncase2,BLOCKED,/private/AUDIT_SENTINEL\n")
    family = _family(Gallery(tmp_path), "recovery-benchmark")
    table = family["tables"][0]
    assert table["status"] == "GALLERY_TABLE_INVALID" and table["rows"] == []
    assert "AUDIT_SENTINEL" not in json.dumps(family)


def test_archive_status_and_gt_debug_scope_never_read_archives_or_sidecars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, canonical = tmp_path / "repo", tmp_path / "canonical"
    repo.mkdir()
    canonical.mkdir()
    relative = "data/pilot/phase1_downstream_20261005/run_01/visualization"
    _png(canonical, relative + "/preview_3d.png")
    (canonical / relative / "debug.rrd").write_bytes(b"UNOPENED_ARCHIVE")
    (canonical / relative / "presentation.json").write_text('{"gt_debug": "UNOPENED"}')
    pool = repo / "data/product/local_run/media_pool"
    pool.mkdir(parents=True)
    (pool / ("video-" + "a" * 24 + ".mp4")).write_bytes(b"UNOPENED_VIDEO")
    manifest = repo / "data/product/local_run/operator_v2/video_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({
        "schema_version": "product.video.v1",
        "scope": {"model_id": "synthetic-local-camera-v1", "run_id": "local-camera-test-v1"},
        "artifacts": [{"relative_path": "video-" + letter * 24 + ".mp4"}
                      for letter in ("a", "b", "c", "d")],
    }))
    (repo / "ground_truth.json").write_text("UNOPENED_GT")
    _png(repo, "arbitrary_raw_directory/AUDIT_PRIVATE_IMAGE.png")
    original_open = Path.open

    def permitted(target: Path, *args, **kwargs):
        assert target.suffix not in {".rrd", ".mp4", ".gif", ".html"}
        assert target.name not in {"ground_truth.json", "presentation.json"}
        assert "arbitrary_raw_directory" not in target.parts
        return original_open(target, *args, **kwargs)

    def limited_directories(target: Path):
        raise AssertionError("Gallery must not enumerate source directories")

    monkeypatch.setattr(Path, "open", permitted)
    monkeypatch.setattr(Path, "iterdir", limited_directories)
    gallery = Gallery(repo, canonical)
    debug = _family(gallery, "school-downstream")
    assert debug["audience"] == "GT_DEBUG_ONLY" and debug["gt_debug_only"]
    assert not debug["normal_presentation_allowed"]
    assert debug["images"][0]["gt_overlay"] is True
    assert debug["artifacts"][0]["verification"] == "EXISTENCE_ONLY"
    assert _family(gallery, "product-p7-p12")["counts"]["mp4"] == 1
    encoded = json.dumps(gallery.list()) + json.dumps(debug)
    assert str(repo) not in encoded and str(canonical) not in encoded
    assert "UNOPENED" not in encoded and "AUDIT_PRIVATE_IMAGE" not in encoded


def test_historical_blocked_table_preserves_legacy_labels_and_not_run(tmp_path: Path) -> None:
    path = tmp_path / "data/finalization/checkpoint/benchmark_table.csv"
    path.parent.mkdir(parents=True)
    path.write_text(
        "Case,Method,K,Status,ADE,Termination\n"
        "Case 3 — Long Gap / Timing Ambiguity,A — shortest_path,1,"
        "N/A / NOT_RUN,N/A,NOT_RUN\n"
    )
    table = _family(Gallery(tmp_path), "blocked-checkpoint")["tables"][0]
    assert table["status"] == "AVAILABLE" and len(table["rows"]) == 1
    assert "N/A / NOT_RUN" in table["rows"][0] and "N/A" in table["rows"][0]


def test_unknown_png_in_known_directory_is_not_enumerated_or_served(tmp_path: Path) -> None:
    _png(tmp_path, _E0)
    _png(tmp_path, str(Path(_E0).parent / "AUDIT_PRIVATE_IMAGE.png"))
    gallery = Gallery(tmp_path)
    assert len(_family(gallery, "e0-simulation")["images"]) == 1
    assert "AUDIT_PRIVATE_IMAGE" not in json.dumps(gallery.list())


def test_png_type_and_read_size_are_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / _E0
    path.parent.mkdir(parents=True)
    path.write_bytes(b"invalid-png")
    assert "GALLERY_PNG_INVALID" in _family(Gallery(tmp_path), "e0-simulation")["issues"]
    _png(tmp_path, _E0)
    monkeypatch.setattr("amidst.workbench.presentation_gallery.MAX_PNG_BYTES", 16)
    assert "GALLERY_ARTIFACT_TOO_LARGE" in _family(Gallery(tmp_path), "e0-simulation")["issues"]


def test_accuracy_frozen_scope_cards_and_comparison_preserve_original_families(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _accuracy(tmp_path, monkeypatch)
    _png(tmp_path, _E0)
    original_open = Path.open

    def no_debug(path: Path, *args, **kwargs):
        assert path.name != "ground_truth.json"
        assert not ("accuracy_v2" in path.parts and "evaluation" in path.parts)
        assert "debug" not in path.parts and not path.name.endswith(".replay.json")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", no_debug)
    gallery = Gallery(tmp_path)
    family = _family(gallery, "research-accuracy-v2")
    assert len(gallery.list()["items"]) == 15
    assert _family(gallery, "e0-simulation")["counts"]["images"] == 1
    assert family["status"] == "MATERIALIZED" and family["counts"]["images"] == 7
    assert family["comparison_mode"] == family["card_mode"] == "photos_only"
    assert family["card_variant"] == "end_to_end" and family["gt_overlay"] is False
    assert len(family["variants"]) == 8 and len(family["modes"]) == 2
    table = family["tables"][0]
    assert len(table["rows"]) == 3
    assert [row[2] for row in table["rows"]] == [
        "FIXED_V1_TRACK_POOL", "FIXED_V1_TRACK_POOL", "CHANGED_V2_TRACK_POOL",
    ]
    assert {im["support_state"] for im in family["images"]} == {
        "SUPPORTED", "UNKNOWN", "GAP_ALTERNATIVES",
    }
    for image in family["images"]:
        assert image["source_frame_count"] == 3 and gallery.media(image["media_ref"])[1]
    public = json.dumps(family) + json.dumps(gallery.list())
    assert "NEVER_RETURN" not in public and str(tmp_path) not in public
    assert "source_locator" not in public and "LOCAL_ONLY_DEBUG" not in public


def test_accuracy_gt_debug_poison_cannot_change_public_gallery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _accuracy(tmp_path, monkeypatch)
    before = _family(Gallery(tmp_path), "research-accuracy-v2")
    for name in ("ground_truth.json", "evaluation/scoped_remaining_errors.json",
                 "evaluation/end_to_end/photos_only/pixel_debug.json"):
        _save_json(tmp_path, module._ACCURACY + "/" + name, {"poison": "HIDDEN_IDENTITY"})
    original_open = Path.open

    def forbid_gt(path: Path, *args, **kwargs):
        assert path.name != "ground_truth.json"
        assert not ("accuracy_v2" in path.parts and "evaluation" in path.parts)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", forbid_gt)
    assert _family(Gallery(tmp_path), "research-accuracy-v2") == before


@pytest.mark.parametrize("target", ("curated", "manifest", "freeze", "card_manifest"))
def test_accuracy_tampering_fails_closed_without_gt_or_private_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    _accuracy(tmp_path, monkeypatch)
    relative = {
        "curated": module._ACCURACY_CURATED,
        "manifest": module._ACCURACY + "/manifest.json",
        "freeze": module._ACCURACY + "/end_to_end/photos_only/receipt.json",
        "card_manifest": module._ACCURACY + "/cards_review/receipt.json",
    }[target]
    value = json.loads((tmp_path / relative).read_bytes())
    value["PRIVATE_POISON"] = str(tmp_path / "ground_truth.json")
    _save_json(tmp_path, relative, value)
    family = _family(Gallery(tmp_path), "research-accuracy-v2")
    assert family["status"] == "PARTIAL" and family["images"] == []
    if target != "card_manifest":
        assert family["tables"] == []
    assert "PRIVATE_POISON" not in json.dumps(family) and str(tmp_path) not in json.dumps(family)


@pytest.mark.parametrize("target", ("card", "card_manifest", "freeze"))
def test_accuracy_missing_assets_report_exact_partial_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    published = _accuracy(tmp_path, monkeypatch)
    relative = {
        "card": module._ACCURACY + "/" + published["evidence"]["cards"][0]["path"],
        "card_manifest": module._ACCURACY + "/cards_review/receipt.json",
        "freeze": module._ACCURACY + "/features_full/photos_plus_observations/receipt.json",
    }[target]
    (tmp_path / relative).unlink()
    family = _family(Gallery(tmp_path), "research-accuracy-v2")
    assert family["status"] == "PARTIAL"
    assert family["counts"]["images"] == (6 if target == "card" else 0)
    assert family["counts"]["missing"] == {"card": 1, "card_manifest": 7, "freeze": 8}[target]
    assert len(family["tables"]) == (0 if target == "freeze" else 1)


@pytest.mark.parametrize("target", ("run", "mode", "variant", "path", "GT_overlay"))
def test_accuracy_explicit_binding_and_card_allowlists_survive_repinned_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    published = _accuracy(tmp_path, monkeypatch)
    if target in {"run", "mode", "variant"}:
        manifest_path = module._ACCURACY + "/manifest.json"
        manifest = json.loads((tmp_path / manifest_path).read_bytes())
        if target == "run":
            manifest["source_run_id"] = "foreign-run"
        elif target == "mode":
            del manifest["variants"]["end_to_end"]["photos_only"]
        else:
            del manifest["variants"]["baseline"]
        _save_json(tmp_path, manifest_path, manifest)
        published["experiments"]["test"] = {
            k: v for k, v in manifest.items() if k != "source_locator"
        } | {"manifest_sha256": digest(manifest), "comparison_sha256": "2" * 64}
    else:
        if target == "path":
            published["evidence"]["cards"][0]["path"] = "../PRIVATE.png"
        else:
            published["evidence"]["gt_overlay"] = True
        _save_json(tmp_path, module._ACCURACY + "/cards_review/receipt.json", published["evidence"])
    _pin_accuracy(tmp_path, monkeypatch, published)
    family = _family(Gallery(tmp_path), "research-accuracy-v2")
    assert family["status"] == "PARTIAL" and family["images"] == []
    assert str(tmp_path) not in json.dumps(family) and "PRIVATE.png" not in json.dumps(family)
