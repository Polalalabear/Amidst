"""Import-built scoped indices and bounded local retrieval, with no truth channel.

Catalog construction is an explicit import operation. Queries use opaque references,
interval trees / bisect and directed adjacency; none iterate a catalog or pair pool.
Finite time and expansion limits describe retrieval coverage, never physical rejection.
"""

from __future__ import annotations

import heapq
import math
from bisect import bisect_left, bisect_right
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Literal, Self

from pydantic import Field, FiniteFloat, model_validator

from amidst.domain.common import DomainModel, PositiveFinite, Timestamp
from amidst.engineering.registry import ResourceScope, scope_parts

RecordKind = Literal["FRAME", "TRACK", "OBSERVATION", "EVENT"]
ScopeKey = tuple[str, ...]


class IndexRecord(DomainModel):
    scope: ResourceScope
    record_ref: str = Field(pattern=r"^[a-z]+:[0-9a-f]{24}$")
    kind: RecordKind
    camera_id: str | None = None
    start_time: Timestamp
    end_time: Timestamp
    region_ids: tuple[str, ...] = ()
    portal_refs: tuple[str, ...] = ()
    size_bytes: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def ordered_interval(self) -> Self:
        if self.end_time < self.start_time:
            raise ValueError("index interval must be ordered")
        return self


class CameraLink(DomainModel):
    from_camera_id: str = Field(min_length=1)
    to_camera_id: str = Field(min_length=1)
    minimum_path_length_m: FiniteFloat = Field(default=0, ge=0)
    portal_refs: tuple[str, ...] = ()


class CameraRegions(DomainModel):
    camera_id: str = Field(min_length=1)
    region_ids: tuple[str, ...] = ()
    coverage_known: bool = True


class RegionLink(DomainModel):
    from_region_id: str = Field(min_length=1)
    to_region_id: str = Field(min_length=1)
    portal_ref: str = Field(min_length=1)


class ScopedTopology(DomainModel):
    scope: ResourceScope
    camera_ids: tuple[str, ...]
    camera_links: tuple[CameraLink, ...] = ()
    camera_regions: tuple[CameraRegions, ...] = ()
    region_links: tuple[RegionLink, ...] = ()
    topology_complete: bool = False
    clock_mapping_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    clock_uncertainty_s: FiniteFloat = Field(default=0, ge=0)

    @model_validator(mode="after")
    def valid_topology(self) -> Self:
        cameras = set(self.camera_ids)
        if len(cameras) != len(self.camera_ids):
            raise ValueError("topology camera IDs must be unique")
        if any(
            link.from_camera_id not in cameras
            or link.to_camera_id not in cameras
            or link.from_camera_id == link.to_camera_id
            for link in self.camera_links
        ):
            raise ValueError("camera adjacency must reference distinct scoped cameras")
        if len({(link.from_camera_id, link.to_camera_id) for link in self.camera_links}) != (
            len(self.camera_links)
        ):
            raise ValueError("directed camera links must be unique")
        if len({row.camera_id for row in self.camera_regions}) != len(self.camera_regions) or any(
            row.camera_id not in cameras for row in self.camera_regions
        ):
            raise ValueError("camera coverage must uniquely reference scoped cameras")
        return self


class RetrievalPolicy(DomainModel):
    window_steps_s: tuple[PositiveFinite, ...] = (12.0,)
    max_hops: int = Field(default=3, ge=0)
    max_cameras: int = Field(default=32, gt=0)
    max_records: int = Field(default=128, gt=0)

    @model_validator(mode="after")
    def growing_windows(self) -> Self:
        if not self.window_steps_s or any(
            b <= a for a, b in zip(self.window_steps_s, self.window_steps_s[1:], strict=False)
        ):
            raise ValueError("retrieval windows must be nonempty and strictly increasing")
        return self


class IndexQueryResult(DomainModel):
    scope: ResourceScope
    records: tuple[IndexRecord, ...]
    records_read: int = Field(ge=0)
    index_entries_touched: int = Field(ge=0)
    bytes_read: int = Field(ge=0)
    truncated: bool


class RetrievalReceipt(DomainModel):
    """Deterministic counts; wall-clock latency belongs in external telemetry."""

    scope: ResourceScope
    anchor_ref: str
    candidate_refs: tuple[str, ...]
    touched_camera_ids: tuple[str, ...]
    records_read: int = Field(ge=0)
    index_entries_touched: int = Field(ge=0)
    pairs_considered: int = Field(ge=0)
    frames_read: int = Field(default=0, ge=0)
    crops_read: int = Field(default=0, ge=0)
    bytes_read: int = Field(default=0, ge=0)
    expansions: int = Field(ge=0)
    lookup_window_s: PositiveFinite
    maximum_hops: int = Field(ge=0)
    stop_reasons: tuple[str, ...]
    truncation_reasons: tuple[str, ...]
    retrieval_coverage: Literal["SCOPED_FINITE_WINDOW", "UNAVAILABLE"]
    local_inventory_complete: bool
    # This field cannot express, or replace, Graph search completeness.
    excluded_outside_window_are_physical_rejections: Literal[False] = False

    @model_validator(mode="after")
    def consistent_receipt(self) -> Self:
        if (
            len(set(self.candidate_refs)) != len(self.candidate_refs)
            or (self.anchor_ref in self.candidate_refs)
            or self.pairs_considered != len(self.candidate_refs)
        ):
            raise ValueError(
                "retrieval receipt requires unique non-anchor candidate refs and counts"
            )
        if len(set(self.touched_camera_ids)) != len(self.touched_camera_ids):
            raise ValueError("retrieval touched cameras must be unique")
        complete = self.retrieval_coverage == "SCOPED_FINITE_WINDOW" and not self.truncation_reasons
        if self.local_inventory_complete != complete:
            raise ValueError("retrieval completeness must retain coverage and truncation")
        if self.records_read < 1 + len(self.candidate_refs):
            raise ValueError("retrieval reads must include the anchor and returned candidates")
        return self


@dataclass(frozen=True)
class _IntervalNode:
    centre: float
    starts: tuple[float, ...]
    start_refs: tuple[str, ...]
    ends: tuple[float, ...]
    end_refs: tuple[str, ...]
    left: _IntervalNode | None
    right: _IntervalNode | None


def _interval_tree(records: list[IndexRecord]) -> _IntervalNode | None:
    if not records:
        return None
    centres = sorted((row.start_time + row.end_time) / 2 for row in records)
    centre = centres[len(centres) // 2]
    left, right, crossing = [], [], []
    for row in records:
        if row.end_time < centre:
            left.append(row)
        elif row.start_time > centre:
            right.append(row)
        else:
            crossing.append(row)
    by_start = sorted(crossing, key=lambda row: (row.start_time, row.record_ref))
    by_end = sorted(crossing, key=lambda row: (row.end_time, row.record_ref))
    return _IntervalNode(
        centre,
        tuple(row.start_time for row in by_start),
        tuple(row.record_ref for row in by_start),
        tuple(row.end_time for row in by_end),
        tuple(row.record_ref for row in by_end),
        _interval_tree(left),
        _interval_tree(right),
    )


def _overlap_refs(
    node: _IntervalNode | None, start: float, end: float, refs: list[str], budget: int
) -> int:
    if node is None or len(refs) >= budget:
        return 0
    touched = 1
    if end < node.centre:
        count = bisect_right(node.starts, end)
        take = node.start_refs[: min(count, budget - len(refs))]
        refs.extend(take)
        return (
            touched
            + len(take)
            + _overlap_refs(
                node.left,
                start,
                end,
                refs,
                budget,
            )
        )
    if start > node.centre:
        low = bisect_left(node.ends, start)
        take = node.end_refs[low : low + budget - len(refs)]
        refs.extend(take)
        return touched + len(take) + _overlap_refs(node.right, start, end, refs, budget)
    take = node.start_refs[: budget - len(refs)]
    refs.extend(take)
    touched += len(take)
    touched += _overlap_refs(node.left, start, end, refs, budget)
    return touched + _overlap_refs(node.right, start, end, refs, budget)


class ScopedLocalIndex:
    """One import-built inventory. Scope mismatches and missing indices fail closed."""

    def __init__(
        self, records: tuple[IndexRecord, ...], topologies: tuple[ScopedTopology, ...]
    ) -> None:
        self._records: dict[tuple[ScopeKey, str], IndexRecord] = {}
        self._topologies: dict[ScopeKey, ScopedTopology] = {}
        self._adjacency: dict[tuple[ScopeKey, str], tuple[str, ...]] = {}
        self._camera_links: dict[tuple[ScopeKey, str], tuple[CameraLink, ...]] = {}
        self._coverage: dict[tuple[ScopeKey, str], CameraRegions] = {}
        self._region_cameras: dict[tuple[ScopeKey, str], tuple[str, ...]] = {}
        self._region_adjacency: dict[tuple[ScopeKey, str], tuple[RegionLink, ...]] = {}
        self._portal_links: dict[tuple[ScopeKey, str], tuple[RegionLink, ...]] = {}
        for topology in topologies:
            key = scope_parts(topology.scope)
            if key in self._topologies:
                raise ValueError("each index scope requires a unique topology")
            self._topologies[key] = topology
            camera_links: dict[str, list[str]] = defaultdict(list)
            path_links: dict[str, list[CameraLink]] = defaultdict(list)
            region_cameras: dict[str, list[str]] = defaultdict(list)
            region_links: dict[str, list[RegionLink]] = defaultdict(list)
            portal_links: dict[str, list[RegionLink]] = defaultdict(list)
            for link in topology.camera_links:
                camera_links[link.from_camera_id].append(link.to_camera_id)
                path_links[link.from_camera_id].append(link)
            for camera in topology.camera_ids:
                self._adjacency[key, camera] = tuple(sorted(camera_links[camera]))
                self._camera_links[key, camera] = tuple(path_links[camera])
            for coverage in topology.camera_regions:
                self._coverage[key, coverage.camera_id] = coverage
                for region in coverage.region_ids:
                    region_cameras[region].append(coverage.camera_id)
            for region_link in topology.region_links:
                region_links[region_link.from_region_id].append(region_link)
                portal_links[region_link.portal_ref].append(region_link)
            self._region_cameras.update(
                {
                    (key, region): tuple(sorted(cameras))
                    for region, cameras in region_cameras.items()
                }
            )
            self._region_adjacency.update(
                {(key, region): tuple(links) for region, links in region_links.items()}
            )
            self._portal_links.update(
                {(key, portal): tuple(links) for portal, links in portal_links.items()}
            )
        buckets: dict[tuple[ScopeKey, str, str, str], list[IndexRecord]] = defaultdict(list)
        for record in records:
            key = scope_parts(record.scope)
            if key not in self._topologies:
                raise ValueError("record scope lacks an imported topology")
            identity = key, record.record_ref
            if identity in self._records:
                raise ValueError("scoped record references must be unique")
            self._records[identity] = record
            selectors = []
            if record.camera_id is not None:
                selectors.append(("camera", record.camera_id))
            selectors.extend(("region", region) for region in record.region_ids)
            selectors.extend(("portal", portal) for portal in record.portal_refs)
            for selector, value in selectors:
                buckets[key, selector, value, "ANY"].append(record)
                buckets[key, selector, value, record.kind].append(record)
        self._trees = {key: _interval_tree(rows) for key, rows in buckets.items()}
        self._starts: dict[tuple[ScopeKey, str, str, str], tuple[float, ...]] = {}
        self._start_refs: dict[tuple[ScopeKey, str, str, str], tuple[str, ...]] = {}
        for bucket_key, rows in buckets.items():
            ordered = sorted(rows, key=lambda row: (row.start_time, row.end_time, row.record_ref))
            self._starts[bucket_key] = tuple(row.start_time for row in ordered)
            self._start_refs[bucket_key] = tuple(row.record_ref for row in ordered)

    def topology(self, scope: ResourceScope) -> ScopedTopology:
        try:
            return self._topologies[scope_parts(scope)]
        except KeyError as error:
            raise ValueError("scope index is unavailable; global fallback is forbidden") from error

    def record(self, scope: ResourceScope, record_ref: str) -> IndexRecord:
        self.topology(scope)
        try:
            return self._records[scope_parts(scope), record_ref]
        except KeyError as error:
            raise ValueError(
                "opaque record reference is unavailable in this exact scope"
            ) from error

    def minimum_path_length_m(
        self, scope: ResourceScope, from_camera_id: str, to_camera_id: str, *, max_hops: int = 3
    ) -> float | None:
        """Configured legal path lower bound; never a camera-centre distance proxy."""
        self.topology(scope)
        key = scope_parts(scope)
        queue = [(0.0, 0, from_camera_id)]
        best: dict[tuple[str, int], float] = {(from_camera_id, 0): 0.0}
        while queue:
            distance, hops, camera = heapq.heappop(queue)
            if camera == to_camera_id:
                return distance
            if hops >= max_hops or distance > best.get((camera, hops), math.inf):
                continue
            for link in self._camera_links.get((key, camera), ()):
                candidate = distance + link.minimum_path_length_m
                state = link.to_camera_id, hops + 1
                if candidate < best.get(state, math.inf):
                    best[state] = candidate
                    heapq.heappush(queue, (candidate, hops + 1, link.to_camera_id))
        return None

    def cameras_for_region(self, scope: ResourceScope, region_id: str) -> tuple[str, ...]:
        self.topology(scope)
        return self._region_cameras.get((scope_parts(scope), region_id), ())

    def region_links(self, scope: ResourceScope, region_id: str) -> tuple[RegionLink, ...]:
        self.topology(scope)
        return self._region_adjacency.get((scope_parts(scope), region_id), ())

    def portal_links(self, scope: ResourceScope, portal_ref: str) -> tuple[RegionLink, ...]:
        self.topology(scope)
        return self._portal_links.get((scope_parts(scope), portal_ref), ())

    def _query(
        self,
        scope: ResourceScope,
        selector: str,
        value: str,
        start_time: float,
        end_time: float,
        *,
        kind: RecordKind | None,
        limit: int,
        starts_within: bool = False,
    ) -> IndexQueryResult:
        self.topology(scope)
        if (
            not (math.isfinite(start_time) and math.isfinite(end_time))
            or not (0 <= start_time <= end_time)
            or limit < 1
        ):
            raise ValueError("query requires a finite ordered interval and positive limit")
        key = scope_parts(scope), selector, value, kind or "ANY"
        refs: list[str] = []
        if starts_within:
            starts = self._starts.get(key, ())
            low, high = bisect_left(starts, start_time), bisect_right(starts, end_time)
            refs.extend(self._start_refs.get(key, ())[low : min(high, low + limit + 1)])
            touched = len(refs)
        else:
            touched = _overlap_refs(self._trees.get(key), start_time, end_time, refs, limit + 1)
        truncated = len(refs) > limit
        selected = tuple(self._records[scope_parts(scope), ref] for ref in refs[:limit])
        selected = tuple(
            sorted(selected, key=lambda row: (row.start_time, row.end_time, row.record_ref))
        )
        return IndexQueryResult(
            scope=scope,
            records=selected,
            records_read=len(selected),
            index_entries_touched=touched,
            bytes_read=0,  # Reference lookup reads no media payload bytes.
            truncated=truncated,
        )

    def camera_records(
        self,
        scope: ResourceScope,
        camera_id: str,
        start_time: float,
        end_time: float,
        *,
        kind: RecordKind | None = None,
        limit: int = 128,
        starts_within: bool = False,
    ) -> IndexQueryResult:
        return self._query(
            scope,
            "camera",
            camera_id,
            start_time,
            end_time,
            kind=kind,
            limit=limit,
            starts_within=starts_within,
        )

    def region_records(
        self,
        scope: ResourceScope,
        region_id: str,
        start_time: float,
        end_time: float,
        *,
        kind: RecordKind | None = None,
        limit: int = 128,
    ) -> IndexQueryResult:
        return self._query(scope, "region", region_id, start_time, end_time, kind=kind, limit=limit)

    def portal_records(
        self,
        scope: ResourceScope,
        portal_ref: str,
        start_time: float,
        end_time: float,
        *,
        kind: RecordKind | None = None,
        limit: int = 128,
    ) -> IndexQueryResult:
        return self._query(
            scope, "portal", portal_ref, start_time, end_time, kind=kind, limit=limit
        )

    def retrieve_successors(
        self, scope: ResourceScope, anchor_ref: str, policy: RetrievalPolicy | None = None
    ) -> RetrievalReceipt:
        policy = policy or RetrievalPolicy()
        topology = self.topology(scope)
        anchor = self.record(scope, anchor_ref)
        if anchor.kind != "TRACK" or anchor.camera_id is None:
            raise ValueError("association anchor requires a camera-local TRACK record")
        if topology.clock_mapping_sha256 is None or anchor.camera_id not in topology.camera_ids:
            reason = (
                "CLOCK_MAPPING_MISSING"
                if topology.clock_mapping_sha256 is None
                else ("ANCHOR_CAMERA_TOPOLOGY_MISSING")
            )
            return RetrievalReceipt(
                scope=scope,
                anchor_ref=anchor_ref,
                candidate_refs=(),
                touched_camera_ids=(),
                records_read=1,
                index_entries_touched=0,
                pairs_considered=0,
                expansions=0,
                lookup_window_s=policy.window_steps_s[-1],
                maximum_hops=policy.max_hops,
                stop_reasons=(reason,),
                truncation_reasons=(reason,),
                retrieval_coverage="UNAVAILABLE",
                local_inventory_complete=False,
            )
        key = scope_parts(scope)
        queue = deque([(anchor.camera_id, 0)])
        visited: set[str] = {anchor.camera_id}
        cameras: list[str] = []
        truncation: set[str] = set()
        while queue:
            camera, hops = queue.popleft()
            cameras.append(camera)
            if not self._coverage.get(
                (key, camera),
                CameraRegions(
                    camera_id=camera,
                    coverage_known=False,
                ),
            ).coverage_known:
                truncation.add("CAMERA_COVERAGE_UNKNOWN")
            for neighbor in self._adjacency.get((key, camera), ()):
                if neighbor in visited:
                    continue
                if hops >= policy.max_hops:
                    truncation.add("MAX_HOPS_REACHED")
                elif len(visited) >= policy.max_cameras:
                    truncation.add("MAX_CAMERAS_REACHED")
                else:
                    visited.add(neighbor)
                    queue.append((neighbor, hops + 1))
        if not topology.topology_complete:
            truncation.add("TOPOLOGY_INCOMPLETE")
        candidates: dict[str, IndexRecord] = {}
        records_read, entries_touched, expansions = 1, 0, 0
        lower = anchor.start_time
        touched: list[str] = []
        for window in policy.window_steps_s:
            upper = anchor.end_time + window + topology.clock_uncertainty_s
            expansions += 1
            for camera in cameras:
                touched.append(camera)
                result = self.camera_records(
                    scope,
                    camera,
                    lower,
                    upper,
                    kind="TRACK",
                    limit=policy.max_records + 1,
                    starts_within=True,
                )
                records_read += result.records_read
                entries_touched += result.index_entries_touched
                if result.truncated:
                    truncation.add("MAX_RECORDS_REACHED")
                for row in result.records:
                    if row.record_ref == anchor_ref:
                        continue
                    # Ordering removes reverse and duplicate pairs before pair formation.
                    if (row.start_time, row.end_time, row.record_ref) <= (
                        anchor.start_time,
                        anchor.end_time,
                        anchor.record_ref,
                    ):
                        continue
                    if row.record_ref not in candidates:
                        if len(candidates) >= policy.max_records:
                            truncation.add("MAX_RECORDS_REACHED")
                            break
                        candidates[row.record_ref] = row
            lower = upper  # one boundary may repeat; direct ref dedup is explicit.
            if "MAX_RECORDS_REACHED" in truncation:
                break
        ordered = sorted(
            candidates.values(), key=lambda row: (row.start_time, row.end_time, row.record_ref)
        )
        return RetrievalReceipt(
            scope=scope,
            anchor_ref=anchor_ref,
            candidate_refs=tuple(row.record_ref for row in ordered),
            touched_camera_ids=tuple(dict.fromkeys(touched)),
            records_read=records_read,
            index_entries_touched=entries_touched,
            pairs_considered=len(ordered),
            expansions=expansions,
            lookup_window_s=policy.window_steps_s[-1],
            maximum_hops=policy.max_hops,
            stop_reasons=("FINITE_LOOKUP_WINDOW_EXHAUSTED",),
            truncation_reasons=tuple(sorted(truncation)),
            retrieval_coverage="SCOPED_FINITE_WINDOW",
            local_inventory_complete=not truncation,
        )
