"""R2 proves indexed scope/time locality, direction, overlap and honest budgets."""

import math

import pytest

from amidst.engineering.local_index import (
    CameraLink,
    CameraRegions,
    IndexRecord,
    RegionLink,
    RetrievalPolicy,
    ScopedLocalIndex,
    ScopedTopology,
)
from amidst.engineering.registry import ResourceScope, opaque_ref, scope_parts


def scope(run: str = "run") -> ResourceScope:
    return ResourceScope(
        place_id="lab",
        model_id="lab",
        model_revision="1",
        run_id=run,
        source_id="source",
        source_sha256="a" * 64,
        spatial_context_id="context",
        spatial_context_sha256="b" * 64,
        clock_id="configured-seconds",
    )


def row(
    camera: str,
    start: float,
    *,
    end: float | None = None,
    identity: str = "",
    run: str = "run",
    kind: str = "TRACK",
) -> IndexRecord:
    values = dict(
        scope=scope(run),
        record_ref=opaque_ref("track", *scope_parts(scope(run)), camera, str(start), identity),
        camera_id=camera,
        start_time=start,
        end_time=start if end is None else end,
        kind=kind,
        region_ids=(camera.lower(),),
        portal_refs=("portal:door",),
    )
    return IndexRecord.model_validate(values)


def topology(run: str = "run", *, mapping: bool = True, complete: bool = True) -> ScopedTopology:
    return ScopedTopology(
        scope=scope(run),
        camera_ids=("A", "B", "C", "ISLAND"),
        camera_links=(
            CameraLink(from_camera_id="A", to_camera_id="B"),
            CameraLink(from_camera_id="B", to_camera_id="C"),
        ),
        camera_regions=tuple(
            CameraRegions(camera_id=camera, region_ids=(camera.lower(),))
            for camera in ("A", "B", "C", "ISLAND")
        ),
        region_links=(RegionLink(from_region_id="a", to_region_id="b", portal_ref="portal:door"),),
        topology_complete=complete,
        clock_mapping_sha256="c" * 64 if mapping else None,
    )


def test_many_unrelated_scopes_cameras_and_times_do_not_expand_reads() -> None:
    anchor, nearby = row("A", 100), row("B", 102)
    baseline = ScopedLocalIndex((anchor, nearby), (topology(),))
    foreign = tuple(row("A", float(index), run="other") for index in range(4000))
    old = tuple(row("B", float(index) / 100, identity="old") for index in range(4000))
    late = tuple(row("B", 1000 + float(index), identity="late") for index in range(4000))
    island = tuple(row("ISLAND", 101, identity=str(index)) for index in range(4000))
    expanded = ScopedLocalIndex(
        (anchor, nearby, *foreign, *old, *late, *island), (topology(), topology("other"))
    )
    one = baseline.retrieve_successors(scope(), anchor.record_ref)
    many = expanded.retrieve_successors(scope(), anchor.record_ref)
    assert many == one
    assert many.candidate_refs == (nearby.record_ref,)
    assert many.touched_camera_ids == ("A", "B", "C")
    # One direct anchor plus one A row and one B row materialized; no global scan.
    assert many.records_read == 3 and many.index_entries_touched == 2
    assert many.pairs_considered == 1 and many.frames_read == many.bytes_read == 0
    assert many.local_inventory_complete
    assert not many.excluded_outside_window_are_physical_rejections


def test_bounded_multihop_preserves_direction_and_stop_reason() -> None:
    anchor, b, c = row("A", 0), row("B", 1), row("C", 2)
    index = ScopedLocalIndex((anchor, b, c), (topology(),))
    full = index.retrieve_successors(scope(), anchor.record_ref)
    assert full.candidate_refs == (b.record_ref, c.record_ref)
    limited = index.retrieve_successors(scope(), anchor.record_ref, RetrievalPolicy(max_hops=1))
    assert limited.candidate_refs == (b.record_ref,)
    assert "MAX_HOPS_REACHED" in limited.truncation_reasons
    assert not limited.local_inventory_complete
    reverse = index.retrieve_successors(scope(), c.record_ref)
    assert reverse.candidate_refs == () and reverse.touched_camera_ids == ("C",)
    budget = index.retrieve_successors(scope(), anchor.record_ref, RetrievalPolicy(max_cameras=1))
    assert "MAX_CAMERAS_REACHED" in budget.truncation_reasons


def test_window_expansion_and_record_budget_report_omitted_arrivals() -> None:
    anchor, late, outside = row("A", 0), row("B", 8), row("B", 20)
    index = ScopedLocalIndex((anchor, late, outside), (topology(),))
    result = index.retrieve_successors(
        scope(), anchor.record_ref, RetrievalPolicy(window_steps_s=(2, 10))
    )
    assert result.candidate_refs == (late.record_ref,)
    assert result.expansions == 2
    assert result.stop_reasons == ("FINITE_LOOKUP_WINDOW_EXHAUSTED",)
    assert result.retrieval_coverage == "SCOPED_FINITE_WINDOW"
    bounded = ScopedLocalIndex((anchor, late, row("B", 9)), (topology(),)).retrieve_successors(
        scope(),
        anchor.record_ref,
        RetrievalPolicy(max_records=1),
    )
    assert bounded.candidate_refs == (late.record_ref,)
    assert "MAX_RECORDS_REACHED" in bounded.truncation_reasons


def test_missing_clock_coverage_and_wrong_scope_fail_closed() -> None:
    anchor = row("A", 0)
    index = ScopedLocalIndex((anchor,), (topology(mapping=False),))
    result = index.retrieve_successors(scope(), anchor.record_ref)
    assert result.candidate_refs == () and result.records_read == 1
    assert result.retrieval_coverage == "UNAVAILABLE"
    assert result.truncation_reasons == ("CLOCK_MAPPING_MISSING",)
    with pytest.raises(ValueError, match="scope index is unavailable"):
        index.record(scope("other"), anchor.record_ref)
    with pytest.raises(ValueError, match="exact scope"):
        index.record(scope(), opaque_ref("track", "missing"))
    incomplete = ScopedLocalIndex((anchor,), (topology(complete=False),))
    assert (
        "TOPOLOGY_INCOMPLETE"
        in incomplete.retrieve_successors(
            scope(),
            anchor.record_ref,
        ).truncation_reasons
    )


def test_interval_tree_finds_long_overlap_without_scanning_old_prefix() -> None:
    sustained = row("B", 0, end=10000, kind="OBSERVATION")
    old = tuple(
        row("B", float(index), identity="old", kind="OBSERVATION") for index in range(1, 5000)
    )
    current = row("B", 9000, kind="OBSERVATION")
    index = ScopedLocalIndex((sustained, *old, current), (topology(),))
    result = index.camera_records(scope(), "B", 8999, 9001, kind="OBSERVATION")
    assert {r.record_ref for r in result.records} == {sustained.record_ref, current.record_ref}
    assert result.records_read == 2 and result.index_entries_touched < 40
    assert not result.truncated
    assert index.region_records(scope(), "b", 8999, 9001).records == result.records
    assert index.portal_records(scope(), "portal:door", 8999, 9001).records == result.records
    assert index.cameras_for_region(scope(), "a") == ("A",)
    assert index.region_links(scope(), "a") == index.portal_links(scope(), "portal:door")


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -1])
def test_invalid_time_query_has_no_unbounded_fallback(invalid: float) -> None:
    index = ScopedLocalIndex((), (topology(),))
    with pytest.raises(ValueError, match="finite ordered interval"):
        index.camera_records(scope(), "A", 0, invalid)


def test_overlap_budget_does_not_materialize_all_matching_records() -> None:
    rows = tuple(row("A", 0, end=100, identity=str(index)) for index in range(2000))
    index = ScopedLocalIndex(rows, (topology(),))
    query = index.camera_records(scope(), "A", 10, 20, limit=3)
    assert query.records_read == 3 and query.truncated
    assert query.index_entries_touched == 5  # one tree node and four bounded refs.
