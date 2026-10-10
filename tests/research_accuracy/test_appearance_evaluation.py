"""Fixed conditional pools, cutoff ties and unavailable descriptors are explicit."""

import math

import pytest

from amidst.engineering.perception import LocalTrack, Measurement, PerceptionResult
from amidst.engineering.research_scene import ResearchPackage
from amidst.product.appearance import TrackDescriptor
from amidst.product.evaluation import _track_labels
from amidst.research_accuracy.appearance_evaluation import (
    _cutoff_refs,
    _p8_pool_digest,
    _pool_manifest,
    _retrieval,
    _track_profiles,
)
from amidst.research_accuracy.association import (
    AssociationConfig,
    CropDescriptor,
    RGBDescriptorBundle,
)


def _track(ref: str, *, quality: float = 0.6) -> TrackDescriptor:
    return TrackDescriptor(
        track_ref=ref, local_track_id=ref, camera_id="CAM", time_range=(0, 1),
        original_observation_ids=(ref + ":pixel",), descriptor_refs=(ref + ":crop",),
        representative_descriptor_refs=(ref + ":crop",), representative_media_refs=(),
        vector=(0,) * 34, quality=quality, usable_measurements=1, status="READY",
    )


def test_ties_at_cutoff_keep_positive_alternatives_and_returned_counts() -> None:
    pool = [{"query_ref": "q", "pool": ("a", "b", "c", "positive"),
             "positive_refs": ("positive",)}]
    vectors = {"q": (0.0,), "a": (0.1,), "b": (0.2,), "c": (0.2,), "positive": (0.2,)}
    report, details = _retrieval(pool, vectors, {"q": 0.6}, math.dist)
    assert report["eligible_queries"] == 1
    assert report["tie_aware_recall_at_k"] == {"1": 0, "3": 1, "5": 1}
    assert report["false_negative_queries_at_k"] == {"1": 1, "3": 0, "5": 0}
    assert report["mean_returned_hits_at_k"] == {"1": 1, "3": 4, "5": 4}
    assert report["cutoff_tie_extensions_at_k"]["3"] == 1
    assert details[0]["at_k"]["3"]["returned_refs"] == ["a", "b", "c", "positive"]
    assert _cutoff_refs([(0.1, "negative"), (0.1, "positive")], 1) == {"negative", "positive"}
    assert _cutoff_refs([(0.1, "negative"), (0.10001, "positive")], 1) == {"negative"}


def test_missing_query_and_missing_positive_keep_both_queries_as_false_negatives() -> None:
    pool = [{"query_ref": "q", "pool": ("p",), "positive_refs": ("p",)},
            {"query_ref": "p", "pool": ("q",), "positive_refs": ("q",)}]
    report, details = _retrieval(pool, {"q": None, "p": (0.2,)}, {"q": 0, "p": 0.4}, math.dist)
    assert report["eligible_queries"] == 2
    assert report["tie_aware_recall_at_k"] == {"1": 0, "3": 0, "5": 0}
    assert report["false_negative_queries_at_k"] == {"1": 2, "3": 2, "5": 2}
    assert report["missing_query_descriptor_count"] == 1
    assert report["missing_candidate_descriptor_reads"] == 1
    assert sum(row["eligible_queries"] for row in report["by_query_quality"].values()) == 2
    assert len(details) == 2 and details[0]["missing_query_descriptor"]


def test_unknown_targets_remain_in_the_p8_pool_and_quality_does_not_filter_it() -> None:
    package = ResearchPackage.model_construct(adjacency=())
    rows = [_track("q", quality=0), _track("p"), _track("unknown"), _track("mixed")]
    labels = {"q": "evaluation-a", "p": "evaluation-a", "unknown": None, "mixed": None}
    manifest, exclusions = _pool_manifest(package, rows, labels)
    assert len(manifest) == 2
    assert manifest[0]["pool"] == ("p", "unknown", "mixed")
    assert manifest[0]["positive_refs"] == ("p",)
    assert manifest[0]["positive_count"] == 1
    assert exclusions == {"UNRESOLVED_OR_IMPURE_QUERY": 2}
    # The public pool digest uses exactly the three P8 fields, not positive labels.
    same = [{**row, "positive_refs": ("different-evaluation-ref",)} for row in manifest]
    assert _p8_pool_digest(manifest) == _p8_pool_digest(same)


def _perception(counts: dict[str, int]) -> PerceptionResult:
    measurements = tuple(Measurement(
        observation_id=f"{track}:{index}", local_track_id=track, camera_id="CAM", model_id="model",
        run_id="run", timestamp=index * 0.4, frame_ref=f"frame:{track}:{index}",
        bbox_xyxy=(10, 10, 20, 40), contact_pixel=(15, 39), appearance=(20, 40, 200),
        uncertainty=0.25, input_sha256="a" * 64, status="DETECTED", local_alternative_count=0,
        evidence_refs=(f"frame:{track}:{index}",),
    ) for track, count in counts.items() for index in range(count))
    tracks = tuple(LocalTrack(
        local_track_id=track, camera_id="CAM", model_id="model", run_id="run",
        observation_ids=tuple(f"{track}:{index}" for index in range(count)),
        timestamps=tuple(index * 0.4 for index in range(count)), status="COMPLETE",
        missing_timestamps=(), termination_reason="SEQUENCE_END",
    ) for track, count in counts.items())
    return PerceptionResult(
        model_id="model", run_id="run", measurements=measurements, tracks=tracks,
        frame_statuses=(), input_manifest_sha256="b" * 64, producer_sha256="c" * 64, complete=True,
    )


def test_reused_p8_label_policy_excludes_unresolved_mixed_and_insufficient_coverage() -> None:
    perception = _perception({"pure": 4, "unknown": 2, "mixed": 2, "low-known": 3})
    labels = {row.observation_id: None for row in perception.measurements}
    labels.update({"pure:0": "a", "pure:1": "a", "pure:2": "a",
                   "mixed:0": "a", "mixed:1": "b", "low-known:0": "a", "low-known:1": "a"})
    resolved, counts, details = _track_labels(perception, labels)
    assert resolved == {"pure": "a", "unknown": None, "mixed": None, "low-known": None}
    assert counts["track_label_status_counts"] == {
        "PURE_SUFFICIENTLY_LABELED": 1, "UNRESOLVED": 1,
        "MIXED_KNOWN_IDENTITIES": 1, "INSUFFICIENT_KNOWN_COVERAGE": 1,
    }
    assert len(details) == 4


def test_no_produced_positive_is_excluded_before_descriptor_ranking() -> None:
    package = ResearchPackage.model_construct(adjacency=())
    rows = [_track("q"), _track("negative")]
    pool, exclusions = _pool_manifest(package, rows, {"q": "a", "negative": "b"})
    report, details = _retrieval(pool, {"q": None, "negative": None}, {}, math.dist)
    assert exclusions["NO_ELIGIBLE_SAME_IDENTITY_PRODUCED_TARGET"] == 2
    assert report["eligible_queries"] == 0
    assert report["tie_aware_recall_at_k"] == {"1": None, "3": None, "5": None}
    assert details == []


def test_track_aggregation_uses_all_original_crops_and_no_identity_label() -> None:
    perception = _perception({"local": 3})
    vector = (1 / 12,) * 12 + (0.25,) * 4 + (0.2, 0.3, 0.5, 0.1) * 4
    samples = tuple(CropDescriptor(
        observation_id=row.observation_id, local_track_id=row.local_track_id,
        frame_ref=row.frame_ref, camera_id=row.camera_id, timestamp=row.timestamp,
        input_sha256=row.input_sha256, status="READY", vector=vector, quality=0.6,
    ) for row in perception.measurements)
    bundle = RGBDescriptorBundle.model_construct(
        config=AssociationConfig(), measurement_descriptors=samples, segment_descriptors=(),
    )
    profiles = _track_profiles(perception, bundle)
    assert profiles["local"].observation_ids == ("local:0", "local:1", "local:2")
    assert profiles["local"].usable_measurements == profiles["local"].retained_measurements == 3
    assert profiles["local"].vector is not None
    assert profiles == _track_profiles(
        perception, bundle.model_copy(update={"measurement_descriptors": tuple(reversed(samples))}),
    )
    with pytest.raises(ValueError, match="crop population mismatch"):
        _track_profiles(
            perception, bundle.model_copy(update={"measurement_descriptors": samples[:2]}),
        )
    mismatched = samples[0].model_copy(update={"local_track_id": "foreign"})
    with pytest.raises(ValueError, match="crop measurement binding mismatch"):
        _track_profiles(perception, bundle.model_copy(
            update={"measurement_descriptors": (mismatched, *samples[1:])},
        ))
