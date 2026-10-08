"""Actual RGB crops, provenance and bounded appearance ties, without GT inputs."""

from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from amidst.engineering.perception import RGBFrame, produce_perception
from amidst.engineering.registry import (
    CameraEntry,
    ClockBinding,
    CoordinateBinding,
    LocationModel,
    LocationRegistry,
    MediaFrame,
    RegistryStore,
    ResourceScope,
    opaque_ref,
    scope_parts,
)
from amidst.product.appearance import (
    AppearanceConfig,
    AppearanceError,
    AppearanceIndex,
    build_appearance_bundle,
)


def _fixture(
    tmp_path: Path,
    *,
    colors: tuple[tuple[int, int, int], ...] = (
        (200, 40, 40),
        (200, 40, 40),
        (200, 40, 40),
        (40, 50, 200),
    ),
    run_id: str = "rgb-v1",
) -> tuple[object, RegistryStore, ResourceScope, dict[str, str]]:
    scope = ResourceScope(
        place_id="fixture",
        model_id="fixture-model",
        model_revision="1",
        run_id=run_id,
        source_id="rgb-fixture",
        source_sha256="a" * 64,
        spatial_context_id="fixture-context",
        spatial_context_sha256="b" * 64,
        clock_id="fixture-seconds",
    )
    camera_ref = opaque_ref("camera", *scope_parts(scope), "CAM_A")
    frames, media, links = [], [], {}
    for index in range(10):
        path = tmp_path / "rgb" / f"f-{index:04d}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (500, 120), (10, 20, 30))
        draw = ImageDraw.Draw(image)
        for target, color in enumerate(colors):
            x = 20 + target * 100 + index * 12
            draw.rectangle((x, 60, x + 10, 88), fill=color)
        image.save(path)
        fingerprint = sha256(path.read_bytes()).hexdigest()
        original_ref = f"rgb:{index:04d}"
        ref = opaque_ref("media", *scope_parts(scope), "CAM_A", str(index), fingerprint)
        links[original_ref] = ref
        frames.append(
            RGBFrame(
                media_ref=original_ref,
                camera_id="CAM_A",
                timestamp=index / 5,
                path=path,
                sha256=fingerprint,
                width=500,
                height=120,
            )
        )
        media.append(
            MediaFrame(
                scope=scope,
                camera_id="CAM_A",
                camera_ref=camera_ref,
                media_ref=ref,
                frame_id=index,
                timestamp=index / 5,
                relative_path=path.relative_to(tmp_path).as_posix(),
                sha256=fingerprint,
                size_bytes=path.stat().st_size,
                width=500,
                height=120,
            )
        )
    model = LocationModel(
        scope=scope,
        display_name="RGB fixture",
        coordinates=CoordinateBinding(
            native_units="METRES",
            metres_per_unit=1,
            normalization_policy="IDENTITY",
            authority="SYNTHETIC_CONFIG",
        ),
        clock=ClockBinding(
            clock_id=scope.clock_id, mapping_sha256="c" * 64, authority="SYNTHETIC_CONFIG"
        ),
        authority="SYNTHETIC_CONFIG",
    )
    registry = LocationRegistry(
        models=(model,),
        cameras=(
            CameraEntry(
                scope=scope,
                camera_id="CAM_A",
                camera_ref=camera_ref,
                authority="SYNTHETIC_CONFIG",
            ),
        ),
        frames=tuple(media),
    )
    perception = produce_perception(frames, model_id=scope.model_id, run_id=scope.run_id)
    return perception, RegistryStore(registry, tmp_path), scope, links


def test_actual_pixels_descriptors_and_all_cutoff_ties(tmp_path: Path) -> None:
    perception, store, scope, links = _fixture(tmp_path)
    bundle = build_appearance_bundle(perception, store, scope, links, input_config_sha256="d" * 64)
    assert bundle.complete and len(bundle.track_descriptors) == 4
    assert all(len(row.vector) == 34 for row in bundle.track_descriptors)
    query = bundle.track_descriptors[0].track_ref
    result = AppearanceIndex(bundle).search(
        query,
        scope=scope,
        allowed_track_refs=[row.track_ref for row in bundle.track_descriptors],
        camera_id="CAM_A",
        time_range=(0, 2),
        top_k=1,
    )
    assert len(result.hits) == 2 and result.cutoff_tie_extension == 1
    assert all(hit.similarity == 1 and hit.distance == 0 for hit in result.hits)
    assert result.truncated and not result.complete
    public = result.model_dump_json()
    assert "vector" not in public and "observation_id" not in public
    assert str(tmp_path) not in public and not bundle.trained_reid


def test_changed_rgb_changes_descriptor_and_lineage(tmp_path: Path) -> None:
    original = _fixture(tmp_path / "original", colors=((200, 40, 40),), run_id="first")
    changed = _fixture(tmp_path / "changed", colors=((40, 180, 40),), run_id="second")
    first = build_appearance_bundle(*original, input_config_sha256="d" * 64)
    second = build_appearance_bundle(*changed, input_config_sha256="d" * 64)
    assert first.track_descriptors[0].vector != second.track_descriptors[0].vector
    assert (
        first.dataset_sha256 != second.dataset_sha256 and first.media_sha256 != second.media_sha256
    )


def test_missing_reference_media_and_corruption_are_explicit(tmp_path: Path) -> None:
    perception, store, scope, links = _fixture(tmp_path)
    missing_links = dict(links)
    missing_links.pop("rgb:0000")
    missing = build_appearance_bundle(
        perception, store, scope, missing_links, input_config_sha256="d" * 64
    )
    assert not missing.complete
    assert any(row.status == "MISSING_REFERENCE" for row in missing.measurement_descriptors)
    path = tmp_path / "rgb" / "f-0000.png"
    path.unlink()
    absent = build_appearance_bundle(perception, store, scope, links, input_config_sha256="d" * 64)
    assert any(row.status == "MISSING_MEDIA" for row in absent.measurement_descriptors)
    path.write_bytes(b"different pixels")
    corrupt = build_appearance_bundle(perception, store, scope, links, input_config_sha256="d" * 64)
    assert any(row.status == "HASH_MISMATCH" for row in corrupt.measurement_descriptors)


def test_invalid_crop_and_exact_rgb_reproduction(tmp_path: Path) -> None:
    perception, store, scope, links = _fixture(tmp_path)
    first = build_appearance_bundle(perception, store, scope, links, input_config_sha256="d" * 64)
    assert first == build_appearance_bundle(
        perception, store, scope, links, input_config_sha256="d" * 64
    )
    malformed = perception.measurements[0].model_copy(update={"bbox_xyxy": (-100, -100, -50, -50)})
    altered = perception.model_copy(
        update={"measurements": (malformed, *perception.measurements[1:])}
    )
    result = build_appearance_bundle(altered, store, scope, links, input_config_sha256="d" * 64)
    assert result.measurement_descriptors[0].status == "INVALID_CROP"
    assert result.measurement_descriptors[0].vector is None and not result.complete


def test_foreign_scope_frame_mapping_and_budgets_rejected(tmp_path: Path) -> None:
    perception, store, scope, links = _fixture(tmp_path)
    foreign = scope.model_copy(update={"run_id": "other-run"})
    with pytest.raises(AppearanceError, match="SCOPE_BINDING_MISMATCH"):
        build_appearance_bundle(perception, store, foreign, links, input_config_sha256="d" * 64)
    bad_links = dict(links)
    bad_links["rgb:0000"] = links["rgb:0001"]
    with pytest.raises(AppearanceError, match="FRAME_BINDING_MISMATCH"):
        build_appearance_bundle(perception, store, scope, bad_links, input_config_sha256="d" * 64)
    with pytest.raises(AppearanceError, match="BUDGET"):
        build_appearance_bundle(
            perception,
            store,
            scope,
            links,
            input_config_sha256="d" * 64,
            config=AppearanceConfig(max_measurements=1),
        )
    bundle = build_appearance_bundle(perception, store, scope, links, input_config_sha256="d" * 64)
    with pytest.raises(AppearanceError, match="SCOPE_DENIED"):
        AppearanceIndex(bundle).search(
            bundle.track_descriptors[0].track_ref,
            scope=foreign,
            allowed_track_refs=(),
            camera_id=None,
            time_range=(0, 2),
        )


def test_empty_window_and_untrusted_query_limits(tmp_path: Path) -> None:
    perception, store, scope, links = _fixture(tmp_path)
    bundle = build_appearance_bundle(perception, store, scope, links, input_config_sha256="d" * 64)
    index = AppearanceIndex(bundle)
    query, candidates = (
        bundle.track_descriptors[0].track_ref,
        [row.track_ref for row in bundle.track_descriptors],
    )
    empty = index.search(
        query,
        scope=scope,
        allowed_track_refs=candidates,
        camera_id="CAM_A",
        time_range=(10, 20),
        top_k=1,
    )
    assert not empty.hits and empty.complete
    for top_k in (True, 0, 1000, 1.5):
        with pytest.raises(AppearanceError, match="INVALID_QUERY"):
            index.search(
                query,
                scope=scope,
                allowed_track_refs=candidates,
                camera_id=None,
                time_range=(0, 2),
                top_k=top_k,
            )
    with pytest.raises(AppearanceError, match="CANDIDATE_SCOPE_DENIED"):
        index.search(
            query,
            scope=scope,
            allowed_track_refs=("track:foreign",),
            camera_id=None,
            time_range=(0, 2),
        )


def test_gt_recipe_poison_never_read_or_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    perception, store, scope, links = _fixture(tmp_path)
    frozen = build_appearance_bundle(perception, store, scope, links, input_config_sha256="d" * 64)
    sidecar = tmp_path / "simulation" / "export" / "ground_truth.json"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text('{"actor_identity":"polluted","recipe":{"answer":"wrong"}}')
    original = Path.read_bytes

    def deny_sidecar(path: Path) -> bytes:
        if path.name == "ground_truth.json":
            raise AssertionError("appearance has no truth channel")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", deny_sidecar)
    assert frozen == build_appearance_bundle(
        perception, store, scope, links, input_config_sha256="d" * 64
    )
    sidecar.unlink()
    assert frozen == build_appearance_bundle(
        perception, store, scope, links, input_config_sha256="d" * 64
    )
