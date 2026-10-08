"""Local SQLite read model and append-only investigation evidence.

An explicit importer supplies verified frozen records. The repository never runs
perception, association or Graph search, and offers no caller-supplied SQL. Full
canonical JSON remains internal; a separate facade owns public allowlist DTOs.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, model_validator

from amidst.domain.common import Timestamp
from amidst.engineering.access import Mode
from amidst.engineering.registry import (
    RegistryModel,
    ResourceRef,
    ResourceScope,
    Sha256,
    content_hash,
    opaque_ref,
)

RecordKind = Literal["FRAME", "TRACK", "OBSERVATION", "EVENT", "HYPOTHESIS"]
EntityKind = Literal["CASE", "REPORT", "REVIEW"]
Payload = dict[str, JsonValue]
PositiveVersion = Annotated[int, Field(gt=0, strict=True)]
SCHEMA_VERSION = "product.sqlite.v1"
_FORBIDDEN_KEYS = frozenset({
    "gt", "ground_truth", "gt_actor_id", "actor_identity", "gt_position", "gt_path",
    "recipe", "recipe_reference", "reference_annotations", "reference_movement_annotations",
    "segmentation", "object_index", "depth_map", "source_archive", "simulation_export_path",
    "private_path", "private_filesystem_path", "relative_path", "secret", "password",
    "api_key", "access_token",
})


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _check_payload(value: object, depth: int = 0) -> None:
    if depth > 64:
        raise ValueError("PAYLOAD_DEPTH_INVALID")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or key.casefold().replace("-", "_") in _FORBIDDEN_KEYS:
                raise ValueError("PAYLOAD_BOUNDARY_DENIED")
            _check_payload(child, depth + 1)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _check_payload(child, depth + 1)
    elif isinstance(value, str) and (
        value.startswith(("/", "\\\\", "file://"))
        or re.search(r"[A-Za-z]:[\\/]", value)
        or any(part in value for part in ("/Users/", "/home/", "/private/", "/tmp/", "file://"))
    ):
        raise ValueError("PAYLOAD_LOCATOR_DENIED")


class ProductScope(RegistryModel):
    resource_scope: ResourceScope
    observation_mode: Mode
    dataset_sha256: Sha256
    config_sha256: Sha256
    producer_sha256: Sha256
    registry_sha256: Sha256
    media_sha256: Sha256
    inference_sha256: Sha256
    freeze_sha256: Sha256

    @model_validator(mode="after")
    def scope_boundary(self) -> Self:
        _check_payload(self.resource_scope.model_dump(mode="json"))
        return self

    @property
    def run_ref(self) -> str:
        return opaque_ref("run", content_hash(self.model_dump(mode="json")))


class CanonicalRecord(RegistryModel):
    run_ref: ResourceRef
    kind: RecordKind
    record_ref: ResourceRef
    camera_ids: tuple[str, ...] = ()
    time_range: tuple[Timestamp, Timestamp]
    region_ids: tuple[str, ...] = ()
    payload: Payload
    payload_sha256: Sha256

    @model_validator(mode="after")
    def immutable_binding(self) -> Self:
        _check_payload(self.payload)
        if self.payload_sha256 != content_hash(self.payload):
            raise ValueError("PAYLOAD_HASH_MISMATCH")
        if self.time_range[1] < self.time_range[0]:
            raise ValueError("TIME_RANGE_INVALID")
        if any(not item for item in (*self.camera_ids, *self.region_ids)) or (
            len(self.camera_ids) != len(set(self.camera_ids))
            or len(self.region_ids) != len(set(self.region_ids))
        ):
            raise ValueError("RECORD_INDEX_BINDING_INVALID")
        return self

    @classmethod
    def create(
        cls, *, run_ref: str, kind: RecordKind, record_ref: str,
        time_range: tuple[float, float], payload: Payload,
        camera_ids: tuple[str, ...] = (), region_ids: tuple[str, ...] = (),
    ) -> CanonicalRecord:
        return cls(run_ref=run_ref, kind=kind, record_ref=record_ref, time_range=time_range,
                   payload=payload, payload_sha256=content_hash(payload),
                   camera_ids=camera_ids, region_ids=region_ids)

    @property
    def envelope_sha256(self) -> str:
        return content_hash(self.model_dump(mode="json"))


class RecordDigest(RegistryModel):
    kind: RecordKind
    record_ref: ResourceRef
    payload_sha256: Sha256
    envelope_sha256: Sha256


class RecordSetReceipt(RegistryModel):
    schema_version: Literal["product.record-set.v1"] = "product.record-set.v1"
    run_ref: ResourceRef
    scope_sha256: Sha256
    records: tuple[RecordDigest, ...]
    receipt_sha256: Sha256

    @classmethod
    def create(cls, scope: ProductScope, records: tuple[CanonicalRecord, ...]) -> RecordSetReceipt:
        scope = ProductScope.model_validate_json(scope.model_dump_json())
        checked = tuple(CanonicalRecord.model_validate_json(row.model_dump_json())
                        for row in records)
        keys = [(row.kind, row.record_ref) for row in checked]
        if len(set(keys)) != len(keys) or any(row.run_ref != scope.run_ref for row in checked):
            raise StoreConflict("RECORD_SCOPE_OR_ID_CONFLICT")
        items = tuple(RecordDigest(kind=row.kind, record_ref=row.record_ref,
                                  payload_sha256=row.payload_sha256,
                                  envelope_sha256=row.envelope_sha256)
                      for row in sorted(checked, key=lambda row: (row.kind, row.record_ref)))
        scope_hash = content_hash(scope.model_dump(mode="json"))
        values = {"schema_version": "product.record-set.v1", "run_ref": scope.run_ref,
                  "scope_sha256": scope_hash,
                  "records": [item.model_dump(mode="json") for item in items]}
        return cls(run_ref=scope.run_ref, scope_sha256=scope_hash, records=items,
                   receipt_sha256=content_hash(values))


class ImportResult(RegistryModel):
    run_ref: ResourceRef
    receipt_sha256: Sha256
    record_count: int = Field(ge=0, strict=True)
    inserted: bool


class RecordQuery(RegistryModel):
    run_ref: ResourceRef
    kind: RecordKind
    time_range: tuple[Timestamp, Timestamp]
    camera_id: str | None = Field(default=None, min_length=1)
    region_id: str | None = Field(default=None, min_length=1)
    # Server-derived allowlist, applied before keyset paging. None selects all;
    # an empty tuple selects none. Callers never supply a SQL predicate.
    record_refs: tuple[ResourceRef, ...] | None = Field(default=None, max_length=4096)
    limit: int = Field(default=50, gt=0, le=500, strict=True)
    cursor: str | None = Field(default=None, min_length=1, max_length=4096)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.time_range[1] < self.time_range[0]:
            raise ValueError("TIME_RANGE_INVALID")
        if self.record_refs is not None and len(set(self.record_refs)) != len(self.record_refs):
            raise ValueError("RECORD_FILTER_DUPLICATE")
        return self

    @property
    def filter_sha256(self) -> str:
        return content_hash(self.model_dump(mode="json", exclude={"cursor"}))


class RecordPage(RegistryModel):
    run_ref: ResourceRef
    records: tuple[CanonicalRecord, ...]
    next_cursor: str | None
    query_complete: bool
    record_set_receipt_sha256: Sha256


class Revision(RegistryModel):
    run_ref: ResourceRef
    kind: EntityKind
    entity_ref: ResourceRef
    version: PositiveVersion
    previous_sha256: Sha256 | None
    payload: Payload
    payload_sha256: Sha256
    revision_sha256: Sha256

    @model_validator(mode="after")
    def chain_binding(self) -> Self:
        _check_payload(self.payload)
        if self.payload_sha256 != content_hash(self.payload) or (
            (self.version == 1) != (self.previous_sha256 is None)
        ):
            raise ValueError("REVISION_CHAIN_INVALID")
        values = self.model_dump(mode="json", exclude={"revision_sha256"})
        if self.revision_sha256 != content_hash(values):
            raise ValueError("REVISION_HASH_MISMATCH")
        return self


class StoreError(ValueError):
    """Fixed codes only; SQL, filesystem locators and payloads are never included."""


class StoreConflict(StoreError):
    pass


class StoreIntegrityError(StoreError):
    pass


class _Cursor(RegistryModel):
    version: Literal["p1"] = "p1"
    filter_sha256: Sha256
    start_time: Timestamp
    end_time: Timestamp
    record_ref: ResourceRef


class SQLiteProductStore:
    def __init__(self, path: Path):
        try:
            self._initialize(path)
        except StoreError:
            if hasattr(self, "_db"):
                self._db.close()
            raise
        except (sqlite3.Error, OSError):
            if hasattr(self, "_db"):
                self._db.close()
            raise StoreError("STORE_UNAVAILABLE") from None

    def _initialize(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        tables = {row[0] for row in self._db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )}
        if tables:
            if "metadata" not in tables:
                raise StoreIntegrityError("SCHEMA_VERSION_INVALID")
            existing_version = self._db.execute("SELECT value FROM metadata WHERE key=?",
                                                ("schema_version",)).fetchone()
            if existing_version is None or existing_version[0] != SCHEMA_VERSION:
                raise StoreIntegrityError("SCHEMA_VERSION_INVALID")
        self._db.execute("PRAGMA journal_mode = WAL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs(
                run_ref TEXT PRIMARY KEY, scope_json TEXT NOT NULL, receipt_json TEXT NOT NULL,
                receipt_sha256 TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS records(
                run_ref TEXT NOT NULL REFERENCES runs(run_ref), kind TEXT NOT NULL,
                record_ref TEXT NOT NULL, start_time REAL NOT NULL, end_time REAL NOT NULL,
                record_json TEXT NOT NULL, envelope_sha256 TEXT NOT NULL,
                PRIMARY KEY(run_ref, kind, record_ref)
            );
            CREATE INDEX IF NOT EXISTS records_interval ON records(
                run_ref, kind, start_time, end_time, record_ref
            );
            CREATE TABLE IF NOT EXISTS record_cameras(
                run_ref TEXT NOT NULL, kind TEXT NOT NULL, record_ref TEXT NOT NULL,
                camera_id TEXT NOT NULL, start_time REAL NOT NULL, end_time REAL NOT NULL,
                PRIMARY KEY(run_ref, kind, record_ref, camera_id),
                FOREIGN KEY(run_ref,kind,record_ref) REFERENCES records(run_ref,kind,record_ref)
            );
            CREATE INDEX IF NOT EXISTS cameras_interval ON record_cameras(
                run_ref, camera_id, kind, start_time, end_time, record_ref
            );
            CREATE TABLE IF NOT EXISTS record_regions(
                run_ref TEXT NOT NULL, kind TEXT NOT NULL, record_ref TEXT NOT NULL,
                region_id TEXT NOT NULL, start_time REAL NOT NULL, end_time REAL NOT NULL,
                PRIMARY KEY(run_ref, kind, record_ref, region_id),
                FOREIGN KEY(run_ref,kind,record_ref) REFERENCES records(run_ref,kind,record_ref)
            );
            CREATE INDEX IF NOT EXISTS regions_interval ON record_regions(
                run_ref, region_id, kind, start_time, end_time, record_ref
            );
            CREATE TABLE IF NOT EXISTS revisions(
                run_ref TEXT NOT NULL REFERENCES runs(run_ref), kind TEXT NOT NULL,
                entity_ref TEXT NOT NULL, version INTEGER NOT NULL,
                revision_json TEXT NOT NULL, revision_sha256 TEXT NOT NULL,
                PRIMARY KEY(run_ref,kind,entity_ref,version)
            );
        """)
        for table in ("runs", "records", "record_cameras", "record_regions", "revisions"):
            for action in ("UPDATE", "DELETE"):
                self._db.execute(f"""CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action}
                    BEFORE {action} ON {table}
                    BEGIN SELECT RAISE(ABORT, 'APPEND_ONLY_RECORD'); END""")
        with self._transaction():
            self._db.execute("INSERT OR IGNORE INTO metadata VALUES (?,?)",
                             ("schema_version", SCHEMA_VERSION))
            self._db.execute("INSERT OR IGNORE INTO metadata VALUES (?,?)",
                             ("cursor_key", secrets.token_hex(32)))
            version = self._db.execute("SELECT value FROM metadata WHERE key=?",
                                       ("schema_version",)).fetchone()
            if version is None or version[0] != SCHEMA_VERSION:
                raise StoreIntegrityError("SCHEMA_VERSION_INVALID")
        row = self._db.execute("SELECT value FROM metadata WHERE key=?", ("cursor_key",)).fetchone()
        if row is None or not re.fullmatch(r"[0-9a-f]{64}", row[0]):
            raise StoreIntegrityError("CURSOR_KEY_INVALID")
        self._cursor_key = bytes.fromhex(row[0])
        self._verified: dict[str, int] = {}

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> SQLiteProductStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        try:
            self._db.execute("BEGIN IMMEDIATE")
        except sqlite3.Error:
            raise StoreError("STORAGE_TRANSACTION_FAILED") from None
        try:
            yield
            self._db.execute("COMMIT")
        except sqlite3.Error:
            self._db.execute("ROLLBACK")
            raise StoreError("STORAGE_TRANSACTION_FAILED") from None
        except BaseException:
            self._db.execute("ROLLBACK")
            raise

    def import_records(
        self, scope: ProductScope, records: tuple[CanonicalRecord, ...], receipt: RecordSetReceipt,
    ) -> ImportResult:
        scope = ProductScope.model_validate_json(scope.model_dump_json())
        records = tuple(CanonicalRecord.model_validate_json(row.model_dump_json())
                        for row in records)
        expected = RecordSetReceipt.create(scope, records)
        if receipt != expected:
            raise StoreIntegrityError("RECORD_SET_RECEIPT_INVALID")
        with self._transaction():
            existing = self._db.execute("SELECT receipt_sha256 FROM runs WHERE run_ref=?",
                                        (scope.run_ref,)).fetchone()
            if existing is not None:
                if existing[0] != expected.receipt_sha256:
                    raise StoreConflict("IMMUTABLE_RUN_CONFLICT")
                self.verify_run(scope.run_ref)
                return ImportResult(run_ref=scope.run_ref, receipt_sha256=expected.receipt_sha256,
                                    record_count=len(records), inserted=False)
            self._db.execute("INSERT INTO runs VALUES (?,?,?,?)", (
                scope.run_ref, scope.model_dump_json(), expected.model_dump_json(),
                expected.receipt_sha256,
            ))
            for record in records:
                start, end = record.time_range
                self._db.execute("INSERT INTO records VALUES (?,?,?,?,?,?,?)", (
                    scope.run_ref, record.kind, record.record_ref, start, end,
                    record.model_dump_json(), record.envelope_sha256,
                ))
                self._db.executemany("INSERT INTO record_cameras VALUES (?,?,?,?,?,?)", (
                    (scope.run_ref, record.kind, record.record_ref, camera, start, end)
                    for camera in record.camera_ids
                ))
                self._db.executemany("INSERT INTO record_regions VALUES (?,?,?,?,?,?)", (
                    (scope.run_ref, record.kind, record.record_ref, region, start, end)
                    for region in record.region_ids
                ))
        return ImportResult(run_ref=scope.run_ref, receipt_sha256=expected.receipt_sha256,
                            record_count=len(records), inserted=True)

    def list_runs(self) -> tuple[ProductScope, ...]:
        return tuple(ProductScope.model_validate_json(row[0]) for row in
                     self._db.execute("SELECT scope_json FROM runs ORDER BY run_ref"))

    def get_scope(self, run_ref: str) -> ProductScope:
        row = self._db.execute("SELECT scope_json FROM runs WHERE run_ref=?", (run_ref,)).fetchone()
        if row is None:
            raise StoreError("RUN_UNAVAILABLE")
        scope = ProductScope.model_validate_json(row[0])
        if scope.run_ref != run_ref:
            raise StoreIntegrityError("RUN_SCOPE_INTEGRITY_INVALID")
        return scope

    @staticmethod
    def _decode_record(row: sqlite3.Row) -> CanonicalRecord:
        try:
            record = CanonicalRecord.model_validate_json(row["record_json"])
        except ValueError:
            raise StoreIntegrityError("CANONICAL_RECORD_INTEGRITY_INVALID") from None
        if record.envelope_sha256 != row["envelope_sha256"] or (
            record.run_ref, record.kind, record.record_ref, *record.time_range
        ) != (row["run_ref"], row["kind"], row["record_ref"], row["start_time"], row["end_time"]):
            raise StoreIntegrityError("CANONICAL_RECORD_INTEGRITY_INVALID")
        return record

    def get_record(self, run_ref: str, kind: RecordKind, record_ref: str) -> CanonicalRecord:
        self.get_scope(run_ref)
        self._ensure_verified(run_ref)
        row = self._db.execute("SELECT * FROM records WHERE run_ref=? AND kind=? AND record_ref=?",
                               (run_ref, kind, record_ref)).fetchone()
        if row is None:
            raise StoreError("RECORD_UNAVAILABLE")
        return self._decode_record(row)

    def verify_run(self, run_ref: str) -> RecordSetReceipt:
        scope = self.get_scope(run_ref)
        row = self._db.execute("SELECT receipt_json,receipt_sha256 FROM runs WHERE run_ref=?",
                               (run_ref,)).fetchone()
        assert row is not None
        records = tuple(self._decode_record(item) for item in self._db.execute(
            "SELECT * FROM records WHERE run_ref=? ORDER BY kind,record_ref", (run_ref,)
        ))
        expected = RecordSetReceipt.create(scope, records)
        if expected != RecordSetReceipt.model_validate_json(row[0]) or (
            expected.receipt_sha256 != row[1]
        ):
            raise StoreIntegrityError("RECORD_SET_INTEGRITY_INVALID")
        for record in records:
            for table, column, identities in (
                ("record_cameras", "camera_id", record.camera_ids),
                ("record_regions", "region_id", record.region_ids),
            ):
                index_rows = tuple(self._db.execute(
                    f"SELECT {column},start_time,end_time FROM {table} "
                    "WHERE run_ref=? AND kind=? AND record_ref=?",  # static names only
                    (run_ref, record.kind, record.record_ref),
                ))
                expected_rows = {(value, *record.time_range) for value in identities}
                if {tuple(item) for item in index_rows} != expected_rows:
                    raise StoreIntegrityError("RECORD_INDEX_INTEGRITY_INVALID")
        self._verified[run_ref] = self._db.execute("PRAGMA data_version").fetchone()[0]
        return expected

    def _ensure_verified(self, run_ref: str) -> None:
        version = self._db.execute("PRAGMA data_version").fetchone()[0]
        if self._verified.get(run_ref) != version:
            self.verify_run(run_ref)

    def _encode_cursor(self, query: RecordQuery, record: CanonicalRecord) -> str:
        cursor = _Cursor(filter_sha256=query.filter_sha256, start_time=record.time_range[0],
                         end_time=record.time_range[1], record_ref=record.record_ref)
        payload = base64.urlsafe_b64encode(cursor.model_dump_json().encode()).decode().rstrip("=")
        signature = hmac.new(self._cursor_key, payload.encode(), hashlib.sha256).hexdigest()
        return f"p1.{payload}.{signature}"

    def _decode_cursor(self, query: RecordQuery) -> _Cursor | None:
        if query.cursor is None:
            return None
        try:
            version, payload, signature = query.cursor.split(".")
            expected = hmac.new(self._cursor_key, payload.encode(), hashlib.sha256).hexdigest()
            if version != "p1" or not hmac.compare_digest(expected, signature):
                raise ValueError("signature")
            data = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
            cursor = _Cursor.model_validate_json(data)
            if cursor.filter_sha256 != query.filter_sha256:
                raise ValueError("filter binding")
            return cursor
        except (ValueError, TypeError):
            raise StoreError("CURSOR_INVALID") from None

    def query_records(self, query: RecordQuery) -> RecordPage:
        query = RecordQuery.model_validate_json(query.model_dump_json())
        self.get_scope(query.run_ref)
        self._ensure_verified(query.run_ref)
        cursor = self._decode_cursor(query)
        sql, parameters = self._query_statement(query, cursor)
        rows = tuple(self._db.execute(sql, parameters))
        has_more = len(rows) > query.limit
        records = tuple(self._decode_record(row) for row in rows[:query.limit])
        receipt = self._db.execute("SELECT receipt_sha256 FROM runs WHERE run_ref=?",
                                   (query.run_ref,)).fetchone()
        assert receipt is not None
        return RecordPage(run_ref=query.run_ref, records=records, query_complete=not has_more,
                          next_cursor=self._encode_cursor(query, records[-1]) if has_more else None,
                          record_set_receipt_sha256=receipt[0])

    @staticmethod
    def _query_statement(
        query: RecordQuery, cursor: _Cursor | None,
    ) -> tuple[str, list[str | float | int]]:
        parameters: list[str | float | int]
        if query.camera_id is not None or query.region_id is not None:
            table, column, selected, index = (
                ("record_cameras", "camera_id", query.camera_id, "cameras_interval")
                if query.camera_id is not None else
                ("record_regions", "region_id", query.region_id, "regions_interval")
            )
            assert selected is not None
            # CROSS JOIN preserves the selected indexed bucket as the outer input.
            source = (f"{table} s INDEXED BY {index} CROSS JOIN records r ON "
                      "r.run_ref=s.run_ref AND r.kind=s.kind AND r.record_ref=s.record_ref")
            conditions = ["s.run_ref=?", f"s.{column}=?", "s.kind=?",
                          "s.start_time<=?", "s.end_time>=?"]
            parameters = [query.run_ref, selected, query.kind,
                          query.time_range[1], query.time_range[0]]
        else:
            source = "records r INDEXED BY records_interval"
            conditions = ["r.run_ref=?", "r.kind=?", "r.start_time<=?", "r.end_time>=?"]
            parameters = [query.run_ref, query.kind, query.time_range[1], query.time_range[0]]
        if query.camera_id is not None and query.region_id is not None:
            conditions.append("EXISTS (SELECT 1 FROM record_regions x WHERE "
                              "x.run_ref=r.run_ref AND x.kind=r.kind "
                              "AND x.record_ref=r.record_ref AND x.region_id=?)")
            parameters.append(query.region_id)
        if query.record_refs is not None:
            if query.record_refs:
                placeholders = ",".join("?" for _ in query.record_refs)
                conditions.append(f"r.record_ref IN ({placeholders})")
                parameters.extend(query.record_refs)
            else:
                conditions.append("0")
        if cursor is not None:
            conditions.append("(r.start_time,r.end_time,r.record_ref)>(?,?,?)")
            parameters.extend((cursor.start_time, cursor.end_time, cursor.record_ref))
        parameters.append(query.limit + 1)
        return ("SELECT r.* FROM " + source + " WHERE " + " AND ".join(conditions) +
                " ORDER BY r.start_time,r.end_time,r.record_ref LIMIT ?", parameters)

    def append_revision(
        self, run_ref: str, kind: EntityKind, entity_ref: str, payload: Payload, *,
        expected_version: int,
    ) -> Revision:
        self.get_scope(run_ref)
        self._ensure_verified(run_ref)
        if type(expected_version) is not int or expected_version < 0:
            raise StoreConflict("EXPECTED_VERSION_INVALID")
        _check_payload(payload)
        with self._transaction():
            previous = self.get_revision(run_ref, kind, entity_ref)
            current_version = 0 if previous is None else previous.version
            if expected_version != current_version:
                raise StoreConflict("REVISION_VERSION_CONFLICT")
            previous_hash = None if previous is None else previous.revision_sha256
            values = {"run_ref": run_ref, "kind": kind, "entity_ref": entity_ref,
                      "version": current_version + 1, "previous_sha256": previous_hash,
                      "payload": payload, "payload_sha256": content_hash(payload)}
            revision = Revision.model_validate_json(_json(values | {
                "revision_sha256": content_hash(values)
            }))
            self._db.execute("INSERT INTO revisions VALUES (?,?,?,?,?,?)", (
                run_ref, kind, entity_ref, revision.version, revision.model_dump_json(),
                revision.revision_sha256,
            ))
        return revision

    def get_revision(
        self, run_ref: str, kind: EntityKind, entity_ref: str, version: int | None = None,
    ) -> Revision | None:
        self.get_scope(run_ref)
        if version is not None and (type(version) is not int or version < 1):
            raise StoreError("REVISION_VERSION_INVALID")
        condition = "" if version is None else " AND version=?"
        values: tuple[str | int, ...] = (run_ref, kind, entity_ref)
        if version is not None:
            values += (version,)
        row = self._db.execute(
            "SELECT revision_json,revision_sha256,version FROM revisions "
            "WHERE run_ref=? AND kind=? AND entity_ref=?" + condition +
            " ORDER BY version DESC LIMIT 1", values,
        ).fetchone()
        if row is None:
            return None
        try:
            revision = Revision.model_validate_json(row[0])
        except ValueError:
            raise StoreIntegrityError("REVISION_INTEGRITY_INVALID") from None
        if revision.revision_sha256 != row[1] or (
            revision.run_ref, revision.kind, revision.entity_ref
        ) != (run_ref, kind, entity_ref) or revision.version != row[2] or (
            version is not None and revision.version != version
        ):
            raise StoreIntegrityError("REVISION_INTEGRITY_INVALID")
        expected_version = revision.version - 1
        expected_hash = revision.previous_sha256
        previous_rows = self._db.execute(
            "SELECT revision_json,revision_sha256,version FROM revisions "
            "WHERE run_ref=? AND kind=? AND entity_ref=? AND version<? ORDER BY version DESC",
            (run_ref, kind, entity_ref, revision.version),
        )
        for previous_row in previous_rows:
            try:
                previous = Revision.model_validate_json(previous_row[0])
            except ValueError:
                raise StoreIntegrityError("REVISION_CHAIN_INTEGRITY_INVALID") from None
            if previous.revision_sha256 != previous_row[1] or (
                previous_row[1] != expected_hash or previous_row[2] != expected_version
            ):
                raise StoreIntegrityError("REVISION_CHAIN_INTEGRITY_INVALID")
            if (previous.run_ref, previous.kind, previous.entity_ref, previous.version) != (
                run_ref, kind, entity_ref, expected_version
            ):
                raise StoreIntegrityError("REVISION_CHAIN_INTEGRITY_INVALID")
            expected_version -= 1
            expected_hash = previous.previous_sha256
        if expected_version != 0 or expected_hash is not None:
            raise StoreIntegrityError("REVISION_CHAIN_INTEGRITY_INVALID")
        return revision

    def list_revisions(
        self, run_ref: str, kind: EntityKind, entity_ref: str,
    ) -> tuple[Revision, ...]:
        self.get_scope(run_ref)
        rows = self._db.execute("SELECT version FROM revisions WHERE run_ref=? AND kind=? "
                                "AND entity_ref=? ORDER BY version", (run_ref, kind, entity_ref))
        result = []
        previous_hash = None
        for number, row in enumerate(rows, start=1):
            revision = self.get_revision(run_ref, kind, entity_ref, row[0])
            if revision is None or revision.version != number or (
                revision.previous_sha256 != previous_hash
            ):
                raise StoreIntegrityError("REVISION_CHAIN_INTEGRITY_INVALID")
            result.append(revision)
            previous_hash = revision.revision_sha256
        return tuple(result)

    def list_latest_revisions(
        self, run_ref: str, kind: EntityKind, *, limit: int = 101,
    ) -> tuple[Revision, ...]:
        """Read one verified revision per scoped entity, in stable ref order."""
        self.get_scope(run_ref)
        if kind not in ("CASE", "REPORT", "REVIEW"):
            raise StoreError("REVISION_KIND_INVALID")
        if type(limit) is not int or not 1 <= limit <= 500:
            raise StoreError("REVISION_LIMIT_INVALID")
        rows = tuple(self._db.execute(
            "SELECT entity_ref,MAX(version) FROM revisions WHERE run_ref=? AND kind=? "
            "GROUP BY entity_ref ORDER BY entity_ref LIMIT ?", (run_ref, kind, limit),
        ))
        result = []
        for row in rows:
            revision = self.get_revision(run_ref, kind, row[0], row[1])
            if revision is None:
                raise StoreIntegrityError("REVISION_INTEGRITY_INVALID")
            result.append(revision)
        return tuple(result)
