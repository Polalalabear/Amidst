"""Real small E1 RGB pilot → independently frozen, reloadable local product."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from amidst.engineering.local_pilot import build_run
from amidst.engineering.research_scene import DEFAULT_CONFIG
from amidst.product import run as product_run
from amidst.product.run import ProductRunError, build_product, load_product
from amidst.product.store import RecordQuery


@pytest.fixture(scope="module")
def source_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("product-e1-source")
    config = json.loads(DEFAULT_CONFIG.read_bytes())
    config["duration_s"] = 4.0
    config_path = root.parent / (root.name + "-config.json")
    config_path.write_text(json.dumps(config))
    build_run(root, run_id="product-e1-fixture-v1", config_path=config_path)
    return root


@pytest.fixture(scope="module")
def product_root(source_root: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("frozen-product")
    pool = tmp_path_factory.mktemp("product-video-pool")
    build_product(source_root, root, video_pool=pool, encode_video=False)
    return root


def copy_product(product_root: Path, tmp_path: Path) -> Path:
    # Only small product JSON/catalog fixtures are copied. Source RGB stays shared.
    output = tmp_path / "product"
    shutil.copytree(product_root, output)
    return output


def alter_manifest(output: Path, update: dict[str, object]) -> None:
    path = output / "product_manifest.json"
    value = json.loads(path.read_bytes())
    value.update(update)
    value.pop("manifest_sha256")
    value["manifest_sha256"] = product_run.digest(value)
    path.write_text(json.dumps(value))


def test_real_product_flow_preserves_source_records_and_safe_context(
    source_root: Path, product_root: Path,
) -> None:
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in source_root.glob("*.json")}
    with load_product(product_root) as runtime:
        assert runtime.source == source_root
        assert runtime.video_manifest is None
        assert len(runtime.services) == 2
        assert {s.scope.observation_mode for s in runtime.services} == {
            "photos_only", "photos_plus_observations",
        }
        assert len({s.scope.run_ref for s in runtime.services}) == 2
        for service, receipt in zip(runtime.services, runtime.manifest.modes, strict=True):
            assert receipt.scope.freeze_sha256 != receipt.base_receipt.receipt_sha256
            assert service.product_freeze_ref == receipt.product_freeze_ref
            camera_ref = next(iter(service.base.cameras))
            session = {"session_ref": service.base.guard.session_ref}
            response = service.call("query_observations", session | {
                "camera_ref": camera_ref, "time_range": [0, 4], "limit": 2,
            })
            assert response["retrieval"]["record_set_receipt_sha256"] == (
                receipt.record_set_receipt.receipt_sha256
            )
            for item in response["items"]:
                assert product_run.digest(item) == product_run.digest(
                    service.base.observations[item["observation_ref"]]
                )
            frames = service.repository.query_records(RecordQuery(
                run_ref=service.scope.run_ref, kind="FRAME", time_range=(0, 4), limit=128,
            ))
            assert len(frames.records) == len(service.base.frames)
            assert all("relative_path" not in row.payload for row in frames.records)
            public = service.context().model_dump_json()
            assert str(source_root) not in public and "simulation_export_path" not in public
    assert before == {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in source_root.glob("*.json")}
    assert not (product_root / "rgb").exists()
    assert not (product_root / "simulation").exists()


def test_build_photos_only_recomputes_pixels_once_and_plus_uses_its_frozen_mode(
    source_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = product_run.produce_perception
    calls = []

    def count_producer(*args: object, **kwargs: object) -> object:
        calls.append(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(product_run, "produce_perception", count_producer)
    manifest = build_product(source_root, tmp_path / "product", video_pool=tmp_path / "videos",
                             encode_video=False)
    assert len(calls) == 1
    assert manifest.modes[0].photos_only_pixels_recomputed is True
    assert manifest.modes[1].photos_only_pixels_recomputed is False
    assert manifest.modes[0].perception_sha256 == manifest.modes[1].perception_sha256
    assert manifest.modes[0].appearance_sha256 == manifest.modes[1].appearance_sha256


def test_restart_never_calls_producers_builders_or_encoder(
    product_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("loader reran an inference/presentation producer")

    for name in ("produce_perception", "build_appearance_bundle", "build_stitch_bundle",
                 "encode_videos"):
        monkeypatch.setattr(product_run, name, forbidden)
    with load_product(product_root) as first:
        original = [s.scope for s in first.services]
    with load_product(product_root) as second:
        assert [s.scope for s in second.services] == original


def test_existing_manifest_is_idempotent_and_conflict_never_overwrites(
    source_root: Path, product_root: Path, tmp_path: Path,
) -> None:
    original = (product_root / "product_manifest.json").read_bytes()
    with load_product(product_root) as loaded:
        pool = loaded.video_pool
    same = build_product(source_root, product_root, video_pool=pool, encode_video=False)
    assert same.manifest_sha256
    with pytest.raises(ProductRunError, match="IMMUTABLE_OUTPUT_CONFLICT"):
        build_product(source_root, product_root, video_pool=tmp_path / "other", encode_video=False)
    assert (product_root / "product_manifest.json").read_bytes() == original


def test_build_output_and_video_pool_cannot_write_inside_immutable_source(
    source_root: Path, tmp_path: Path,
) -> None:
    before = {path.relative_to(source_root): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in source_root.rglob("*") if path.is_file()}
    for output, pool in ((source_root, tmp_path / "pool"),
                         (source_root / "product", tmp_path / "pool"),
                         (source_root.parent, tmp_path / "pool"),
                         (tmp_path / "product", source_root / "videos")):
        with pytest.raises(ProductRunError, match="SOURCE_WRITE_SCOPE_DENIED"):
            build_product(source_root, output, video_pool=pool, encode_video=False)
    assert before == {path.relative_to(source_root): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in source_root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("document", ["appearance_photos_only.json", "stitch_photos_only.json",
                                      "record_set_photos_only.json"])
def test_missing_or_tampered_product_artifacts_are_denied(
    product_root: Path, tmp_path: Path, document: str,
) -> None:
    output = copy_product(product_root, tmp_path)
    (output / document).write_text('{"wrong":"private rejected input"}')
    with pytest.raises(ProductRunError, match="^PRODUCT_FROZEN_INPUT_INVALID$"):
        load_product(output)


def test_missing_source_and_wrong_mode_or_config_are_denied(
    product_root: Path, tmp_path: Path,
) -> None:
    for case, update in (
        ("source", {"source": str(tmp_path / "absent-source")}),
        ("config", {"product_config_sha256": "f" * 64}),
    ):
        output = tmp_path / case
        shutil.copytree(product_root, output)
        alter_manifest(output, update)
        with pytest.raises(ProductRunError, match="^PRODUCT_FROZEN_INPUT_INVALID$"):
            load_product(output)
    output = tmp_path / "mode"
    shutil.copytree(product_root, output)
    value = json.loads((output / "product_manifest.json").read_bytes())
    value["modes"][0]["observation_mode"] = "photos_plus_observations"
    alter_manifest(output, {"modes": value["modes"]})
    with pytest.raises(ProductRunError, match="^PRODUCT_FROZEN_INPUT_INVALID$"):
        load_product(output)


def test_changed_source_rgb_is_denied_and_source_bytes_can_be_restored(
    source_root: Path, product_root: Path,
) -> None:
    frame = next((source_root / "rgb").rglob("*.png"))
    original = frame.read_bytes()
    try:
        frame.write_bytes(original + b"tampered")
        with pytest.raises(ProductRunError, match="^PRODUCT_FROZEN_INPUT_INVALID$"):
            load_product(product_root)
    finally:
        frame.write_bytes(original)
    with load_product(product_root) as restored:
        assert restored.services


def test_gt_poison_does_not_enter_build_load_or_change_product_freeze(
    source_root: Path, product_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    gt = source_root / "simulation/export/ground_truth.json"
    original_gt = gt.read_bytes()
    with load_product(product_root) as original:
        hashes = [m.scope.freeze_sha256 for m in original.manifest.modes]
        pool = original.video_pool
    try:
        gt.write_text("POISONED ACTOR_ID / PRIVATE PATH / NOT JSON")
        read_bytes = Path.read_bytes

        def guarded_read(path: Path) -> bytes:
            assert path != gt, "product opened the evaluation-only GT sidecar"
            return read_bytes(path)

        monkeypatch.setattr(Path, "read_bytes", guarded_read)
        with load_product(product_root) as loaded:
            assert [m.scope.freeze_sha256 for m in loaded.manifest.modes] == hashes
        fresh = build_product(source_root, tmp_path / "fresh", video_pool=pool, encode_video=False)
        assert [m.scope.freeze_sha256 for m in fresh.modes] == hashes
    finally:
        gt.write_bytes(original_gt)


def test_append_only_case_does_not_change_canonical_freeze_or_prevent_reload(
    product_root: Path,
) -> None:
    with load_product(product_root) as loaded:
        service = loaded.services[0]
        receipt = loaded.manifest.modes[0].record_set_receipt
        service.repository.append_revision(service.scope.run_ref, "CASE", "case:" + "a" * 24,
                                            {"status": "OPEN"}, expected_version=0)
    with load_product(product_root) as loaded:
        service = loaded.services[0]
        assert service.repository.verify_run(service.scope.run_ref) == receipt
        assert service.repository.get_revision(service.scope.run_ref, "CASE", "case:" + "a" * 24)


def test_real_video_encoding_cache_reuse_and_tamper_rejection(
    source_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = tmp_path / "videos"
    first = tmp_path / "first"
    manifest = build_product(source_root, first, video_pool=pool)
    with load_product(first) as loaded:
        videos = loaded.video_manifest
        assert videos is not None and len(videos.artifacts) == 4
        assert all(v.fps == 15 and v.sampling == "NEAREST_REGISTERED_RGB_FRAME_HOLD"
                   for v in videos.artifacts)
        original = {v.relative_path: (pool / v.relative_path).read_bytes()
                    for v in videos.artifacts}
    second = build_product(source_root, tmp_path / "second", video_pool=pool)
    assert second.video_manifest_sha256 == manifest.video_manifest_sha256
    assert original == {name: (pool / name).read_bytes() for name in original}

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("reload encoded video")

    monkeypatch.setattr(product_run, "encode_videos", forbidden)
    with load_product(first) as loaded:
        assert loaded.video_manifest == videos
    artifact = pool / videos.artifacts[0].relative_path
    artifact.write_bytes(artifact.read_bytes() + b"tampered")
    with pytest.raises(ProductRunError, match="^PRODUCT_FROZEN_INPUT_INVALID$"):
        load_product(first)
