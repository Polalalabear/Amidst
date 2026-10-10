"""Actual RGB invariance, fixed-pool preservation and explicit missing evidence."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from amidst.domain.geometry import Plane
from amidst.engineering.association import InferenceScope, SyntheticStaticContext
from amidst.engineering.local_association import (
    GroundCalibration,
    InferenceBundle,
    build_inference,
    content_sha256,
)
from amidst.engineering.perception import (
    LocalTrack,
    Measurement,
    PerceptionResult,
    RGBFrame,
    frame_manifest_sha256,
)
from amidst.research_accuracy.association import (
    AssociationConfig,
    RGBDescriptorBundle,
    build_appearance_bundle,
    descriptor_distance,
    improve_association,
    rank_association_hypotheses,
)


def fixture(tmp_path: Path) -> tuple[PerceptionResult, InferenceBundle, tuple[RGBFrame, ...]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    frames, measurements, tracks = [], [], []
    for camera, start, x, top, lower, background in (
        ("A", 0.0, 20, (200, 40, 40), (40, 40, 180), (230, 230, 230)),
        ("B", 2.0, 40, (100, 20, 20), (20, 20, 90), (20, 20, 20)),
        ("C", 2.0, 60, (40, 180, 40), (140, 40, 140), (160, 160, 160)),
    ):
        selected = []
        identity = f"lab/research/{camera}/local-0"
        for index in range(3):
            timestamp = start + index * 0.4
            path = tmp_path / f"{camera}-{index}.png"
            image = Image.new("RGB", (140, 100), background)
            draw = ImageDraw.Draw(image)
            left = x + index * 2
            draw.rectangle((left, 20, left + 19, 49), fill=top)
            draw.rectangle((left, 50, left + 19, 79), fill=lower)
            image.save(path)
            fingerprint = sha256(path.read_bytes()).hexdigest()
            frame_ref = f"rgb:{camera}/{index}"
            frames.append(
                RGBFrame(
                    media_ref=frame_ref,
                    camera_id=camera,
                    timestamp=timestamp,
                    path=path,
                    sha256=fingerprint,
                    width=140,
                    height=100,
                )
            )
            selected.append(
                Measurement(
                    observation_id=f"pixels:{identity}/{index}",
                    local_track_id=identity,
                    camera_id=camera,
                    model_id="lab",
                    run_id="research",
                    timestamp=timestamp,
                    frame_ref=frame_ref,
                    bbox_xyxy=(left - 3, 17, left + 23, 83),
                    contact_pixel=(left + 10, 80),
                    appearance=(200, 40, 40),
                    uncertainty=0.1,
                    input_sha256=fingerprint,
                    status="DETECTED",
                    local_alternative_count=0,
                    evidence_refs=(frame_ref,),
                )
            )
        measurements.extend(selected)
        tracks.append(
            LocalTrack(
                local_track_id=identity,
                camera_id=camera,
                model_id="lab",
                run_id="research",
                observation_ids=tuple(row.observation_id for row in selected),
                timestamps=tuple(row.timestamp for row in selected),
                status="COMPLETE",
                missing_timestamps=(),
                termination_reason="SEQUENCE_END",
            )
        )
    plane = Plane(plane_id="floor", point=(0, 0, 0), normal=(0, 0, 1), floor_id="floor")
    context = SyntheticStaticContext(
        spatial_context_id="context",
        source_sha256="a" * 64,
        context_sha256="b" * 64,
        ground_plane=plane,
        walkable_bounds_xy_m=(0, 0, 20, 20),
        calibrations=tuple(
            GroundCalibration(
                camera_id=camera, plane=plane, affine_ground_to_pixel=((10, 0, 0), (0, 10, 0))
            )
            for camera in ("A", "B", "C")
        ),
        allowed_camera_pairs=tuple(
            (a, b) for a in ("A", "B", "C") for b in ("A", "B", "C") if a != b
        ),
    )
    scope = InferenceScope(
        place_id="synthetic",
        model_id="lab",
        model_revision="1",
        run_id="research",
        clock_id="seconds",
        source_ref="source",
        source_sha256="a" * 64,
        spatial_context_id="context",
        context_sha256="b" * 64,
    )
    perception = PerceptionResult(
        model_id="lab",
        run_id="research",
        measurements=tuple(measurements),
        tracks=tuple(tracks),
        frame_statuses=(),
        input_manifest_sha256=frame_manifest_sha256(frames),
        producer_sha256="c" * 64,
        complete=True,
    )
    return perception, build_inference(perception, scope=scope, context=context), tuple(frames)


def test_rgb_chromaticity_resists_background_and_brightness(tmp_path: Path) -> None:
    perception, inference, frames = fixture(tmp_path)
    bundle = build_appearance_bundle(perception, inference, frames)
    a, b, c = bundle.segment_descriptors
    assert a.vector is not None and b.vector is not None and c.vector is not None
    same = descriptor_distance(a.vector, b.vector)
    different = descriptor_distance(a.vector, c.vector)
    assert same < 0.04 and different > 0.30
    assert same < different / 5
    assert bundle.complete and not bundle.trained_reid and not bundle.scores_are_probabilities
    assert RGBDescriptorBundle.model_validate_json(bundle.model_dump_json()) == bundle
    assert str(tmp_path) not in bundle.model_dump_json()


def test_wrapper_preserves_graph_pool_hard_status_and_original_order(tmp_path: Path) -> None:
    perception, inference, frames = fixture(tmp_path)
    original = inference.model_dump(mode="json")
    result = improve_association(perception, inference, frames)
    assert inference.model_dump(mode="json") == original
    assert result.snapshot == inference.snapshot
    assert result.association_pool_sha256 == inference.association_pool_sha256
    assert result.local_record_maps == inference.local_record_maps
    assert result.derived_record_maps == inference.derived_record_maps
    assert result.retrieval_receipts == inference.retrieval_receipts
    for old, new in zip(
        inference.association_hypotheses, result.association_hypotheses, strict=True
    ):
        assert old.model_dump(exclude={"appearance_distance", "feature_scores"}) == new.model_dump(
            exclude={"appearance_distance", "feature_scores"}
        )
    ranked = rank_association_hypotheses(result, feature_only="APPEARANCE")
    source = inference.local_record_maps[0].segment_id
    selected = [row for row in ranked if row.segment_ids[0] == source]
    assert selected[0].camera_ids == ("A", "B")


def test_legacy_features_replay_and_ablations_keep_same_eligibility(tmp_path: Path) -> None:
    perception, inference, frames = fixture(tmp_path)
    legacy = AssociationConfig(
        appearance_mode="LEGACY_MEAN_RGB",
        spatial_mode="LEGACY_PROXIMITY",
        time_mode="LEGACY_DIRECTION",
    )
    assert improve_association(perception, inference, frames, legacy) == inference
    improved = improve_association(perception, inference, frames)
    variants = [rank_association_hypotheses(improved)]
    for feature in ("SPACE", "TIME", "APPEARANCE"):
        variants.append(rank_association_hypotheses(improved, removed_feature=feature))
        variants.append(rank_association_hypotheses(improved, feature_only=feature))
    expected = {row.hypothesis_id for row in variants[0]}
    assert all({row.hypothesis_id for row in variant} == expected for variant in variants)
    with pytest.raises(ValueError, match="one removal"):
        rank_association_hypotheses(improved, removed_feature="SPACE", feature_only="TIME")


@pytest.mark.parametrize("kind", ["missing", "corrupt", "invalid_crop"])
def test_missing_and_unusable_rgb_preserve_unknown(tmp_path: Path, kind: str) -> None:
    perception, inference, frames = fixture(tmp_path)
    if kind == "missing":
        for frame in frames[:3]:
            frame.path.unlink()
    elif kind == "corrupt":
        for frame in frames[:3]:
            frame.path.write_bytes(b"corrupt")
    else:
        bad = tuple(
            row.model_copy(update={"bbox_xyxy": (-100, -100, -50, -50)})
            for row in perception.measurements[:3]
        )
        perception = perception.model_copy(
            update={"measurements": (*bad, *perception.measurements[3:])}
        )
    artifact = build_appearance_bundle(perception, inference, frames)
    assert not artifact.complete and artifact.segment_descriptors[0].status == "UNAVAILABLE"
    expected = {
        "missing": "MISSING_MEDIA",
        "corrupt": "HASH_MISMATCH",
        "invalid_crop": "INVALID_CROP",
    }[kind]
    assert all(row.status == expected for row in artifact.measurement_descriptors[:3])
    result = improve_association(perception, inference, frames)
    for row in result.association_hypotheses:
        if (
            len(row.segment_ids) == 2
            and row.segment_ids[0] == inference.local_record_maps[0].segment_id
        ):
            assert row.appearance_distance is None
            assert (
                row.feature_scores is not None and row.feature_scores.appearance_continuity is None
            )
    assert result.snapshot == inference.snapshot


def test_quality_outlier_is_retained_as_conflicting_evidence(tmp_path: Path) -> None:
    perception, inference, frames = fixture(tmp_path)
    changed = perception.measurements[0].model_copy(update={"status": "MERGED_OR_PARTIAL"})
    altered = perception.model_copy(
        update={"measurements": (changed, *perception.measurements[1:])}
    )
    bundle = build_appearance_bundle(altered, inference, frames)
    assert bundle.measurement_descriptors[0].status == "UNCERTAIN"
    assert bundle.measurement_descriptors[0].quality < bundle.measurement_descriptors[1].quality / 4
    assert bundle.segment_descriptors[0].status == "UNCERTAIN"
    assert (
        bundle.segment_descriptors[0].observation_ids
        == inference.local_record_maps[0].original_pixel_observation_ids
    )


def test_input_binding_and_undeclared_truth_fail_closed(tmp_path: Path) -> None:
    perception, inference, frames = fixture(tmp_path)
    with pytest.raises(ValueError, match="binding"):
        build_appearance_bundle(
            perception.model_copy(update={"run_id": "other"}), inference, frames
        )
    with pytest.raises(ValueError, match="binding"):
        build_appearance_bundle(perception, inference, frames[:-1])
    poisoned = perception.model_copy(update={"ground_truth": {"actor": "answer"}})
    with pytest.raises(ValueError, match="undeclared or truth"):
        improve_association(poisoned, inference, frames)
    wrong = frames[0].model_copy(update={"camera_id": "other"})
    with pytest.raises(ValueError, match="binding"):
        build_appearance_bundle(perception, inference, (wrong, *frames[1:]))


def test_determinism_relocation_and_truth_sidecars_are_independent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    perception, inference, frames = fixture(tmp_path)
    original = improve_association(perception, inference, frames)
    artifact = build_appearance_bundle(perception, inference, frames)
    for name in ("ground_truth.json", "recipe.json", "reference_annotations.json"):
        (tmp_path / name).write_text('{"answer":"poison"}')
    reader = Path.read_bytes

    def read_pixels_only(path: Path) -> bytes:
        assert path.suffix in {".png", ".py"}
        return reader(path)

    monkeypatch.setattr(Path, "read_bytes", read_pixels_only)
    assert improve_association(perception, inference, frames) == original
    for name in ("ground_truth.json", "recipe.json", "reference_annotations.json"):
        (tmp_path / name).unlink()
    assert build_appearance_bundle(perception, inference, frames) == artifact
    relocated = []
    for frame in frames:
        new_path = tmp_path / "relocated" / frame.path.name
        new_path.parent.mkdir(exist_ok=True)
        new_path.write_bytes(reader(frame.path))
        relocated.append(frame.model_copy(update={"path": new_path}))
    assert content_sha256(
        build_appearance_bundle(perception, inference, relocated)
    ) == content_sha256(artifact)


def test_development_selection_refuses_test_split_before_any_truth_or_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from amidst.research_accuracy import development

    package = SimpleNamespace(split="test")
    monkeypatch.setattr(development, "_load", lambda _: (package, None, None, {}))

    def forbid_read(path: Path) -> bytes:
        raise AssertionError("test truth cannot enter development policy selection")

    monkeypatch.setattr(Path, "read_bytes", forbid_read)
    with pytest.raises(ValueError, match="DEVELOPMENT"):
        development.develop_association(tmp_path, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_development_options_preserve_selected_policy_and_rejected_combinations() -> None:
    from amidst.research_accuracy.development import SELECTED, development_options

    options = development_options()
    chosen = options[SELECTED]
    assert chosen.appearance_mode == "ROBUST_CROP"
    assert chosen.spatial_mode == "FEASIBILITY_RATIO"
    assert chosen.time_mode == "LEGACY_DIRECTION"
    assert chosen.spatial_weight == chosen.time_weight == chosen.appearance_weight == 1
    assert options["v2_equal_weights"].time_mode == "SPEED_RESIDUAL"
    assert options["v2_soft_weights"].spatial_weight == 0.15
