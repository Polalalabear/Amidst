"""Persistent freeze scopes, paged canonical reads and append-only evidence."""

import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from amidst.engineering.registry import ResourceScope, content_hash, opaque_ref
from amidst.product.store import (
    CanonicalRecord,
    Payload,
    ProductScope,
    RecordQuery,
    RecordSetReceipt,
    SQLiteProductStore,
    StoreConflict,
    StoreError,
    StoreIntegrityError,
)


def scope(run_id: str = "run-1", mode: str = "photos_only") -> ProductScope:
    return ProductScope.model_validate_json(json.dumps({
        "resource_scope": ResourceScope(
            place_id="lab", model_id="synthetic-lab", model_revision="1", run_id=run_id,
            source_id="procedural-rgb", source_sha256="a" * 64, spatial_context_id="lab-context",
            spatial_context_sha256="b" * 64, clock_id="lab-seconds",
        ).model_dump(mode="json"),
        "observation_mode": mode,
        **{name + "_sha256": "c" * 64 for name in
           ("dataset", "config", "producer", "registry", "media", "inference", "freeze")},
    }))


def record(
    binding: ProductScope, number: int = 0, *, time_range: tuple[float, float] = (0, 1),
    camera_ids: tuple[str, ...] = ("CAM_A",), region_ids: tuple[str, ...] = ("west",),
    payload: Payload | None = None,
) -> CanonicalRecord:
    return CanonicalRecord.create(
        run_ref=binding.run_ref, kind="EVENT", record_ref=opaque_ref("event", str(number)),
        camera_ids=camera_ids, region_ids=region_ids, time_range=time_range,
        payload={"event_id": f"canonical-event-{number}",
                 "candidates": [{"order": 1}, {"order": 0}],
                 "complete": False, "termination_reason": "MAX_CANDIDATES_REACHED"}
        if payload is None else payload,
    )


def import_batch(
    store: SQLiteProductStore, binding: ProductScope, rows: tuple[CanonicalRecord, ...],
) -> None:
    assert store.import_records(binding, rows, RecordSetReceipt.create(binding, rows)).inserted


def test_restart_idempotence_preserves_canonical_records(tmp_path: Path) -> None:
    path = tmp_path / "product.sqlite"
    binding = scope()
    rows = (record(binding), record(binding, 1, time_range=(1, 2)))
    originals = tuple(row.model_dump_json() for row in rows)
    receipt = RecordSetReceipt.create(binding, rows)
    with SQLiteProductStore(path) as store:
        result = store.import_records(binding, rows, receipt)
        assert result.inserted and result.record_count == 2
        assert store.verify_run(binding.run_ref) == receipt
        assert not store.import_records(binding, tuple(reversed(rows)), receipt).inserted
    with SQLiteProductStore(path) as reopened:
        assert reopened.list_runs() == (binding,)
        assert reopened.get_scope(binding.run_ref) == binding
        loaded = tuple(reopened.get_record(binding.run_ref, "EVENT", row.record_ref)
                       for row in rows)
        assert tuple(item.model_dump_json() for item in loaded) == originals
        assert loaded[0].payload["candidates"] == [{"order": 1}, {"order": 0}]
        assert loaded[0].payload["complete"] is False


def test_closed_overlap_camera_region_and_empty_indexed_queries(tmp_path: Path) -> None:
    binding = scope()
    rows = (record(binding, 0, time_range=(0, 1)),
            record(binding, 1, time_range=(1, 4), camera_ids=("CAM_A", "CAM_B"),
                   region_ids=("west", "central")),
            record(binding, 2, time_range=(4, 4), camera_ids=("CAM_B",), region_ids=("east",)))
    with SQLiteProductStore(tmp_path / "store.sqlite") as store:
        import_batch(store, binding, rows)
        query = RecordQuery(run_ref=binding.run_ref, kind="EVENT", time_range=(1, 1),
                            camera_id="CAM_A", region_id="west")
        page = store.query_records(query)
        assert page.records == rows[:2] and page.query_complete
        assert page.next_cursor is None
        assert store.query_records(RecordQuery(run_ref=binding.run_ref, kind="EVENT",
                                              time_range=(4, 4))).records == rows[1:]
        assert store.query_records(RecordQuery(run_ref=binding.run_ref, kind="OBSERVATION",
                                              time_range=(0, 5))).records == ()
        assert store.query_records(RecordQuery(run_ref=binding.run_ref, kind="EVENT",
                                              time_range=(0, 5), region_id="missing")).records == ()
        assert store.query_records(RecordQuery(run_ref=binding.run_ref, kind="EVENT",
                                              time_range=(0, 5),
                                              camera_id="CAM_A' OR 1=1 --")).records == ()
        plan = store._db.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM records WHERE run_ref=? AND kind=? "
            "AND start_time<=? AND end_time>=?", (binding.run_ref, "EVENT", 5, 0)
        ).fetchall()
        assert "records_interval" in str([tuple(row) for row in plan])


def test_stable_keyset_paging_preserves_equal_time_records(tmp_path: Path) -> None:
    binding = scope()
    rows = tuple(record(binding, n, time_range=(n // 3, n // 3 + 2)) for n in range(23))
    with SQLiteProductStore(tmp_path / "store.sqlite") as store:
        import_batch(store, binding, rows)
        query = RecordQuery(run_ref=binding.run_ref, kind="EVENT", time_range=(0, 20), limit=4)
        collected = []
        while True:
            page = store.query_records(query)
            collected.extend(page.records)
            assert page.query_complete == (page.next_cursor is None)
            if page.next_cursor is None:
                break
            query = RecordQuery.model_validate(query.model_dump() | {"cursor": page.next_cursor})
        assert tuple(collected) == tuple(sorted(rows, key=lambda r: (*r.time_range, r.record_ref)))
        assert len({r.record_ref for r in collected}) == len(rows)


@pytest.mark.parametrize("indexed", [False, True])
def test_record_ref_allowlist_is_applied_before_paging(
    tmp_path: Path, indexed: bool,
) -> None:
    binding = scope()
    rows = tuple(record(binding, n, time_range=(n // 3, n // 3 + 2)) for n in range(180))
    selected = rows[150:157] + rows[170:175]
    query = RecordQuery(
        run_ref=binding.run_ref, kind="EVENT", time_range=(0, 80), limit=3,
        record_refs=tuple(row.record_ref for row in selected),
        camera_id="CAM_A" if indexed else None,
        region_id="west" if indexed else None,
    )
    with SQLiteProductStore(tmp_path / "store.sqlite") as store:
        import_batch(store, binding, rows)
        collected = []
        while True:
            page = store.query_records(query)
            collected.extend(page.records)
            if page.next_cursor is None:
                assert page.query_complete
                break
            assert not page.query_complete
            query = RecordQuery.model_validate(query.model_dump() | {"cursor": page.next_cursor})
        assert tuple(collected) == tuple(sorted(
            selected, key=lambda row: (*row.time_range, row.record_ref),
        ))
        assert len({row.record_ref for row in collected}) == len(selected)
        # Explicitly absent refs do not widen the result or alter stored records.
        absent = RecordQuery.model_validate(query.model_dump() | {
            "cursor": None, "record_refs": (opaque_ref("event", "absent"),),
        })
        assert store.query_records(absent).records == ()
        assert store.verify_run(binding.run_ref) == RecordSetReceipt.create(binding, rows)


def test_record_ref_filter_binds_cursor_and_distinguishes_empty_from_all(tmp_path: Path) -> None:
    binding = scope()
    rows = tuple(record(binding, n, time_range=(n, n + 1)) for n in range(8))
    query = RecordQuery(run_ref=binding.run_ref, kind="EVENT", time_range=(0, 20), limit=1,
                        record_refs=tuple(row.record_ref for row in rows[3:6]))
    path = tmp_path / "store.sqlite"
    with SQLiteProductStore(path) as store:
        import_batch(store, binding, rows)
        first = store.query_records(query)
        assert first.records == rows[3:4]
        assert first.next_cursor is not None
        cursor = first.next_cursor
    with SQLiteProductStore(path) as store:
        continued = RecordQuery.model_validate(query.model_dump() | {"cursor": cursor})
        assert store.query_records(continued).records == rows[4:5]
        for other_refs in (None, (), tuple(row.record_ref for row in rows[4:7]),
                           tuple(reversed(query.record_refs or ()))):
            changed = RecordQuery.model_validate(continued.model_dump() | {
                "record_refs": other_refs,
            })
            with pytest.raises(StoreError, match="CURSOR_INVALID"):
                store.query_records(changed)
        empty_query = RecordQuery.model_validate(query.model_dump() | {"record_refs": ()})
        empty = store.query_records(empty_query)
        assert empty.records == () and empty.query_complete and empty.next_cursor is None
        all_query = RecordQuery.model_validate(query.model_dump() | {
            "record_refs": None, "limit": 50,
        })
        assert store.query_records(all_query).records == rows
        assert empty_query.filter_sha256 != all_query.filter_sha256


def test_record_ref_filter_is_bounded_and_rejects_duplicates() -> None:
    values = {"run_ref": scope().run_ref, "kind": "EVENT", "time_range": (0, 20)}
    with pytest.raises(ValidationError, match="RECORD_FILTER_DUPLICATE"):
        RecordQuery.model_validate(values | {
            "record_refs": (opaque_ref("event", "1"), opaque_ref("event", "1")),
        })
    with pytest.raises(ValidationError):
        RecordQuery.model_validate(values | {
            "record_refs": tuple(opaque_ref("event", str(n)) for n in range(4097)),
        })


def test_persistent_cursor_cannot_change_run_kind_or_filter(tmp_path: Path) -> None:
    path = tmp_path / "store.sqlite"
    binding, other = scope(), scope("other")
    query = RecordQuery(run_ref=binding.run_ref, kind="EVENT", time_range=(0, 5), limit=1)
    with SQLiteProductStore(path) as store:
        import_batch(store, binding, (record(binding), record(binding, 1)))
        import_batch(store, other, (record(other),))
        cursor = store.query_records(query).next_cursor
        assert cursor is not None
    with SQLiteProductStore(path) as store:
        continued = RecordQuery.model_validate(query.model_dump() | {"cursor": cursor})
        assert len(store.query_records(continued).records) == 1
        for changes in ({"run_ref": other.run_ref}, {"kind": "TRACK"}, {"camera_id": "CAM_B"},
                        {"region_id": "east"}, {"time_range": (1, 4)}, {"limit": 2},
                        {"cursor": cursor[:-1] + ("0" if cursor[-1] != "0" else "1")},
                        {"cursor": "random"}):
            changed = RecordQuery.model_validate(continued.model_dump() | changes)
            with pytest.raises(StoreError, match="CURSOR_INVALID"):
                store.query_records(changed)


def test_scopes_modes_and_freezes_are_distinct_and_transfer_fails(tmp_path: Path) -> None:
    first, other, plus = scope(), scope("other"), scope(mode="photos_plus_observations")
    assert len({first.run_ref, other.run_ref, plus.run_ref}) == 3
    with SQLiteProductStore(tmp_path / "store.sqlite") as store:
        import_batch(store, first, (record(first),))
        with pytest.raises(StoreConflict, match="SCOPE_OR_ID"):
            RecordSetReceipt.create(other, (record(first),))
        with pytest.raises(StoreError, match="RUN_UNAVAILABLE"):
            store.get_record(other.run_ref, "EVENT", record(first).record_ref)
        import_batch(store, other, (record(other),))
        import_batch(store, plus, (record(plus),))
        assert len(store.list_runs()) == 3


def test_receipt_covers_payload_and_indexes_and_rejects_conflicts(tmp_path: Path) -> None:
    binding = scope()
    original = record(binding)
    receipt = RecordSetReceipt.create(binding, (original,))
    with SQLiteProductStore(tmp_path / "store.sqlite") as store:
        import_batch(store, binding, (original,))
        altered = record(binding, payload={"event_id": "replaced"})
        with pytest.raises(StoreIntegrityError, match="RECEIPT_INVALID"):
            store.import_records(binding, (altered,), receipt)
        with pytest.raises(StoreConflict, match="IMMUTABLE_RUN_CONFLICT"):
            store.import_records(binding, (altered,), RecordSetReceipt.create(binding, (altered,)))
        changed_index = record(binding, camera_ids=("CAM_OTHER",))
        with pytest.raises(StoreIntegrityError, match="RECEIPT_INVALID"):
            store.import_records(binding, (changed_index,), receipt)
        assert store.get_record(binding.run_ref, "EVENT", original.record_ref) == original
        with pytest.raises(StoreConflict, match="SCOPE_OR_ID"):
            RecordSetReceipt.create(binding, (original, original))


def test_sql_failure_rolls_back_entire_run_and_first_insert(tmp_path: Path) -> None:
    binding = scope()
    rows = (record(binding), record(binding, 1))
    with SQLiteProductStore(tmp_path / "store.sqlite") as store:
        store._db.execute(
            "CREATE TRIGGER fail_second BEFORE INSERT ON records WHEN NEW.record_ref='" +
            rows[1].record_ref + "' BEGIN SELECT RAISE(ABORT,'test failure'); END"
        )
        with pytest.raises(StoreError, match="STORAGE_TRANSACTION_FAILED"):
            store.import_records(binding, rows, RecordSetReceipt.create(binding, rows))
        assert store.list_runs() == ()
        assert store._db.execute("SELECT count(*) FROM records").fetchone()[0] == 0
        store._db.execute("DROP TRIGGER fail_second")
        import_batch(store, binding, rows)


def test_empty_frozen_run_is_a_verified_complete_empty_result(tmp_path: Path) -> None:
    binding = scope()
    with SQLiteProductStore(tmp_path / "store.sqlite") as store:
        import_batch(store, binding, ())
        page = store.query_records(RecordQuery(run_ref=binding.run_ref, kind="EVENT",
                                              time_range=(0, 2)))
        assert page.records == () and page.query_complete and page.next_cursor is None
        assert store.verify_run(binding.run_ref).records == ()


@pytest.mark.parametrize("kind", ["CASE", "REPORT", "REVIEW"])
def test_append_only_revisions_restart_optimistic_version_and_chain(
    tmp_path: Path, kind: str,
) -> None:
    path = tmp_path / "store.sqlite"
    binding = scope()
    entity_ref = opaque_ref(kind.lower(), "case-1")
    with SQLiteProductStore(path) as first, SQLiteProductStore(path) as second:
        import_batch(first, binding, (record(binding),))
        one = first.append_revision(binding.run_ref, kind, entity_ref, {"status": "OPEN"},
                                    expected_version=0)
        assert one.version == 1 and one.previous_sha256 is None
        with pytest.raises(StoreConflict, match="VERSION_CONFLICT"):
            second.append_revision(binding.run_ref, kind, entity_ref, {"status": "STALE"},
                                   expected_version=0)
        two = second.append_revision(binding.run_ref, kind, entity_ref, {"status": "REVIEWED"},
                                     expected_version=1)
        assert two.previous_sha256 == one.revision_sha256
        assert first.get_revision(binding.run_ref, kind, entity_ref, 1) == one
        assert first.list_revisions(binding.run_ref, kind, entity_ref) == (one, two)
        with pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY"):
            first._db.execute("DELETE FROM revisions WHERE run_ref=?", (binding.run_ref,))
        with pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY"):
            first._db.execute("UPDATE records SET end_time=20 WHERE run_ref=?", (binding.run_ref,))
    with SQLiteProductStore(path) as reopened:
        assert reopened.get_revision(binding.run_ref, kind, entity_ref) == two
        assert reopened.get_revision(binding.run_ref, kind, entity_ref, 3) is None
        assert reopened.verify_run(binding.run_ref).records[0].payload_sha256 == record(
            binding
        ).payload_sha256


def test_revision_invalid_version_or_unknown_run_has_no_side_effect(tmp_path: Path) -> None:
    binding = scope()
    with SQLiteProductStore(tmp_path / "store.sqlite") as store:
        import_batch(store, binding, ())
        for value in (True, -1, 1.5):
            with pytest.raises(StoreConflict, match="EXPECTED_VERSION_INVALID"):
                store.append_revision(binding.run_ref, "CASE", opaque_ref("case", "test"), {},
                                      expected_version=value)
        with pytest.raises(StoreError, match="RUN_UNAVAILABLE"):
            store.append_revision(scope("unknown").run_ref, "CASE", opaque_ref("case", "test"),
                                  {}, expected_version=0)
        assert store._db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 0


def test_latest_revisions_are_scoped_bounded_and_restart_with_latest_only(tmp_path: Path) -> None:
    path = tmp_path / "store.sqlite"
    binding, other = scope(), scope("other")
    refs = sorted(opaque_ref("case", str(number)) for number in range(4))
    with SQLiteProductStore(path) as store:
        import_batch(store, binding, ())
        import_batch(store, other, ())
        assert store.list_latest_revisions(binding.run_ref, "CASE") == ()
        expected = []
        for ref in reversed(refs):
            store.append_revision(binding.run_ref, "CASE", ref, {"status": "OPEN"},
                                  expected_version=0)
            store.append_revision(binding.run_ref, "CASE", ref, {"status": "REVIEWED"},
                                  expected_version=1)
            expected.append(store.append_revision(binding.run_ref, "CASE", ref,
                                                  {"status": "CLOSED"}, expected_version=2))
        foreign = store.append_revision(other.run_ref, "CASE", refs[0], {"status": "FOREIGN"},
                                        expected_version=0)
        report = store.append_revision(binding.run_ref, "REPORT", refs[0], {"status": "REPORT"},
                                       expected_version=0)
    with SQLiteProductStore(path) as store:
        expected.sort(key=lambda revision: revision.entity_ref)
        assert store.list_latest_revisions(binding.run_ref, "CASE") == tuple(expected)
        assert store.list_latest_revisions(binding.run_ref, "CASE", limit=2) == tuple(expected[:2])
        assert store.list_latest_revisions(other.run_ref, "CASE") == (foreign,)
        assert store.list_latest_revisions(binding.run_ref, "REPORT") == (report,)
        assert store.list_latest_revisions(binding.run_ref, "REVIEW") == ()
        assert store.verify_run(binding.run_ref).records == ()
        with pytest.raises(StoreError, match="RUN_UNAVAILABLE"):
            store.list_latest_revisions(scope("absent").run_ref, "CASE")


@pytest.mark.parametrize("limit", [True, False, 0, -1, 501, 1.5, "2"])
def test_latest_revisions_reject_invalid_limits(tmp_path: Path, limit: object) -> None:
    binding = scope()
    with SQLiteProductStore(tmp_path / "store.sqlite") as store:
        import_batch(store, binding, ())
        with pytest.raises(StoreError, match="REVISION_LIMIT_INVALID"):
            store.list_latest_revisions(binding.run_ref, "CASE", limit=limit)
        with pytest.raises(StoreError, match="REVISION_KIND_INVALID"):
            store.list_latest_revisions(binding.run_ref, "CASE' OR 1=1 --")


@pytest.mark.parametrize("mutation", ["envelope", "previous", "row-version", "oldest"])
def test_latest_revisions_reject_ledger_corruption(tmp_path: Path, mutation: str) -> None:
    path = tmp_path / "store.sqlite"
    binding = scope()
    ref = opaque_ref("case", "tampered")
    with SQLiteProductStore(path) as store:
        import_batch(store, binding, ())
        store.append_revision(binding.run_ref, "CASE", ref, {"status": "OPEN"}, expected_version=0)
        store.append_revision(binding.run_ref, "CASE", ref, {"status": "REVIEWED"},
                              expected_version=1)
        store.append_revision(binding.run_ref, "CASE", ref, {"status": "CLOSED"},
                              expected_version=2)
    with sqlite3.connect(path) as corruptor:
        if mutation in ("envelope", "oldest"):
            corruptor.execute("DROP TRIGGER immutable_revisions_UPDATE")
            corruptor.execute("UPDATE revisions SET revision_sha256=? WHERE version=?",
                              ("f" * 64, 3 if mutation == "envelope" else 1))
        elif mutation == "previous":
            corruptor.execute("DROP TRIGGER immutable_revisions_DELETE")
            corruptor.execute("DELETE FROM revisions WHERE version=1")
        else:
            corruptor.execute("DROP TRIGGER immutable_revisions_UPDATE")
            corruptor.execute("UPDATE revisions SET version=4 WHERE version=3")
    with SQLiteProductStore(path) as store:
        with pytest.raises(StoreIntegrityError, match="REVISION_.*INTEGRITY_INVALID"):
            store.list_latest_revisions(binding.run_ref, "CASE")


@pytest.mark.parametrize("payload", [
    {"ground_truth": [{"position": [1, 2, 3]}]}, {"nested": {"api_key": "private"}},
    {"annotations": [{"actor_identity": "simulator-actor"}]}, {"recipe": {}},
    {"media": {"relative_path": "rgb/frame.png"}}, {"locator": "/Users/private/run.json"},
    {"explanation": "loaded /private/tmp/truth.json"}, {"uri": "file:///private/tmp/data"},
    {"location": "C:\\Users\\private\\file.json"},
])
def test_payload_boundary_rejects_gt_secrets_and_private_locators(payload: Payload) -> None:
    with pytest.raises(ValidationError, match="PAYLOAD_"):
        record(scope(), payload=payload)


def test_unchecked_payload_mutation_does_not_change_original_stored_record(tmp_path: Path) -> None:
    binding = scope()
    original = record(binding)
    with SQLiteProductStore(tmp_path / "store.sqlite") as store:
        import_batch(store, binding, (original,))
        read = store.get_record(binding.run_ref, "EVENT", original.record_ref)
        read.payload["complete"] = True
        again = store.get_record(binding.run_ref, "EVENT", original.record_ref)
        assert again.payload["complete"] is False
        with pytest.raises(ValidationError, match="PAYLOAD_HASH_MISMATCH"):
            RecordSetReceipt.create(binding, (read,))


def test_external_record_or_index_corruption_is_detected_before_paged_reads(tmp_path: Path) -> None:
    path = tmp_path / "store.sqlite"
    binding = scope()
    original = record(binding)
    with SQLiteProductStore(path) as store:
        import_batch(store, binding, (original,))
        store.verify_run(binding.run_ref)
        with sqlite3.connect(path) as corruptor:
            corruptor.execute("INSERT INTO record_regions VALUES (?,?,?,?,?,?)",
                              (binding.run_ref, "EVENT", original.record_ref, "invented", 0, 1))
        with pytest.raises(StoreIntegrityError, match="INDEX_INTEGRITY"):
            store.query_records(RecordQuery(run_ref=binding.run_ref, kind="EVENT",
                                            time_range=(0, 3)))


def test_external_hash_chain_corruption_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "store.sqlite"
    binding = scope()
    ref = opaque_ref("case", "case-1")
    with SQLiteProductStore(path) as store:
        import_batch(store, binding, ())
        store.append_revision(binding.run_ref, "CASE", ref, {"status": "OPEN"}, expected_version=0)
        two = store.append_revision(binding.run_ref, "CASE", ref, {"status": "OPEN"},
                                    expected_version=1)
        data = two.model_dump(mode="json", exclude={"revision_sha256"})
        data["previous_sha256"] = "f" * 64
        data["revision_sha256"] = content_hash(data)
        with sqlite3.connect(path) as corruptor:
            corruptor.execute("DROP TRIGGER immutable_revisions_UPDATE")
            corruptor.execute("UPDATE revisions SET revision_json=?,revision_sha256=? "
                              "WHERE version=2",
                              (json.dumps(data), data["revision_sha256"]))
        with pytest.raises(StoreIntegrityError, match="CHAIN_INTEGRITY"):
            store.get_revision(binding.run_ref, "CASE", ref)


def test_product_scope_and_time_filter_are_strict() -> None:
    with pytest.raises(ValidationError):
        ProductScope.model_validate(scope().model_dump() | {"observation_mode": "caller-stage"})
    for interval in ((False, 1), (float("nan"), 1), (0, float("inf")), (2, 1), (-1, 0)):
        with pytest.raises(ValidationError):
            RecordQuery(run_ref=scope().run_ref, kind="EVENT", time_range=interval)
    with pytest.raises(ValidationError):
        RecordQuery(run_ref=scope().run_ref, kind="EVENT", time_range=(0, 1), limit=True)


def test_camera_and_region_queries_start_at_their_scoped_index(tmp_path: Path) -> None:
    binding = scope()
    with SQLiteProductStore(tmp_path / "store.sqlite") as store:
        import_batch(store, binding, (record(binding),))
        for selector, index_name in (({"camera_id": "CAM_A"}, "cameras_interval"),
                                     ({"region_id": "west"}, "regions_interval")):
            query = RecordQuery.model_validate_json(json.dumps({
                "run_ref": binding.run_ref, "kind": "EVENT", "time_range": [0, 5], **selector,
            }))
            sql, parameters = store._query_statement(query, None)
            plan = str([tuple(row) for row in store._db.execute("EXPLAIN QUERY PLAN " + sql,
                                                                parameters)])
            assert index_name in plan
            assert "SCAN r" not in plan
            assert len(store.query_records(query).records) == 1


def test_unknown_database_schema_is_preserved_and_refused(tmp_path: Path) -> None:
    path = tmp_path / "unknown.sqlite"
    with sqlite3.connect(path) as historical:
        historical.execute("CREATE TABLE original_evidence(id INTEGER PRIMARY KEY, value TEXT)")
        historical.execute("INSERT INTO original_evidence(value) VALUES ('preserve')")
    before = path.read_bytes()
    with pytest.raises(StoreIntegrityError, match="SCHEMA_VERSION_INVALID"):
        SQLiteProductStore(path)
    assert path.read_bytes() == before


def test_external_payload_corruption_has_a_fixed_integrity_failure(tmp_path: Path) -> None:
    path = tmp_path / "store.sqlite"
    binding = scope()
    original = record(binding)
    with SQLiteProductStore(path) as store:
        import_batch(store, binding, (original,))
        altered = original.model_dump(mode="json")
        altered["payload"]["complete"] = True
        with sqlite3.connect(path) as corruptor:
            corruptor.execute("DROP TRIGGER immutable_records_UPDATE")
            corruptor.execute("UPDATE records SET record_json=?", (json.dumps(altered),))
        with pytest.raises(StoreIntegrityError, match="^CANONICAL_RECORD_INTEGRITY_INVALID$"):
            store.get_record(binding.run_ref, "EVENT", original.record_ref)


def test_revision_row_version_cannot_disagree_with_the_hashed_envelope(tmp_path: Path) -> None:
    path = tmp_path / "store.sqlite"
    binding = scope()
    ref = opaque_ref("case", "version-test")
    with SQLiteProductStore(path) as store:
        import_batch(store, binding, ())
        store.append_revision(binding.run_ref, "CASE", ref, {}, expected_version=0)
        with sqlite3.connect(path) as corruptor:
            corruptor.execute("DROP TRIGGER immutable_revisions_UPDATE")
            corruptor.execute("UPDATE revisions SET version=2")
        with pytest.raises(StoreIntegrityError, match="REVISION_INTEGRITY_INVALID"):
            store.get_revision(binding.run_ref, "CASE", ref)
