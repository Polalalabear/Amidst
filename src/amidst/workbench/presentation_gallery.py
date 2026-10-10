"""Fixed, human-research artifact gallery; no inference, truth reader or archive export.

Family membership comes from WORKBENCH_EXPERIMENT_COVERAGE, not a repository scan.
PNG content is pinned when the gallery is assembled and verified at every read.
RRD/MP4/HTML/GIF entries describe existence only; their bytes are never opened.
"""

from __future__ import annotations

import builtins
import copy
import csv
import io
import json
import math
import re
from dataclasses import dataclass
from hashlib import sha256
from itertools import islice
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image

from amidst.engineering.access import FreezeReceipt, digest
from amidst.workbench.scenes import AggregateEvaluationDTO

Json = dict[str, Any]
MAX_PNG_BYTES = 10 * 1024 * 1024
MAX_METADATA_BYTES = 256 * 1024
MAX_IMAGES = 256
MAX_TABLE_ROWS = 128
_HEX = re.compile(r"[0-9a-f]{64}")
_IDENTIFIER = re.compile(r"[A-Za-z0-9_. -]{1,100}")
_CHARTS = (
    "accuracy_ade",
    "accuracy_fde",
    "accuracy_minade_at_k",
    "accuracy_minfde_at_k",
    "candidate_count",
    "collision_rate",
    "constraint_rate",
    "coverage_at_k",
    "feasible_recall",
    "impossible_transition_rate",
    "path_length_error",
    "physical_validity",
    "projection_confidence",
    "projection_error",
    "projection_methods",
    "projection_uncertainty",
    "runtime",
    "search_nodes",
    "termination_categories",
    "travel_time_error",
)
_ABLATION_CHARTS = tuple(
    x
    for x in _CHARTS
    if x
    not in {
        "projection_confidence",
        "projection_methods",
        "projection_uncertainty",
    }
)
_NATIVE_CHARTS = tuple(
    x
    for x in _CHARTS
    if x
    in {
        "accuracy_ade",
        "accuracy_fde",
        "accuracy_minade_at_k",
        "accuracy_minfde_at_k",
        "candidate_count",
        "collision_rate",
        "constraint_rate",
        "coverage_at_k",
        "physical_validity",
        "runtime",
        "termination_categories",
    }
)
_CSV_COLUMNS = (
    "case_id",
    "method_id",
    "k",
    "result_type",
    "status",
    "ade_m",
    "fde_m",
    "min_ade_at_k_m",
    "min_fde_at_k_m",
    "coverage_at_k",
    "collision_rate",
    "constraint_violation_rate",
    "candidate_count",
    "expanded_states",
    "inference_runtime_s",
    "termination_reason",
    "projection_error_m",
    "feasible_candidate_recall",
    "impossible_transition_rate",
    "path_length_error_m",
    "travel_time_error_s",
)
_TEXT_COLUMNS = frozenset({"case_id", "method_id", "result_type", "status", "termination_reason"})
_LEGACY_COLUMNS = (
    "Case",
    "Method",
    "K",
    "Status",
    "ADE",
    "FDE",
    "minADE@K",
    "minFDE@K",
    "Coverage@K",
    "Physical validity",
    "Candidates",
    "Expanded states",
    "Runtime",
    "Termination",
)
_LEGACY_TEXT = frozenset({"Case", "Method", "Status", "Physical validity", "Termination"})
_RECOVERY = "data/finalization/reviewed_run_recovery_20261008/evaluation"
_V5 = "data/finalization/reviewed_run_v5/evaluation"
_E1 = "data/engineering/local_run/local_camera_v1/test/checkpoints/final"
_ACCURACY = "data/engineering/local_run/accuracy_v2/test/final"
_ACCURACY_CURATED = "data/engineering/accuracy_20261010/validation.json"
# Published a0cef96 receipt. Certification is server-owned, never a caller option.
_ACCURACY_CURATED_SHA256 = "01639e15c8ca3a7d66c36ffaf2e464e2180189b737cfe8a9625b072b2dc21555"
_ACCURACY_CURATED_MAX_BYTES = 512 * 1024
_ACCURACY_MODES = ("photos_only", "photos_plus_observations")
_ACCURACY_VARIANTS = (
    "baseline", "pixel_only", "appearance_only", "prior_only", "features_full",
    "behavior_only", "motion_diagnostic", "end_to_end",
)
_ACCURACY_CARDS = {
    ("INFERRED_GAP_ALTERNATIVES", "GAP_ALTERNATIVES"),
    ("ENTER_DOOR", "UNKNOWN"), ("EXIT_DOOR", "SUPPORTED"),
    ("TURN_CORNER", "UNKNOWN"), ("LOST_NEAR_CORNER", "UNKNOWN"),
    ("DWELL", "SUPPORTED"), ("ENTER_DOOR", "SUPPORTED"),
}


class GalleryError(ValueError):
    """Fixed safe codes; callers never receive filesystem locators or source payloads."""


@dataclass(frozen=True)
class _Asset:
    relative: str
    root: str = "ENGINEERING"
    kind: str = "PNG"
    gt_overlay: bool | None = False


@dataclass(frozen=True)
class _Table:
    relative: str
    parser: str = "csv"
    label: str = "Frozen aggregate table"


@dataclass(frozen=True)
class _Family:
    key: str
    title: str
    classification: str
    images: tuple[_Asset, ...] = ()
    artifacts: tuple[_Asset, ...] = ()
    tables: tuple[_Table, ...] = ()
    gt_debug_only: bool = False
    model_id: str | None = None
    authority: str | None = None
    limitation: str = "Historical artifact availability does not certify a new experiment."


def _pngs(
    directory: str,
    names: tuple[str, ...],
    *,
    root: str = "ENGINEERING",
    gt_overlay: bool | None = False,
) -> tuple[_Asset, ...]:
    return tuple(_Asset(f"{directory}/{name}.png", root, gt_overlay=gt_overlay) for name in names)


_SCHOOL = "data/pilot/school_v3_pilot_20261005"
_MULTISITE = "data/pilot/school_v3_multisite_20261005"
_WALL = "data/pilot/phase1_wall_pilot_20261005/office"
_FAMILIES = (
    _Family(
        "e0-simulation",
        "E0 simulation-v2",
        "SYNTHETIC_ENGINEERING",
        images=(_Asset("data/engineering/local_run/simulation_v2/presentation/inference.png"),),
        artifacts=(
            _Asset(
                "data/engineering/local_run/simulation_v2/presentation/inference.rrd", kind="RRD"
            ),
        ),
        tables=(_Table("data/engineering/simulation_20261008/evaluation_summary.json", "e0"),),
        model_id="synthetic-lab-v1",
        authority="CONFIGURED_ENGINEERING_ONLY",
    ),
    _Family(
        "e1-local-camera",
        "E1 local-camera",
        "SYNTHETIC_PIXEL_PILOT",
        images=_pngs(
            f"{_E1}/cards",
            (
                "dwell",
                "enter_door",
                "exit_door",
                "inferred_gap_alternatives",
                "lost_near_corner",
                "possible_loitering",
                "turn_corner",
            ),
        ),
        tables=(_Table(f"{_E1}/evaluation.json", "e1", "Frozen E1 metrics and ablations"),),
        model_id="synthetic-local-camera-v1",
        authority="SYNTHETIC_CONFIG",
    ),
    _Family(
        "product-p7-p12",
        "P7–P12 product",
        "LOCAL_SYNTHETIC_PRODUCT",
        tables=(
            _Table(
                "data/product/checkpoint_20261008/evaluation.json",
                "product",
                "Conditional appearance and stitching evaluation",
            ),
        ),
        model_id="synthetic-local-camera-v1",
        authority="CONFIGURED_ENGINEERING_DIAGNOSTIC_ONLY",
        limitation="MP4 status only; 15 fps hold presentation does not change 2.5 Hz source CV.",
    ),
    _Family(
        "reviewed-recovery-demos",
        "Reviewed Office recovery demos",
        "REVIEWED_PARTIAL_RECOVERY",
        images=tuple(
            _Asset(f"{_RECOVERY}/demos/{case}/preview.png") for case in ("case1", "case3")
        ),
        artifacts=tuple(
            _Asset(f"{_RECOVERY}/demos/{case}/reviewed.rrd", kind="RRD")
            for case in ("case1", "case3")
        ),
        limitation="Case1/Case3 local partial evidence; "
        "full Exit and Case2/Case3 gates remain BLOCKED.",
    ),
    _Family(
        "recovery-benchmark",
        "Recovery benchmark / ablations",
        "REVIEWED_PARTIAL_RECOVERY",
        images=(
            _pngs(f"{_RECOVERY}/charts", _CHARTS)
            + _pngs(f"{_RECOVERY}/ablations/charts", _ABLATION_CHARTS)
        ),
        tables=(
            _Table(f"{_RECOVERY}/benchmark_table.csv", label="Recovery baseline"),
            _Table(f"{_RECOVERY}/ablations/benchmark_table.csv", label="Recovery ablations"),
        ),
        limitation="27 baseline / 45 ablation rows are bounded historical results, "
        "with BLOCKED/N/A retained.",
    ),
    _Family(
        "reviewed-v5",
        "Historical reviewed V5",
        "HISTORICAL_REVIEWED_REPORT",
        images=(
            _pngs(f"{_V5}/charts", _CHARTS)
            + tuple(_Asset(f"{_V5}/demos/{case}/preview.png") for case in ("case1", "case3"))
        ),
        artifacts=tuple(
            _Asset(f"{_V5}/demos/{case}/reviewed.rrd", kind="RRD") for case in ("case1", "case3")
        ),
        tables=(_Table(f"{_V5}/benchmark_table.csv", label="Historical V5 baseline"),),
        limitation="Report charts exist independently of missing V5 raw demos; "
        "recovery is separate.",
    ),
    _Family(
        "diagnostic-rerun",
        "Office / auditorium / corridor diagnostic Rerun",
        "DIAGNOSTIC_ONLY",
        images=tuple(
            _Asset(
                f"data/pilot/phase1_finalization_20261006/{run}/diagnostics/"
                f"{site}/demo/preview.png",
                "CANONICAL",
                gt_overlay=None,
            )
            for run in ("local_run", "fresh_run")
            for site in ("office", "auditorium", "corridor")
        ),
        artifacts=tuple(
            _Asset(
                f"data/pilot/phase1_finalization_20261006/{run}/diagnostics/"
                f"{site}/demo/diagnostic.rrd",
                "CANONICAL",
                "RRD",
                None,
            )
            for run in ("local_run", "fresh_run")
            for site in ("office", "auditorium", "corridor")
        ),
        gt_debug_only=True,
        limitation="Source presentation JSON embeds GT debug samples and is never opened here. "
        "Preview GT visibility is unknown; this family stays debug-only.",
    ),
    _Family(
        "school-downstream",
        "School downstream 3D pilot",
        "GT_DEBUG_ONLY",
        images=(
            _Asset(
                "data/pilot/phase1_downstream_20261005/run_01/visualization/preview_3d.png",
                "CANONICAL",
                gt_overlay=True,
            ),
        ),
        artifacts=(
            _Asset(
                "data/pilot/phase1_downstream_20261005/run_01/visualization/debug.rrd",
                "CANONICAL",
                "RRD",
                True,
            ),
        ),
        gt_debug_only=True,
        limitation="Documented 50 GT debug markers; no normal presentation or Agent consumption.",
    ),
    _Family(
        "school-rendered",
        "School rendered pilot galleries",
        "ANNOTATED_PILOT_DEBUG",
        images=(
            tuple(
                _Asset(f"{directory}/trajectory_preview.png", "CANONICAL", gt_overlay=None)
                for directory in (
                    _SCHOOL,
                    _WALL,
                    *(f"{_MULTISITE}/{site}" for site in ("office", "auditorium", "classroom101")),
                )
            )
            + (_Asset(f"{_MULTISITE}/overview.png", "CANONICAL", gt_overlay=None),)
            + _pngs(
                f"{_SCHOOL}/representative",
                (
                    "01_visible_start_t0.0",
                    "02_approaching_occlusion_t3.4",
                    "03_entering_gap_t3.6",
                    "04_middle_of_gap_t6.4",
                    "05_visible_again_t9.4",
                ),
                root="CANONICAL",
                gt_overlay=None,
            )
            + _pngs(
                f"{_WALL}/representative",
                (
                    "01_visible_start_t0.0",
                    "02_approaching_occlusion_t4.0",
                    "03_entering_gap_t4.2",
                    "04_middle_of_gap_t6.4",
                    "05_visible_again_t9.0",
                ),
                root="CANONICAL",
                gt_overlay=None,
            )
        ),
        artifacts=tuple(
            _Asset(f"{directory}/trajectory_preview.gif", "CANONICAL", "GIF", None)
            for directory in (_SCHOOL, _WALL)
        ),
        gt_debug_only=True,
        limitation="Annotated marker/planned trajectories are not an unannotated CV sequence. "
        "Only named previews are registered; raw frame directories are never enumerated.",
    ),
    _Family(
        "human-review-preview",
        "Human review / four-panel preview",
        "VIEW_ONLY_DIAGNOSTIC",
        images=(_Asset("human_review/frames/topology_context/topology_preview.png"),),
        authority="VIEW_ONLY",
        limitation="Original 50 diagnostic preview frames plus eight audit stills; 4/5/9 s "
        "camera stills are not continuous camera video. No new rendering or inference.",
    ),
    _Family(
        "projection-upgrade",
        "Projection upgrade / mitigation",
        "UNMATERIALIZED_HISTORY",
        artifacts=(
            _Asset(
                "data/pilot/phase1_projection_model_upgrade_20261006/verified_run",
                kind="RUN_DIRECTORY",
            ),
            _Asset(
                "data/pilot/phase1_projection_model_upgrade_20261006/verified_run",
                "CANONICAL",
                "RUN_DIRECTORY",
            ),
        ),
        limitation="Helpers or historical PASS do not establish available plots/results; "
        "exact-input rebuild needed.",
    ),
    _Family(
        "native-mock-benchmarks",
        "Native / mock benchmark plots",
        "SYNTHETIC_AND_MOCK_COMPARISON",
        images=(
            _pngs("data/reports/benchmark", _NATIVE_CHARTS)
            + _pngs("data/reports/benchmark/mock_comparison", _ABLATION_CHARTS)
        ),
        tables=(
            _Table(
                "data/reports/benchmark/benchmark_summary.json", "native", "SYNTHETIC REGRESSION"
            ),
            _Table(
                "data/reports/benchmark/mock_comparison/benchmark_summary.json",
                "native",
                "MOCK VALIDATION",
            ),
        ),
        limitation="Synthetic regression and mock validation are distinct from "
        "formal school results.",
    ),
    _Family(
        "blocked-checkpoint",
        "Original blocked checkpoint plots",
        "HISTORICAL_BLOCKED",
        images=_pngs(
            "data/finalization/checkpoint",
            (
                "accuracy",
                "coverage",
                "physical_validity",
                "projection_confidence",
                "projection_methods",
                "runtime_search",
                "termination",
                "top_k_candidates",
            ),
        ),
        tables=(
            _Table(
                "data/finalization/checkpoint/benchmark_table.csv",
                "legacy_csv",
                label="Original BLOCKED / NOT_RUN checkpoint",
            ),
        ),
        limitation="Historical NOT_RUN/N/A rows never replace later recovery results.",
    ),
    _Family(
        "legacy-four-case",
        "Legacy four-case Rerun / Phase 2 API",
        "INTERNAL_SYNTHETIC_DEBUG",
        artifacts=tuple(
            _Asset(
                f"data/candidates/fake_downstream_20261001/{case}/debug.rrd",
                "CANONICAL",
                "RRD",
                None,
            )
            for case in ("single_path", "branching_top_k", "temporal_slack", "simplified_stair")
        ),
        gt_debug_only=True,
        limitation="Low-level mock interfaces/internal synthetic target IDs are not Agent tools; "
        "the stair fixture does not unlock Case4.",
    ),
    _Family(
        "research-accuracy-v2",
        "Research accuracy v2",
        "MEASURED_SYNTHETIC_RESEARCH_V2_WITH_TRADEOFFS",
        model_id="synthetic-local-camera-v1",
        authority="RGB_PIXELS_WITH_SYNTHETIC_CONFIG",
        limitation="Published test comparison is photos_only. Baseline/features_full use "
        "the fixed v1 pool; end_to_end changes the detected population. Non-sealed synthetic "
        "test; scores uncalibrated; UNKNOWN/failures retained; no formal acceptance.",
    ),
)


@dataclass(frozen=True)
class _PinnedImage:
    root: Path
    relative: str
    sha256: str


def _safe_path(root: Path, relative: str) -> Path:
    parsed = PurePosixPath(relative)
    if not relative or parsed.is_absolute() or ".." in parsed.parts or "\\" in relative:
        raise GalleryError("GALLERY_REFERENCE_DENIED")
    if root.is_symlink():
        raise GalleryError("GALLERY_REFERENCE_DENIED")
    candidate = root
    for part in parsed.parts:
        candidate /= part
        if candidate.is_symlink():
            raise GalleryError("GALLERY_REFERENCE_DENIED")
    try:
        candidate.resolve().relative_to(root.resolve())
    except (OSError, ValueError) as error:
        raise GalleryError("GALLERY_REFERENCE_DENIED") from error
    return candidate


def _bytes(path: Path, limit: int) -> bytes:
    try:
        with path.open("rb") as stream:
            payload = stream.read(limit + 1)
    except OSError as error:
        raise GalleryError("GALLERY_ARTIFACT_UNAVAILABLE") from error
    if len(payload) > limit:
        raise GalleryError("GALLERY_ARTIFACT_TOO_LARGE")
    return payload


def _number(value: object) -> int | float | str:
    if value is None or value == "" or value in ("N/A", "NOT_RUN", "BLOCKED", "DEFERRED"):
        return "N/A" if value in (None, "") else str(value)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        if value in ("True", "False"):
            return int(value == "True")
        try:
            value = float(value)
        except ValueError as error:
            raise GalleryError("GALLERY_TABLE_INVALID") from error
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    raise GalleryError("GALLERY_TABLE_INVALID")


def _text(value: object) -> str:
    if value is None or value == "":
        return "N/A"
    if value in ("N/A", "N/A / NOT_RUN", "NOT_CERTIFIED"):
        return str(value)
    if value == "Case 3 — Long Gap / Timing Ambiguity":
        return "Case 3 - Long Gap - Timing Ambiguity"
    if isinstance(value, str):
        value = value.replace("—", "-").replace("–", "-")
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise GalleryError("GALLERY_TABLE_INVALID")
    return value


class Gallery:
    """Server-only roots over fixed families; never accepts caller paths."""

    def __init__(self, repo: Path, canonical_root: Path | None = None) -> None:
        self._roots = {
            "ENGINEERING": repo.absolute(),
            "CANONICAL": canonical_root.absolute() if canonical_root else None,
        }
        for root in self._roots.values():
            if root is not None and root.is_symlink():
                raise GalleryError("GALLERY_REFERENCE_DENIED")
        self._images: dict[str, _PinnedImage] = {}
        self._families: dict[str, Json] = {}
        for spec in _FAMILIES:
            self._assemble(spec)

    def list(self) -> Json:
        return {
            "schema_version": "workbench.presentation-gallery.v1",
            "audience": "HUMAN_RESEARCH_DIAGNOSTIC",
            "complete": True,
            "items": [
                copy.deepcopy(
                    {
                        key: value
                        for key, value in family.items()
                        if key not in {"images", "tables", "artifacts"}
                    }
                )
                for family in self._families.values()
            ],
        }

    def detail(self, family_ref: str) -> Json:
        if not isinstance(family_ref, str) or family_ref not in self._families:
            raise GalleryError("GALLERY_FAMILY_SCOPE_DENIED")
        return copy.deepcopy(self._families[family_ref])

    def media(self, ref: str) -> tuple[str, bytes]:
        image = self._images.get(ref) if isinstance(ref, str) else None
        if image is None:
            raise GalleryError("GALLERY_MEDIA_SCOPE_DENIED")
        path = _safe_path(image.root, image.relative)
        payload = _bytes(path, MAX_PNG_BYTES)
        if sha256(payload).hexdigest() != image.sha256:
            raise GalleryError("GALLERY_MEDIA_CONTENT_CHANGED")
        return "image/png", payload

    def _root(self, kind: str) -> Path:
        root = self._roots[kind]
        if root is None:
            raise GalleryError("CANONICAL_ROOT_UNAVAILABLE")
        return root

    def _json(self, relative: str) -> tuple[Json, str]:
        payload = _bytes(_safe_path(self._root("ENGINEERING"), relative), MAX_METADATA_BYTES)
        try:
            value = json.loads(payload)
        except (ValueError, RecursionError) as error:
            raise GalleryError("GALLERY_METADATA_INVALID") from error
        if not isinstance(value, dict):
            raise GalleryError("GALLERY_METADATA_INVALID")
        return value, sha256(payload).hexdigest()

    def _image(
        self,
        spec: _Family,
        asset: _Asset,
        *,
        expected_hash: str | None = None,
        sequence_index: int | None = None,
    ) -> Json:
        if len(self._images) >= MAX_IMAGES:
            raise GalleryError("GALLERY_IMAGE_BUDGET")
        root = self._root(asset.root)
        path = _safe_path(root, asset.relative)
        payload = _bytes(path, MAX_PNG_BYTES)
        checksum = sha256(payload).hexdigest()
        if expected_hash is not None and expected_hash != checksum:
            raise GalleryError("GALLERY_INPUT_HASH_MISMATCH")
        try:
            with Image.open(io.BytesIO(payload)) as image:
                width, height = image.size
                if (
                    image.format != "PNG"
                    or not (0 < width <= 8192 and 0 < height <= 8192)
                    or (width * height > 32 * 1024 * 1024)
                ):
                    raise GalleryError("GALLERY_PNG_INVALID")
                image.verify()
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            raise GalleryError("GALLERY_PNG_INVALID") from error
        ref = "gallery-image:" + digest((spec.key, asset.root, asset.relative, checksum))[:24]
        self._images[ref] = _PinnedImage(root, asset.relative, checksum)
        return {
            "media_ref": ref,
            "label": path.stem.replace("_", " "),
            "sha256": checksum,
            "width": width,
            "height": height,
            "audience": "GT_DEBUG_ONLY" if spec.gt_debug_only else "HUMAN_RESEARCH_DIAGNOSTIC",
            "gt_overlay": asset.gt_overlay,
            "status": "VERIFIED_PNG",
            "sequence_index": sequence_index,
            "measurement_source": "HISTORICAL_PRESENTATION_NOT_CV_INPUT",
        }

    def _artifact(self, asset: _Asset) -> Json:
        try:
            path = _safe_path(self._root(asset.root), asset.relative)
            exists = path.is_dir() if asset.kind == "RUN_DIRECTORY" else path.is_file()
            status = "PRESENT" if exists else "MISSING"
        except (GalleryError, OSError) as error:
            status = str(error) if isinstance(error, GalleryError) else "ARTIFACT_UNAVAILABLE"
        return {
            "kind": asset.kind,
            "status": status,
            "verification": "EXISTENCE_ONLY",
            "access": "STATUS_ONLY",
            "sha256": None,
            "source_location": asset.root,
        }

    def _table(self, source: _Table) -> Json:
        path = _safe_path(self._root("ENGINEERING"), source.relative)
        payload = _bytes(path, MAX_METADATA_BYTES)
        rows: builtins.list[builtins.list[object]]
        if source.parser in {"csv", "legacy_csv"}:
            try:
                reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
                allowed = _CSV_COLUMNS if source.parser == "csv" else _LEGACY_COLUMNS
                text_fields = _TEXT_COLUMNS if source.parser == "csv" else _LEGACY_TEXT
                columns = [name for name in allowed if name in (reader.fieldnames or [])]
                required = {"case_id", "status"} if source.parser == "csv" else {"Case", "Status"}
                if not required <= set(columns):
                    raise GalleryError("GALLERY_TABLE_INVALID")
                records = list(islice(reader, MAX_TABLE_ROWS + 1))
                record_count = len(records)
                rows = [
                    [
                        _text(row[name]) if name in text_fields else _number(row[name])
                        for name in columns
                    ]
                    for row in records[:MAX_TABLE_ROWS]
                ]
            except (ValueError, TypeError, csv.Error) as error:
                raise GalleryError("GALLERY_TABLE_INVALID") from error
        else:
            try:
                value = json.loads(payload)
                columns, rows = self._aggregate_rows(value, source.parser)
                record_count = len(rows)
                rows = rows[:MAX_TABLE_ROWS]
            except (ValueError, TypeError, KeyError, RecursionError) as error:
                raise GalleryError("GALLERY_TABLE_INVALID") from error
        return {
            "label": source.label,
            "status": "AVAILABLE",
            "columns": columns,
            "rows": rows,
            "complete": record_count <= MAX_TABLE_ROWS,
            "source_sha256": sha256(payload).hexdigest(),
            "scope": "FROZEN_AGGREGATE_ONLY",
            "formal_phase1_acceptance": False,
        }

    @staticmethod
    def _aggregate_rows(
        value: Json, parser: str
    ) -> tuple[builtins.list[str], builtins.list[builtins.list[object]]]:
        if parser in {"e0", "e1"}:
            AggregateEvaluationDTO.model_validate(value)
        if parser == "e0":
            columns = ["mode", "measurements", "local_tracks", "eligible_contact_recall", "GT_IDF1"]
            return columns, [
                [
                    mode,
                    _number(row["measurement_count"]),
                    _number(row["local_track_count"]),
                    _number(row["eligible_detection_recall_24px"]),
                    "N/A",
                ]
                for mode, row in value["modes"].items()
            ]
        if parser == "e1":
            columns = ["mode", "ablation", "eligible_queries", "Recall1", "Recall3", "Recall5"]
            return columns, [
                [
                    mode,
                    name,
                    _number(row["eligible_query_count"]),
                    *(_number(row["identity_candidate_recall_at_k"][str(k)]) for k in (1, 3, 5)),
                ]
                for mode, summary in value.items()
                for name, row in summary["fixed_pool_feature_ablations"].items()
            ]
        if parser == "product":
            if value.get("schema_version") != "product.curated-evaluation.v1" or (
                set(value["modes"]) != {"photos_only", "photos_plus_observations"}
            ):
                raise GalleryError("GALLERY_TABLE_INVALID")
            columns = [
                "mode",
                "eligible_queries",
                "Recall1",
                "Recall3",
                "Recall5",
                "stitch_precision",
                "stitch_recall",
                "IDF1",
            ]
            return columns, [
                [
                    mode,
                    _number(row["appearance"]["handcrafted"]["eligible_queries"]),
                    *(
                        _number(row["appearance"]["handcrafted"]["tie_aware_recall_at_k"][str(k)])
                        for k in (1, 3, 5)
                    ),
                    _number(row["stitching"]["pair_precision"]),
                    _number(row["stitching"]["pair_recall"]),
                    "N/A",
                ]
                for mode, row in value["modes"].items()
            ]
        if parser == "native":
            if value.get("schema_version") != "benchmark-comparison/v1":
                raise GalleryError("GALLERY_TABLE_INVALID")
            columns = ["case", "method", "runs", "ADE_mean", "FDE_mean", "runtime_mean"]
            return columns, [
                [
                    _text(row["case_id"]),
                    _text(row["method_id"]),
                    _number(row["run_count"]),
                    *(
                        _number(row["metrics"][name]["mean"])
                        for name in ("ade_m", "fde_m", "runtime_s")
                    ),
                ]
                for row in value["rows"][: MAX_TABLE_ROWS + 1]
            ]
        raise GalleryError("GALLERY_TABLE_INVALID")

    def _preview(self, spec: _Family) -> tuple[builtins.list[Json], Json, int]:
        value, checksum = self._json("human_review/playback/build_manifest.json")
        entries = value.get("media_files")
        if value.get("schema_version") != "phase1-playback-build-v1" or (
            value.get("mode") != "VIEW_ONLY"
            or value.get("research_rerun") is not False
            or value.get("frame_count") != 50
            or value.get("media_count") != 58
            or not isinstance(entries, list)
            or len(entries) != 58
        ):
            raise GalleryError("GALLERY_PREVIEW_MANIFEST_INVALID")
        assets: list[tuple[_Asset, str, int | None]] = []
        frames: set[int] = set()
        seen: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "bytes"}:
                raise GalleryError("GALLERY_PREVIEW_MANIFEST_INVALID")
            relative, expected = entry["path"], entry["sha256"]
            if (
                not isinstance(relative, str)
                or not isinstance(expected, str)
                or (_HEX.fullmatch(expected) is None or relative in seen)
                or type(entry["bytes"]) is not int
                or not 0 < entry["bytes"] <= MAX_PNG_BYTES
            ):
                raise GalleryError("GALLERY_PREVIEW_MANIFEST_INVALID")
            match = re.fullmatch(r"frames/motion_context/motion_(\d{3})\.png", relative)
            index = int(match[1]) if match else None
            if index is not None:
                frames.add(index)
            elif relative not in {
                "frames/hr02_camera_audit/wide.png",
                "frames/hr02_camera_audit/side.png",
                *(
                    f"frames/hr02_camera_audit/camera_{camera}_frame{frame:03}.png"
                    for camera in ("FRONT", "REAR")
                    for frame in (20, 25, 45)
                ),
            }:
                raise GalleryError("GALLERY_PREVIEW_REFERENCE_DENIED")
            seen.add(relative)
            _safe_path(self._root("ENGINEERING"), "human_review/" + relative)
            assets.append((_Asset("human_review/" + relative), expected, index))
        if frames != set(range(50)):
            raise GalleryError("GALLERY_PREVIEW_MANIFEST_INVALID")
        images, missing = [], 0
        for asset, expected, index in assets:
            try:
                images.append(
                    self._image(spec, asset, expected_hash=expected, sequence_index=index)
                )
            except GalleryError:
                missing += 1
        source = value.get("source_sha256")
        return (
            images,
            {
                "source_sha256": source
                if isinstance(source, str) and _HEX.fullmatch(source)
                else None,
                "provenance_sha256": checksum,
                "preview_frame_count": 50,
                "verified_preview_frames": sum(i["sequence_index"] is not None for i in images),
                "missing_preview_frame_indices": sorted(
                    frames
                    - {i["sequence_index"] for i in images if i["sequence_index"] is not None}
                ),
            },
            missing,
        )

    def _mp4_status(self) -> builtins.list[Json]:
        try:
            value, _ = self._json("data/product/local_run/operator_v2/video_manifest.json")
        except GalleryError:
            return [
                {
                    "kind": "MP4",
                    "status": "MISSING",
                    "verification": "EXISTENCE_ONLY",
                    "access": "STATUS_ONLY",
                    "sha256": None,
                }
                for _ in range(4)
            ]
        scope, entries = value.get("scope"), value.get("artifacts")
        if value.get("schema_version") != "product.video.v1" or not isinstance(scope, dict) or (
            scope.get("model_id") != "synthetic-local-camera-v1"
            or scope.get("run_id") != "local-camera-test-v1"
            or not isinstance(entries, list) or len(entries) != 4
        ):
            raise GalleryError("GALLERY_VIDEO_MANIFEST_INVALID")
        names = []
        for entry in entries:
            name = entry.get("relative_path") if isinstance(entry, dict) else None
            if not isinstance(name, str) or re.fullmatch(r"video-[0-9a-f]{24}\.mp4", name) is None:
                raise GalleryError("GALLERY_VIDEO_REFERENCE_DENIED")
            names.append(name)
        if len(set(names)) != 4:
            raise GalleryError("GALLERY_VIDEO_MANIFEST_INVALID")
        return [
            self._artifact(_Asset("data/product/local_run/media_pool/" + name, kind="MP4"))
            for name in names
        ]

    def _accuracy_documents(self) -> tuple[Json, Json, Json]:
        payload = _bytes(
            _safe_path(self._root("ENGINEERING"), _ACCURACY_CURATED),
            _ACCURACY_CURATED_MAX_BYTES,
        )
        if sha256(payload).hexdigest() != _ACCURACY_CURATED_SHA256:
            raise GalleryError("GALLERY_ACCURACY_CONTENT_UNCERTIFIED")
        try:
            published = json.loads(payload)
            expected = published["experiments"]["test"]
            manifest, _ = self._json(_ACCURACY + "/manifest.json")
            if (
                published["schema_version"] != "accuracy.curated-validation.v2"
                or digest(manifest) != expected["manifest_sha256"]
                or {k: v for k, v in manifest.items() if k != "source_locator"}
                != {k: v for k, v in expected.items()
                    if k not in {"manifest_sha256", "comparison_sha256"}}
                or manifest["schema_version"] != "accuracy.frozen-run.v2"
                or manifest["version"] != "local-camera-accuracy-v2"
                or manifest["experiment_id"] != "accuracy-test-v2-final"
                or manifest["source_run_id"] != "local-camera-test-v1"
                or manifest["split"] != "test"
                or manifest["clock_id"] != "synthetic-seconds-v1"
                or manifest["unit"] != "METRES_SYNTHETIC_SECONDS"
                or manifest["external_model_calls"] is not False
                or manifest["formal_phase1_acceptance"] is not False
                or set(manifest["variants"]) != set(_ACCURACY_VARIANTS)
            ):
                raise GalleryError("GALLERY_ACCURACY_BINDING_MISMATCH")
            for variant in _ACCURACY_VARIANTS:
                if set(manifest["variants"][variant]) != set(_ACCURACY_MODES):
                    raise GalleryError("GALLERY_ACCURACY_BINDING_MISMATCH")
                for mode in _ACCURACY_MODES:
                    value, _ = self._json(f"{_ACCURACY}/{variant}/{mode}/receipt.json")
                    receipt = FreezeReceipt.model_validate(value)
                    entry = manifest["variants"][variant][mode]
                    binding = receipt.binding
                    if (
                        receipt.receipt_sha256 != digest(
                            receipt.model_dump(mode="json", exclude={"receipt_sha256"}))
                        or receipt.receipt_sha256 != entry["receipt_sha256"]
                        or binding.model_id != "synthetic-local-camera-v1"
                        or binding.model_revision != "1"
                        or binding.run_id != manifest["source_run_id"]
                        or binding.observation_mode != mode
                        or binding.registry_version != manifest["version"]
                        or binding.clock_id != manifest["clock_id"]
                        or binding.source_ref != "source:" + manifest["source_sha256"]
                        or binding.dataset_sha256 != manifest["dataset_sha256"]
                        or binding.config_sha256 != entry["binding_config_sha256"]
                        or binding.config_sha256 != digest({
                            "run_config": manifest["config_sha256"],
                            "experiment_id": manifest["experiment_id"], "variant": variant,
                        })
                    ):
                        raise GalleryError("GALLERY_ACCURACY_BINDING_MISMATCH")
            return published, manifest, expected
        except GalleryError:
            raise
        except (ValueError, TypeError, KeyError, RecursionError) as error:
            raise GalleryError("GALLERY_ACCURACY_BINDING_MISMATCH") from error

    @staticmethod
    def _accuracy_table(published: Json) -> Json:
        columns = [
            "variant", "mode", "population", "tracks", "ID_switches", "pairs",
            "eligible_positive_pairs", "pair_precision", "pair_recall", "Recall1", "Recall3",
            "Recall5", "contact_recall", "ground_RMS_m", "UNKNOWN", "visible_candidates",
        ]
        rows = []
        try:
            for variant in ("baseline", "features_full", "end_to_end"):
                value = published["comparison"]["test"][variant]
                if value["same_baseline_pool"] is not (variant != "end_to_end"):
                    raise GalleryError("GALLERY_ACCURACY_POPULATION_MISMATCH")
                rows.append([
                    variant, "photos_only",
                    "CHANGED_V2_TRACK_POOL" if variant == "end_to_end" else "FIXED_V1_TRACK_POOL",
                    *(_number(value[k]) for k in ("tracks", "ID_switches", "pairs",
                                                 "eligible_pair_positives", "pair_precision",
                                                 "pair_recall")),
                    *(_number(value["rank_recall_at_k"][str(k)]) for k in (1, 3, 5)),
                    *(_number(value[k]) for k in ("contact_recall", "ground_RMS_m",
                                                 "unknown_count", "visible_candidate_count")),
                ])
        except (KeyError, TypeError, ValueError) as error:
            raise GalleryError("GALLERY_ACCURACY_TABLE_INVALID") from error
        return {
            "label": "Published test comparison; changed end_to_end population is separate",
            "status": "AVAILABLE", "columns": columns, "rows": rows, "complete": True,
            "source_sha256": _ACCURACY_CURATED_SHA256,
            "scope": "PUBLISHED_CURATED_AGGREGATE_ONLY", "formal_phase1_acceptance": False,
            "evaluation_mode": "photos_only", "test_is_sealed_holdout": False,
        }

    def _accuracy_cards(self, spec: _Family, published: Json, manifest: Json) -> tuple[
        builtins.list[Json], Json, int, builtins.list[str]
    ]:
        value, checksum = self._json(_ACCURACY + "/cards_review/receipt.json")
        try:
            contract = value["contract"]
            if (
                digest(value) != digest(published["evidence"])
                or value["schema_version"] != "accuracy.review-cards.v2"
                or value["actual_source_rgb"] is not True or value["gt_overlay"] is not False
                or value["clock_and_unit"] != "SYNTHETIC_SECONDS_METRES"
                or contract["experiment_id"] != manifest["experiment_id"]
                or contract["source_run_id"] != manifest["source_run_id"]
                or contract["config_sha256"] != manifest["config_sha256"]
                or contract["read_modes"] != list(_ACCURACY_MODES)
                or contract["event_refs_bound_to_experiment_variant"] is not True
                or value["indexed_query_telemetry"]["mode"] != "photos_only"
                or published["adapter_validation"]["variant"] != "end_to_end"
                or len(value["cards"]) != len(_ACCURACY_CARDS)
            ):
                raise GalleryError("GALLERY_ACCURACY_CARDS_UNCERTIFIED")
            seen = set()
            for card in value["cards"]:
                key = (card["kind"], card["support_state"])
                if key not in _ACCURACY_CARDS or key in seen or (
                    card["path"] != "cards_review/" + "_".join(key).lower() + ".png"
                    or _HEX.fullmatch(card["sha256"]) is None
                    or re.fullmatch(r"event:[0-9a-f]{24}", card["event_ref"]) is None
                    or not 3 <= len(card["source_frames"]) <= 5
                ):
                    raise GalleryError("GALLERY_ACCURACY_CARDS_UNCERTIFIED")
                seen.add(key)
                for frame in card["source_frames"]:
                    timestamp = frame["timestamp"]
                    if (
                        frame["camera_id"] not in {"WEST", "EAST", "CORNER", "DOOR"}
                        or frame["evidence_state"] != "PROJECTED"
                        or re.fullmatch(r"media:[0-9a-f]{24}", frame["frame_ref"]) is None
                        or type(timestamp) not in {int, float}
                        or not math.isfinite(timestamp) or not 0 <= timestamp <= 24
                    ):
                        raise GalleryError("GALLERY_ACCURACY_CARDS_UNCERTIFIED")
        except GalleryError:
            raise
        except (ValueError, TypeError, KeyError) as error:
            raise GalleryError("GALLERY_ACCURACY_CARDS_UNCERTIFIED") from error
        images, missing, issues = [], 0, []
        for card in value["cards"]:
            try:
                image = self._image(
                    spec, _Asset(_ACCURACY + "/" + card["path"]), expected_hash=card["sha256"]
                )
                image.update({
                    "support_state": card["support_state"], "variant": "end_to_end",
                    "observation_mode": "photos_only",
                    "source_frame_count": len(card["source_frames"]),
                    "camera_ids": sorted({f["camera_id"] for f in card["source_frames"]}),
                    "origin": "SYNTHETIC", "underlying_image_measurement": True,
                    "presentation_only": True, "cv_input": False,
                    "measurement_source": "EXISTING_SOURCE_RGB_WITH_DERIVED_3D_REVIEW_CARD",
                })
                images.append(image)
            except GalleryError as error:
                missing += 1
                issues.append(str(error))
        return images, {
            "card_manifest_sha256": checksum, "card_manifest_content_sha256": digest(value),
            "card_variant": "end_to_end", "card_mode": "photos_only", "gt_overlay": False,
            "card_freeze_ref": "freeze:" + manifest["variants"]["end_to_end"]["photos_only"][
                "receipt_sha256"],
        }, missing, issues

    def _source(self, spec: _Family) -> Json:
        paths = {
            "e0-simulation": (
                "data/engineering/simulation_20261008/validation.json",
                ("artifacts", "scope", "source_sha256"),
            ),
            "e1-local-camera": (
                "data/engineering/local_camera_20261008/validation.json",
                ("hashes", "source_sha256"),
            ),
            "product-p7-p12": (
                "data/product/checkpoint_20261008/modecomparison.json",
                ("bindings", "static_context", "source_sha256"),
            ),
        }
        if spec.key not in paths:
            return {"source_sha256": None, "provenance_sha256": None}
        relative, fields = paths[spec.key]
        try:
            value, checksum = self._json(relative)
            source: Any = value
            for field in fields:
                source = source[field]
            return {
                "source_sha256": source
                if isinstance(source, str) and _HEX.fullmatch(source)
                else None,
                "provenance_sha256": checksum,
            }
        except (GalleryError, KeyError, TypeError):
            return {"source_sha256": None, "provenance_sha256": None}

    def _assemble(self, spec: _Family) -> None:
        images: list[Json] = []
        tables: list[Json] = []
        artifacts = [self._artifact(asset) for asset in spec.artifacts]
        missing, issues = 0, []
        source = self._source(spec)
        for asset in spec.images:
            try:
                images.append(self._image(spec, asset))
            except GalleryError as error:
                missing += 1
                if str(error) not in {"GALLERY_ARTIFACT_UNAVAILABLE", "CANONICAL_ROOT_UNAVAILABLE"}:
                    issues.append(str(error))
        if spec.key == "human-review-preview":
            try:
                preview, source, absent = self._preview(spec)
                images.extend(preview)
                missing += absent
            except GalleryError as error:
                missing += 58
                issues.append(str(error))
        if spec.key == "product-p7-p12":
            try:
                artifacts.extend(self._mp4_status())
            except (GalleryError, OSError):
                issues.append("GALLERY_VIDEO_STATUS_UNAVAILABLE")
        if spec.key == "research-accuracy-v2":
            try:
                published, manifest, expected = self._accuracy_documents()
                tables.append(self._accuracy_table(published))
                source = {
                    "source_sha256": manifest["source_sha256"],
                    "provenance_sha256": _ACCURACY_CURATED_SHA256,
                    "certification_status": "PUBLISHED_RECEIPT_AND_FROZEN_SCOPE_VERIFIED",
                    "experiment_id": manifest["experiment_id"],
                    "source_run_id": manifest["source_run_id"],
                    "dataset_sha256": manifest["dataset_sha256"],
                    "context_sha256": manifest["context_sha256"],
                    "config_sha256": manifest["config_sha256"],
                    "clock_id": manifest["clock_id"], "unit": manifest["unit"],
                    "manifest_sha256": expected["manifest_sha256"],
                    "variants": list(_ACCURACY_VARIANTS), "modes": list(_ACCURACY_MODES),
                    "comparison_mode": "photos_only", "test_is_sealed_holdout": False,
                }
                try:
                    cards, bindings, absent, errors = self._accuracy_cards(
                        spec, published, manifest
                    )
                    images.extend(cards)
                    source.update(bindings)
                    missing += absent
                    issues.extend(errors)
                except GalleryError as error:
                    missing += len(_ACCURACY_CARDS)
                    issues.append(str(error))
            except GalleryError as error:
                missing += len(_ACCURACY_CARDS) + 1
                issues.append(str(error))
                source = {"certification_status": "UNAVAILABLE"}
        for table in spec.tables:
            try:
                tables.append(self._table(table))
            except GalleryError as error:
                missing += 1
                tables.append(
                    {
                        "label": table.label,
                        "status": str(error),
                        "columns": [],
                        "rows": [],
                        "complete": False,
                    }
                )
        missing += sum(asset["status"] != "PRESENT" for asset in artifacts)
        present = len(images) + sum(table["status"] == "AVAILABLE" for table in tables)
        present += sum(
            asset["status"] == "PRESENT" and asset["kind"] != "RUN_DIRECTORY"
            for asset in artifacts
        )
        status = (
            "PARTIAL"
            if present and (missing or issues)
            else "MATERIALIZED"
            if present
            else ("NOT_MATERIALIZED")
        )
        if spec.gt_debug_only and self._roots["CANONICAL"] is None:
            status = "CANONICAL_ROOT_UNAVAILABLE"
        if spec.key == "research-accuracy-v2" and (missing or issues):
            status = "PARTIAL"
        ref = "gallery-family:" + digest(spec.key)[:24]
        self._families[ref] = {
            "family_ref": ref,
            "family_id": spec.key,
            "title": spec.title,
            "status": status,
            "classification": spec.classification,
            "origin": "SYNTHETIC" if present else None,
            "source_locations": sorted({a.root for a in spec.images + spec.artifacts}
                                       or {"ENGINEERING"}),
            "model_id": spec.model_id,
            "authority": spec.authority,
            **source,
            "audience": "GT_DEBUG_ONLY" if spec.gt_debug_only else "HUMAN_RESEARCH_DIAGNOSTIC",
            "gt_debug_only": spec.gt_debug_only,
            "normal_presentation_allowed": False,
            "formal_phase1_acceptance": False,
            "counts": {
                "images": len(images),
                "tables": sum(t["status"] == "AVAILABLE" for t in tables),
                "rrd": sum(a["kind"] == "RRD" and a["status"] == "PRESENT" for a in artifacts),
                "mp4": sum(a["kind"] == "MP4" and a["status"] == "PRESENT" for a in artifacts),
                "missing": missing,
            },
            "images": images,
            "tables": tables,
            "artifacts": artifacts,
            "issues": sorted(set(issues)),
            "limitations": [spec.limitation],
        }
