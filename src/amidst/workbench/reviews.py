"""Append-only human review overlays, isolated from source and frozen inference.

The caller supplies already authorized scene snapshots. This module reads no
scene files, GT, recipes or algorithm outputs. Publishing an overlay records a
synthetic-scene review and a rerun requirement, never formal spatial authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

Payload = dict[str, Any]
_KINDS = frozenset({"REGION", "PORTAL", "WALKABLE", "CAMERA"})
_SEMANTICS = {
    "REGION": {"UNKNOWN", "ROOM", "CORRIDOR", "HALL", "OUTDOOR", "REGION"},
    "PORTAL": {"UNKNOWN", "DOOR", "PASSAGE", "ENTRANCE", "EXIT", "PORTAL"},
    "WALKABLE": {"UNKNOWN", "WALKABLE", "FLOOR", "STAIR", "NON_WALKABLE"},
    "CAMERA": {"UNKNOWN", "CAMERA", "FIXED_CAMERA", "SIMULATED_CAMERA"},
}
_PROPERTY_KEYS = {
    "REGION": {"floor", "level", "walkable", "description", "region_id", "floor_id"},
    "PORTAL": {"width", "height", "traversable", "description", "direction",
               "inside_region_id", "outside_region_id", "enter_normal_xy"},
    "WALKABLE": {"floor", "level", "walkable", "description", "slope", "floor_id", "plane_z_m"},
    "CAMERA": {
        "fx", "fy", "cx", "cy", "width", "height", "image_width", "image_height",
        "focal_length", "sensor_width", "sensor_height", "description",
        "calibration_kind", "position", "camera_to_world", "convention", "ground_to_pixel",
        "plane_z_m", "physical_pose_status",
    },
}
_POSITIVE_CAMERA = frozenset({
    "fx", "fy", "width", "height", "image_width", "image_height", "focal_length",
    "sensor_width", "sensor_height",
})
_OBJECT_KEYS = frozenset({
    "object_id", "kind", "label", "semantic", "geometry", "properties", "editable_fields",
    "authority",
})
_EDITABLE = frozenset({"label", "semantic", "geometry", "properties"})
_TABLES = ("scenes", "drafts", "validations", "versions", "result_reviews", "management_notes")


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _clone(value: Payload) -> Payload:
    result: Payload = json.loads(_json(value))
    return result


def _text(value: object, field: str, limit: int = 2048) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field.upper()}_INVALID")
    return value.strip()


def _version(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("VERSION_INVALID")
    return value


def _number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _cross(a: list[float], b: list[float]) -> list[float]:
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def _geometry_errors(kind: str, geometry: object, unknown_camera: bool = False) -> list[str]:
    if not isinstance(geometry, dict) or set(geometry) != {"type", "points"}:
        return ["GEOMETRY_SCHEMA_INVALID"]
    expected = {"REGION": "polygon", "WALKABLE": "polygon", "PORTAL": "line", "CAMERA": "point"}
    if geometry["type"] != expected[kind]:
        return ["GEOMETRY_TYPE_INVALID"]
    raw = geometry["points"]
    if not isinstance(raw, list) or len(raw) > 2048 or any(
        not isinstance(point, list) or len(point) != 3 or not all(_number(x) for x in point)
        for point in raw
    ):
        return ["GEOMETRY_COORDINATES_INVALID"]
    points: list[list[float]] = [[float(x) for x in point] for point in raw]
    if kind == "CAMERA":
        if unknown_camera:
            return [] if not points else ["UNKNOWN_CAMERA_POSE_REQUIRED"]
        return [] if len(points) == 1 else ["CAMERA_POSITION_INVALID"]
    if kind == "PORTAL":
        if len(points) != 2:
            return ["PORTAL_ENDPOINTS_INVALID"]
        distance = math.dist(points[0], points[1])
        if not math.isfinite(distance) or distance <= 1e-8:
            return ["PORTAL_ENDPOINTS_INVALID"]
        return []
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if len(points) < 3 or len({tuple(point) for point in points}) != len(points):
        return ["POLYGON_VERTICES_INVALID"]
    normal = [0.0, 0.0, 0.0]
    origin = points[0]
    for a, b in zip(points, points[1:] + points[:1], strict=True):
        cross = _cross([x - y for x, y in zip(a, origin, strict=True)],
                       [x - y for x, y in zip(b, origin, strict=True)])
        normal = [x + y for x, y in zip(normal, cross, strict=True)]
    magnitude = math.sqrt(sum(x * x for x in normal))
    if not math.isfinite(magnitude) or magnitude <= 1e-8:
        return ["POLYGON_DEGENERATE"]
    normal = [x / magnitude for x in normal]
    scale = max(1.0, *(math.dist(origin, point) for point in points))
    if any(abs(sum((point[i] - origin[i]) * normal[i] for i in range(3))) > 1e-6 * scale
           for point in points):
        return ["POLYGON_NOT_PLANAR"]
    # Project onto the dominant plane, retaining vertical walkable/portal surfaces.
    axis = max(range(3), key=lambda i: abs(normal[i]))
    projected = [[v for i, v in enumerate(point) if i != axis] for point in points]

    def orientation(a: list[float], b: list[float], c: list[float]) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_segment(a: list[float], b: list[float], c: list[float]) -> bool:
        return (min(a[0], b[0]) - 1e-9 <= c[0] <= max(a[0], b[0]) + 1e-9
                and min(a[1], b[1]) - 1e-9 <= c[1] <= max(a[1], b[1]) + 1e-9)

    for i, a in enumerate(projected):
        b = projected[(i + 1) % len(projected)]
        if math.dist(a, b) <= 1e-8:
            return ["POLYGON_EDGE_DEGENERATE"]
        for j in range(i + 1, len(projected)):
            if j == i + 1 or (i == 0 and j == len(projected) - 1):
                continue
            c, d = projected[j], projected[(j + 1) % len(projected)]
            o1, o2 = orientation(a, b, c), orientation(a, b, d)
            o3, o4 = orientation(c, d, a), orientation(c, d, b)
            crosses = o1 * o2 < 0 and o3 * o4 < 0
            touches = any(abs(o) <= 1e-9 and on_segment(p, q, r) for o, p, q, r in (
                (o1, a, b, c), (o2, a, b, d), (o3, c, d, a), (o4, c, d, b),
            ))
            if crosses or touches:
                return ["POLYGON_SELF_INTERSECTION"]
    return []


def _vector(value: object, size: int) -> bool:
    return isinstance(value, list) and len(value) == size and all(_number(x) for x in value)


def _matrix(value: object, rows: int, columns: int) -> bool:
    return (isinstance(value, list) and len(value) == rows
            and all(_vector(row, columns) for row in value))


def _properties_errors(kind: str, properties: Payload, geometry: object) -> list[str]:
    errors: list[str] = []
    camera_text = {"description", "calibration_kind", "convention", "physical_pose_status"}
    for key, value in properties.items():
        if key == "floor_id" and value is None:
            continue
        if key == "position" and kind == "CAMERA":
            if value is not None and not _vector(value, 3):
                errors.append("CAMERA_POSITION_INVALID")
        elif key in {"camera_to_world", "ground_to_pixel"} and kind == "CAMERA":
            shape = (4, 4) if key == "camera_to_world" else (2, 3)
            if not _matrix(value, *shape):
                errors.append("CAMERA_MATRIX_INVALID")
        elif key == "enter_normal_xy" and kind == "PORTAL":
            if not _vector(value, 2) or math.hypot(*value) <= 1e-8:
                errors.append("PORTAL_NORMAL_INVALID")
        elif isinstance(value, (list, dict)) or value is None or (
            not isinstance(value, (str, bool)) and not _number(value)
        ):
            errors.append("PROPERTY_VALUE_INVALID")
        elif kind == "CAMERA" and key not in camera_text:
            if not _number(value) or (key in _POSITIVE_CAMERA and value <= 0):
                errors.append("CAMERA_CALIBRATION_INVALID")
            elif key in {"width", "height", "image_width", "image_height"} and (
                not isinstance(value, int)
            ):
                errors.append("CAMERA_DIMENSION_INVALID")
        elif key in {"width", "height"} and (not _number(value) or value <= 0):
            errors.append("DIMENSION_INVALID")
        elif key in {"walkable", "traversable"} and not isinstance(value, bool):
            errors.append("BOOLEAN_PROPERTY_INVALID")
        elif key in {"plane_z_m", "slope"} and not _number(value):
            errors.append("NUMERIC_PROPERTY_INVALID")
        elif key in {"region_id", "floor_id", "inside_region_id", "outside_region_id"}:
            if not isinstance(value, str) or not value.strip():
                errors.append("REGION_REFERENCE_INVALID")
    if kind != "CAMERA" or errors:
        return errors
    calibration = properties.get("calibration_kind")
    if calibration == "PINHOLE":
        required = {"position", "camera_to_world", "fx", "fy", "cx", "cy", "width", "height",
                    "convention"}
        if not required.issubset(properties) or properties["position"] is None:
            return ["CAMERA_CALIBRATION_INCOMPLETE"]
        if properties["convention"] != "BLENDER_NEG_Z_UP_Y":
            errors.append("CAMERA_CONVENTION_UNSUPPORTED")
        matrix = properties["camera_to_world"]
        position = properties["position"]
        if matrix[3] != [0, 0, 0, 1] or any(
            abs(matrix[i][3] - position[i]) > 1e-8 for i in range(3)
        ):
            errors.append("CAMERA_POSE_INCONSISTENT")
        for i in range(3):
            for j in range(3):
                dot = sum(matrix[k][i] * matrix[k][j] for k in range(3))
                if not math.isfinite(dot) or abs(dot - (1.0 if i == j else 0.0)) > 1e-5:
                    errors.append("CAMERA_ROTATION_INVALID")
        cross = _cross([matrix[i][0] for i in range(3)], [matrix[i][1] for i in range(3)])
        if sum(cross[i] * matrix[i][2] for i in range(3)) < 0:
            errors.append("CAMERA_ROTATION_REFLECTION")
        if isinstance(geometry, dict) and geometry.get("points") != [position]:
            errors.append("CAMERA_POSITION_GEOMETRY_MISMATCH")
    elif calibration == "AFFINE_GROUND_PLANE_SYNTHETIC":
        required = {"position", "ground_to_pixel", "plane_z_m", "width", "height",
                    "physical_pose_status"}
        if not required.issubset(properties):
            return ["CAMERA_CALIBRATION_INCOMPLETE"]
        if properties["position"] is not None or properties["physical_pose_status"] != "UNKNOWN":
            errors.append("UNKNOWN_CAMERA_POSE_REQUIRED")
        a, b = properties["ground_to_pixel"]
        determinant = a[0] * b[1] - a[1] * b[0]
        if not math.isfinite(determinant) or abs(determinant) <= 1e-10:
            errors.append("CAMERA_AFFINE_DEGENERATE")
    elif calibration == "UNAVAILABLE":
        if (properties.get("position") is not None
                or properties.get("physical_pose_status") != "UNKNOWN"):
            errors.append("UNKNOWN_CAMERA_POSE_REQUIRED")
    elif calibration is not None:
        errors.append("CAMERA_CALIBRATION_KIND_UNSUPPORTED")
    return errors


def _object_errors(obj: Payload, baseline: Payload | None = None) -> list[str]:
    if (set(obj) != _OBJECT_KEYS or not isinstance(obj.get("kind"), str)
            or obj["kind"] not in _KINDS):
        return ["OBJECT_SCHEMA_INVALID"]
    kind = obj["kind"]
    errors: list[str] = []
    for field in ("object_id", "label", "semantic", "authority"):
        try:
            _text(obj[field], field)
        except ValueError as exc:
            errors.append(str(exc))
    semantics = _SEMANTICS[kind]
    if (not isinstance(obj["semantic"], str) or obj["semantic"] not in semantics) and (
        baseline is None or obj["semantic"] != baseline["semantic"]
    ):
        errors.append("SEMANTIC_UNSUPPORTED")
    editable = obj["editable_fields"]
    if not isinstance(editable, list) or any(
        not isinstance(x, str) or x not in _EDITABLE for x in editable
    ):
        errors.append("EDITABLE_FIELDS_INVALID")
    properties = obj["properties"]
    if not isinstance(properties, dict) or any(k not in _PROPERTY_KEYS[kind] for k in properties):
        errors.append("PROPERTIES_UNSUPPORTED")
    else:
        errors.extend(_properties_errors(kind, properties, obj["geometry"]))
        if baseline is not None:
            for key in {"calibration_kind", "convention", "physical_pose_status", "region_id"}:
                if properties.get(key) != baseline["properties"].get(key):
                    errors.append("PROPERTY_IDENTITY_IMMUTABLE")
    calibration = properties.get("calibration_kind") if isinstance(properties, dict) else None
    unknown_camera = isinstance(calibration, str) and calibration in {
        "AFFINE_GROUND_PLANE_SYNTHETIC", "UNAVAILABLE",
    }
    errors.extend(_geometry_errors(kind, obj["geometry"], unknown_camera))
    if baseline is not None and any(obj[key] != baseline[key] for key in (
        "object_id", "kind", "authority", "editable_fields",
    )):
        errors.append("AUTHORITY_OR_IDENTITY_IMMUTABLE")
    return sorted(set(errors))


def _relationship_errors(obj: Payload, objects: list[Payload]) -> list[str]:
    """Check declared references without inferring semantic authority from geometry."""
    props = obj.get("properties")
    if not isinstance(props, dict):
        return []
    errors = []
    if obj["kind"] == "PORTAL":
        region_ids = {item["properties"].get("region_id", item["object_id"])
                      for item in objects if item["kind"] == "REGION"}
        sides = [props.get(key) for key in ("inside_region_id", "outside_region_id")]
        if any(side is not None for side in sides):
            if any(not isinstance(side, str) or side not in region_ids for side in sides):
                errors.append("PORTAL_REGION_REFERENCE_INVALID")
            elif sides[0] == sides[1]:
                errors.append("PORTAL_REGIONS_IDENTICAL")
    elif obj["kind"] == "WALKABLE" and _number(props.get("plane_z_m")):
        geometry = obj.get("geometry")
        if isinstance(geometry, dict) and isinstance(geometry.get("points"), list):
            for point in geometry["points"]:
                if _vector(point, 3) and abs(point[2] - props["plane_z_m"]) > 1e-6:
                    errors.append("WALKABLE_PLANE_GEOMETRY_MISMATCH")
    return sorted(set(errors))


class ReviewStore:
    """Store validated review overlays using immutable rows and version checks."""

    def __init__(self, db_path: Path, scenes: Mapping[str, Payload]) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._scene_ids = frozenset(scenes)
        with self._connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS scenes (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL, hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS drafts (
                    id TEXT PRIMARY KEY, scene_id TEXT NOT NULL, payload TEXT NOT NULL,
                    hash TEXT NOT NULL, FOREIGN KEY(scene_id) REFERENCES scenes(id));
                CREATE TABLE IF NOT EXISTS validations (
                    id TEXT PRIMARY KEY, scene_id TEXT NOT NULL, draft_id TEXT NOT NULL,
                    payload TEXT NOT NULL, hash TEXT NOT NULL,
                    FOREIGN KEY(scene_id) REFERENCES scenes(id),
                    FOREIGN KEY(draft_id) REFERENCES drafts(id));
                CREATE TABLE IF NOT EXISTS versions (
                    id TEXT PRIMARY KEY, scene_id TEXT NOT NULL, version INTEGER NOT NULL,
                    draft_id TEXT UNIQUE, payload TEXT NOT NULL, hash TEXT NOT NULL,
                    UNIQUE(scene_id, version), FOREIGN KEY(scene_id) REFERENCES scenes(id));
                CREATE TABLE IF NOT EXISTS result_reviews (
                    id TEXT PRIMARY KEY, scene_id TEXT NOT NULL, payload TEXT NOT NULL,
                    hash TEXT NOT NULL, FOREIGN KEY(scene_id) REFERENCES scenes(id));
                CREATE TABLE IF NOT EXISTS management_notes (
                    id TEXT PRIMARY KEY, scene_id TEXT NOT NULL, payload TEXT NOT NULL,
                    hash TEXT NOT NULL, FOREIGN KEY(scene_id) REFERENCES scenes(id));
                CREATE INDEX IF NOT EXISTS drafts_scene ON drafts(scene_id);
                CREATE INDEX IF NOT EXISTS validations_draft ON validations(draft_id);
                CREATE INDEX IF NOT EXISTS results_scene ON result_reviews(scene_id);
                CREATE INDEX IF NOT EXISTS notes_scene ON management_notes(scene_id);
            """)
            for table in _TABLES:
                for action in ("UPDATE", "DELETE"):
                    db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()}
                        BEFORE {action} ON {table} BEGIN
                        SELECT RAISE(ABORT, 'APPEND_ONLY_REVIEW_STORE'); END""")
        with self._transaction() as db:
            for scene_id, supplied in scenes.items():
                snapshot = _clone(supplied)
                self._check_scene(scene_id, snapshot)
                existing = db.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
                if existing is not None:
                    stored = self._decode(existing)
                    if stored != snapshot:
                        raise ValueError("SCENE_REGISTRATION_MISMATCH")
                else:
                    self._insert(db, "scenes", scene_id, snapshot)
                    initial = {
                        "scene_id": scene_id, "version": 0, "source_hash": snapshot["source_hash"],
                        "model_revision": snapshot["model_revision"], "run_id": snapshot["run_id"],
                        "objects": snapshot["objects"], "status": "BASELINE",
                        "authority": "SOURCE_SNAPSHOT", "created_at": self._now(),
                    }
                    self._insert(db, "versions", f"{scene_id}:0", initial,
                                 scene_id=scene_id, version=0)
            self._verify(db)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat(timespec="microseconds")

    @staticmethod
    def _check_scene(scene_id: str, snapshot: Payload) -> None:
        _text(scene_id, "scene_id", 256)
        if set(snapshot) != {"scene_id", "source_hash", "model_revision", "run_id", "objects"}:
            raise ValueError("SCENE_SCHEMA_INVALID")
        if snapshot["scene_id"] != scene_id:
            raise ValueError("SCENE_ID_MISMATCH")
        for field in ("source_hash", "model_revision", "run_id"):
            _text(snapshot[field], field)
        if len(snapshot["source_hash"]) != 64 or any(
            char not in "0123456789abcdef" for char in snapshot["source_hash"]
        ):
            raise ValueError("SOURCE_HASH_INVALID")
        if not isinstance(snapshot["objects"], list) or not snapshot["objects"]:
            raise ValueError("SCENE_OBJECTS_INVALID")
        identifiers = []
        for obj in snapshot["objects"]:
            if not isinstance(obj, dict) or _object_errors(obj):
                raise ValueError("SCENE_OBJECT_INVALID")
            identifiers.append(obj["object_id"])
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("SCENE_OBJECT_ID_DUPLICATE")
        if any(_relationship_errors(obj, snapshot["objects"]) for obj in snapshot["objects"]):
            raise ValueError("SCENE_OBJECT_RELATIONSHIP_INVALID")

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    @staticmethod
    def _decode(row: sqlite3.Row) -> Payload:
        payload: Payload = json.loads(row["payload"])
        if _hash(payload) != row["hash"]:
            raise ValueError("REVIEW_INTEGRITY_MISMATCH")
        return payload

    @staticmethod
    def _insert(db: sqlite3.Connection, table: str, row_id: str, payload: Payload,
                **columns: object) -> None:
        assert table in _TABLES
        names = ["id", "payload", "hash", *columns]
        values = [row_id, _json(payload), _hash(payload), *columns.values()]
        db.execute(f"INSERT INTO {table} ({','.join(names)}) VALUES "
                   f"({','.join('?' for _ in names)})", values)

    def _verify(self, db: sqlite3.Connection) -> None:
        for table in _TABLES:
            for row in db.execute(f"SELECT * FROM {table}"):
                payload = self._decode(row)
                if table != "scenes" and payload["scene_id"] != row["scene_id"]:
                    raise ValueError("REVIEW_SCENE_BINDING_INVALID")
        for scene_id in self._scene_ids:
            scene = self._scene(db, scene_id)
            rows = db.execute("SELECT * FROM versions WHERE scene_id=? ORDER BY version",
                              (scene_id,)).fetchall()
            if [row["version"] for row in rows] != list(range(len(rows))):
                raise ValueError("REVIEW_VERSION_CHAIN_INVALID")
            previous = None
            for row in rows:
                version = self._decode(row)
                if version["source_hash"] != scene["source_hash"] or (
                    version["model_revision"] != scene["model_revision"]
                ) or version["run_id"] != scene["run_id"] or version["version"] != row["version"]:
                    raise ValueError("REVIEW_SOURCE_BINDING_INVALID")
                if previous is None:
                    if version["objects"] != scene["objects"]:
                        raise ValueError("REVIEW_BASELINE_MISMATCH")
                elif version["previous_version_hash"] != _hash(previous):
                    raise ValueError("REVIEW_VERSION_CHAIN_INVALID")
                previous = version

    def _scene(self, db: sqlite3.Connection, scene_id: str) -> Payload:
        if scene_id not in self._scene_ids:
            raise ValueError("SCENE_NOT_FOUND")
        row = db.execute("SELECT * FROM scenes WHERE id=?", (scene_id,)).fetchone()
        if row is None:
            raise ValueError("SCENE_NOT_FOUND")
        return self._decode(row)

    def _latest(self, db: sqlite3.Connection, scene_id: str) -> Payload:
        self._scene(db, scene_id)
        row = db.execute("SELECT * FROM versions WHERE scene_id=? ORDER BY version DESC LIMIT 1",
                         (scene_id,)).fetchone()
        assert row is not None
        return self._decode(row)

    def _draft(self, db: sqlite3.Connection, draft_id: str) -> Payload:
        row = db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
        if row is None:
            raise ValueError("DRAFT_NOT_FOUND")
        draft = self._decode(row)
        self._scene(db, draft["scene_id"])
        return draft

    def state(self, scene_id: str) -> Payload:
        with self._connection() as db:
            scene = self._scene(db, scene_id)
            current = self._latest(db, scene_id)
            lists = {table: [self._decode(row) for row in db.execute(
                f"SELECT * FROM {table} WHERE scene_id=? ORDER BY rowid", (scene_id,),
            )] for table in (
                "drafts", "validations", "versions", "result_reviews", "management_notes",
            )}
            history = sorted([_clone(item) for item in (
                *lists["drafts"], *lists["validations"], *lists["versions"],
                *lists["result_reviews"], *lists["management_notes"],
            )],
                             key=lambda x: (x["created_at"], x.get("version", -1)))
            statuses = {x["draft_id"]: x["status"] for x in lists["validations"]}
            statuses.update({x["draft_id"]: "PUBLISHED" for x in lists["versions"]
                             if "draft_id" in x})
            for draft in lists["drafts"]:
                draft["status"] = statuses.get(draft["draft_id"], "DRAFT")
                if draft["status"] != "PUBLISHED" and draft["base_version"] != current["version"]:
                    draft["status"] = "STALE"
            return {
                "scene_id": scene_id, "source_hash": scene["source_hash"],
                "model_revision": scene["model_revision"], "run_id": scene["run_id"],
                "current_version": current["version"], "objects": current["objects"],
                "baseline_objects": scene["objects"], **lists, "history": history,
                "notes": lists["management_notes"],
                "authority": "SYNTHETIC_REVIEW_ONLY",
                "inference_status": "NEEDS_RERUN" if current["version"] else "BASELINE",
            }

    def save_draft(self, scene_id: str, object_id: str, changes: Payload, base_version: int,
                   reviewer: str, reason: str) -> Payload:
        base_version = _version(base_version)
        reviewer, reason = _text(reviewer, "reviewer", 256), _text(reason, "reason")
        if not isinstance(changes, dict) or not changes:
            raise ValueError("CHANGES_REQUIRED")
        changes = _clone(changes)
        with self._transaction() as db:
            current = self._latest(db, scene_id)
            if current["version"] != base_version:
                raise ValueError("VERSION_CONFLICT")
            before = next((obj for obj in current["objects"]
                           if obj["object_id"] == object_id), None)
            if before is None:
                raise ValueError("OBJECT_NOT_FOUND")
            if any(key not in _EDITABLE or key not in before["editable_fields"] for key in changes):
                raise ValueError("FIELD_NOT_EDITABLE")
            after = {**before, **changes}
            if after == before:
                raise ValueError("CHANGES_REQUIRED")
            draft = {
                "draft_id": "draft_" + uuid.uuid4().hex, "scene_id": scene_id,
                "source_hash": current["source_hash"], "model_revision": current["model_revision"],
                "run_id": current["run_id"], "base_version": base_version, "object_id": object_id,
                "changes": changes, "before": before, "after": after, "status": "DRAFT",
                "reviewer": reviewer, "reason": reason, "created_at": self._now(),
            }
            self._insert(db, "drafts", draft["draft_id"], draft, scene_id=scene_id)
            return draft

    def validate_draft(self, draft_id: str) -> Payload:
        with self._transaction() as db:
            draft = self._draft(db, draft_id)
            current = self._latest(db, draft["scene_id"])
            errors = _object_errors(draft["after"], draft["before"])
            errors.extend(_relationship_errors(draft["after"], current["objects"]))
            if current["version"] != draft["base_version"]:
                errors.append("VERSION_CONFLICT")
            if db.execute("SELECT 1 FROM versions WHERE draft_id=?", (draft_id,)).fetchone():
                errors.append("DRAFT_ALREADY_PUBLISHED")
            validation = {
                "validation_id": "validation_" + uuid.uuid4().hex, "draft_id": draft_id,
                "scene_id": draft["scene_id"], "source_hash": draft["source_hash"],
                "base_version": draft["base_version"], "draft_hash": _hash(draft),
                "valid": not errors, "errors": sorted(set(errors)),
                "status": "INVALID" if errors else "VALIDATED", "created_at": self._now(),
                "authority": "SYNTHETIC_REVIEW_ONLY",
            }
            self._insert(db, "validations", validation["validation_id"], validation,
                         scene_id=draft["scene_id"], draft_id=draft_id)
            return validation

    def publish_draft(self, draft_id: str, reviewer: str, reason: str,
                      expected_version: int) -> Payload:
        expected_version = _version(expected_version)
        reviewer, reason = _text(reviewer, "reviewer", 256), _text(reason, "reason")
        with self._transaction() as db:
            draft = self._draft(db, draft_id)
            current = self._latest(db, draft["scene_id"])
            if current["version"] != expected_version or draft["base_version"] != expected_version:
                raise ValueError("VERSION_CONFLICT")
            row = db.execute(
                "SELECT * FROM validations WHERE draft_id=? ORDER BY rowid DESC LIMIT 1",
                (draft_id,),
            ).fetchone()
            if row is None:
                raise ValueError("VALIDATION_REQUIRED")
            validation = self._decode(row)
            if not validation["valid"] or validation["draft_hash"] != _hash(draft):
                raise ValueError("VALIDATION_FAILED")
            if (_object_errors(draft["after"], draft["before"])
                    or _relationship_errors(draft["after"], current["objects"])):
                raise ValueError("VALIDATION_FAILED")
            objects = [draft["after"] if obj["object_id"] == draft["object_id"] else obj
                       for obj in current["objects"]]
            version = expected_version + 1
            overlay = {
                "schema": "workbench.scene-overlay.v1", "scene_id": draft["scene_id"],
                "source_hash": draft["source_hash"], "model_revision": draft["model_revision"],
                "version": version, "objects": objects,
                "authority": "SYNTHETIC_REVIEW_ONLY",
            }
            publication = {
                **overlay, "run_id": draft["run_id"], "draft_id": draft_id,
                "validation_id": validation["validation_id"], "previous_version": expected_version,
                "previous_version_hash": _hash(current), "object_id": draft["object_id"],
                "before": draft["before"], "after": draft["after"], "changes": draft["changes"],
                "status": "PUBLISHED", "reviewer": reviewer, "reason": reason,
                "created_at": self._now(), "overlay": overlay, "overlay_hash": _hash(overlay),
                "affected_runs": [{"run_id": draft["run_id"], "status": "NEEDS_RERUN"}],
                "formal_approval": False,
            }
            self._insert(db, "versions", f"{draft['scene_id']}:{version}", publication,
                         scene_id=draft["scene_id"], version=version, draft_id=draft_id)
            return publication

    def record_result(self, scene_id: str, event_ref: str, decision: str, reason: str,
                      reviewer: str, run_ref: str) -> Payload:
        event_ref, run_ref = _text(event_ref, "event_ref", 512), _text(run_ref, "run_ref", 512)
        reason, reviewer = _text(reason, "reason"), _text(reviewer, "reviewer", 256)
        if not isinstance(decision, str) or decision not in {
            "SUPPORT", "REJECT", "UNKNOWN", "MORE_EVIDENCE",
        }:
            raise ValueError("RESULT_DECISION_INVALID")
        with self._transaction() as db:
            scene = self._scene(db, scene_id)
            if run_ref != scene["run_id"]:
                raise ValueError("RESULT_RUN_MISMATCH")
            current = self._latest(db, scene_id)
            result = {
                "review_id": "result_" + uuid.uuid4().hex, "scene_id": scene_id,
                "source_hash": scene["source_hash"], "run_ref": run_ref, "event_ref": event_ref,
                "decision": decision, "reviewer": reviewer, "reason": reason,
                "annotation_version": current["version"], "created_at": self._now(),
                "status": "HUMAN_RESULT_REVIEW", "authority": "RESEARCH_JUDGMENT_ONLY",
                "algorithm_result_modified": False,
            }
            self._insert(db, "result_reviews", result["review_id"], result, scene_id=scene_id)
            return result

    def record_note(self, scene_id: str, event_ref: str, status: str, note: str,
                    reviewer: str, run_ref: str) -> Payload:
        """Append handling state; a management note never changes research judgments."""
        event_ref, run_ref = _text(event_ref, "event_ref", 512), _text(run_ref, "run_ref", 512)
        note, reviewer = _text(note, "note"), _text(reviewer, "reviewer", 256)
        if not isinstance(status, str) or status not in {"OPEN", "IN_PROGRESS", "RESOLVED"}:
            raise ValueError("HANDLING_STATUS_INVALID")
        with self._transaction() as db:
            scene = self._scene(db, scene_id)
            if run_ref != scene["run_id"]:
                raise ValueError("RESULT_RUN_MISMATCH")
            record = {
                "note_id": "note_" + uuid.uuid4().hex, "scene_id": scene_id,
                "source_hash": scene["source_hash"], "run_ref": run_ref, "event_ref": event_ref,
                "handling_status": status, "note": note, "reviewer": reviewer,
                "created_at": self._now(), "status": "MANAGEMENT_NOTE",
                "authority": "HANDLING_NOTE_ONLY", "algorithm_result_modified": False,
            }
            self._insert(db, "management_notes", record["note_id"], record, scene_id=scene_id)
            return record
