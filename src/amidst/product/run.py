"""Independent local product freeze over an immutable E1 camera pilot.

Build may compute RGB-only appearance and provisional stitch hypotheses. Load
verifies frozen bytes, actual media and the catalog; it never calls a producer,
association, Graph search, a video encoder or evaluation/GT reader. Locators in
the manifest/runtime are local administration data, never ProductContext fields.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from amidst.domain.common import Timestamp
from amidst.engineering.access import FreezeReceipt, Mode
from amidst.engineering.access import digest as canonical_digest
from amidst.engineering.local_pilot import MODES, frozen_mode, load_services
from amidst.engineering.local_service import LocalPilotService
from amidst.engineering.perception import produce_perception
from amidst.engineering.registry import (
    RegistryModel,
    ResourceRef,
    Sha256,
    opaque_ref,
    safe_relative_path,
    scope_parts,
)
from amidst.engineering.research_scene import ResearchPackage
from amidst.product.appearance import AppearanceConfig, DescriptorBundle, build_appearance_bundle
from amidst.product.contracts import EventDetail, ObservationDetail
from amidst.product.service import ProductService
from amidst.product.stitching import StitchBundle, StitchConfig, build_stitch_bundle
from amidst.product.store import (
    CanonicalRecord,
    Payload,
    ProductScope,
    RecordKind,
    RecordSetReceipt,
    SQLiteProductStore,
)
from amidst.product.video import VideoManifest, encode_videos

_SOURCE_DOCUMENTS = (
    "manifest.json", "package.json", "registry.json", "topology.json", "runtime_config.json",
    "behavior_config.json",
    *(f"{prefix}_{mode}.json" for mode in MODES
      for prefix in ("perception", "inference", "events")),
)
_MANIFEST_FILE = "product_manifest.json"


class ProductRunError(ValueError):
    """Fixed codes; local paths, raw manifests and rejected payloads stay private."""


def _plain(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _plain(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(child) for child in value]
    return value


def digest(value: object) -> str:
    return canonical_digest(_plain(value))


class FrameMetadata(RegistryModel):
    media_ref: ResourceRef
    camera_ref: ResourceRef
    camera_id: str
    frame_id: int = Field(ge=0, strict=True)
    timestamp: Timestamp
    sha256: Sha256
    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)
    media_type: Literal["image/png", "image/jpeg"]
    purpose: Literal["RGB_SEQUENCE"] = "RGB_SEQUENCE"
    annotations: Literal["NONE"] = "NONE"
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"


class _ExportRecord(RegistryModel):
    kind: RecordKind
    record_ref: ResourceRef
    camera_ids: tuple[str, ...]
    time_range: tuple[Timestamp, Timestamp]
    region_ids: tuple[str, ...]
    payload: Payload


class ProductModeReceipt(RegistryModel):
    observation_mode: Mode
    scope: ProductScope
    base_receipt: FreezeReceipt
    perception_sha256: Sha256
    appearance_sha256: Sha256
    stitch_sha256: Sha256
    canonical_export_sha256: Sha256
    record_set_receipt: RecordSetReceipt
    product_freeze_ref: ResourceRef
    photos_only_pixels_recomputed: bool

    @property
    def mode(self) -> Mode:
        return self.observation_mode

    @model_validator(mode="after")
    def scope_binding(self) -> Self:
        if (
            self.scope.observation_mode != self.observation_mode
            or self.base_receipt.binding.observation_mode != self.observation_mode
            or self.record_set_receipt.run_ref != self.scope.run_ref
            or self.record_set_receipt.scope_sha256 != digest(self.scope)
            or self.product_freeze_ref != opaque_ref("freeze", self.scope.freeze_sha256)
            or self.photos_only_pixels_recomputed != (self.observation_mode == "photos_only")
        ):
            raise ValueError("PRODUCT_MODE_BINDING_INVALID")
        return self


class ProductManifest(RegistryModel):
    schema_version: Literal["product.run.v1"] = "product.run.v1"
    source: Path
    video_pool: Path
    source_manifest_sha256: Sha256
    source_documents: dict[str, Sha256]
    product_documents: dict[str, Sha256]
    algorithms: dict[str, Sha256]
    appearance_policy: AppearanceConfig
    stitch_policy: StitchConfig
    product_config_sha256: Sha256
    modes: tuple[ProductModeReceipt, ...]
    video_manifest_sha256: Sha256 | None
    video_fps: Literal[15] = 15
    external_model_calls: Literal[False] = False
    formal_phase1_acceptance: Literal[False] = False
    manifest_sha256: Sha256

    @model_validator(mode="after")
    def declared_freeze(self) -> Self:
        if not self.source.is_absolute() or not self.video_pool.is_absolute():
            raise ValueError("LOCAL_ADMIN_LOCATOR_INVALID")
        if tuple(receipt.observation_mode for receipt in self.modes) != MODES:
            raise ValueError("PRODUCT_MODES_INVALID")
        if set(self.source_documents) != set(_SOURCE_DOCUMENTS) or (
            self.source_documents["manifest.json"] != self.source_manifest_sha256
        ):
            raise ValueError("SOURCE_DOCUMENT_BINDING_INVALID")
        if digest(self.model_dump(mode="json", exclude={"manifest_sha256"})) != (
            self.manifest_sha256
        ):
            raise ValueError("PRODUCT_MANIFEST_HASH_INVALID")
        return self


@dataclass(frozen=True)
class ProductRuntime:
    manifest: ProductManifest
    services: tuple[ProductService, ...]
    video_manifest: VideoManifest | None
    video_pool: Path
    source: Path

    def close(self) -> None:
        if self.services:
            self.services[0].repository.close()

    def __enter__(self) -> ProductRuntime:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def algorithm_hashes() -> dict[str, str]:
    """Runtime Python implementations only; no tests, HTML or debug artifacts."""
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(__file__).parent.glob("*.py"))
            if not path.name.startswith(("__", "debug", "test_"))}


def _file_bytes(root: Path, relative: str) -> bytes:
    path = root.joinpath(*safe_relative_path(relative).parts)
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ProductRunError("FROZEN_DOCUMENT_UNAVAILABLE")
    return path.read_bytes()


def _documents(root: Path, names: tuple[str, ...]) -> dict[str, str]:
    return {name: hashlib.sha256(_file_bytes(root, name)).hexdigest() for name in names}


def _save(root: Path, relative: str, value: object) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    encoded = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    path = root.joinpath(*safe_relative_path(relative).parts)
    if path.is_symlink():
        raise ProductRunError("IMMUTABLE_OUTPUT_CONFLICT")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != encoded:
            raise ProductRunError("IMMUTABLE_OUTPUT_CONFLICT")
        return
    with path.open("xb") as stream:
        stream.write(encoded)


def _exports(base: LocalPilotService) -> tuple[_ExportRecord, ...]:
    rows = []
    for raw in base.observations.values():
        observation = ObservationDetail.model_validate(raw)
        rows.append(_ExportRecord(kind="OBSERVATION", record_ref=observation.observation_ref,
                    camera_ids=observation.camera_ids, time_range=observation.time_range,
                    region_ids=observation.region_ids, payload=observation.model_dump(mode="json")))
    for raw in base.events.values():
        event = EventDetail.model_validate(raw)
        rows.append(_ExportRecord(kind="EVENT", record_ref=event.event_ref,
                    camera_ids=event.camera_ids, time_range=event.time_range,
                    region_ids=event.region_ids, payload=event.model_dump(mode="json")))
    for frame in base.frames.values():
        metadata = FrameMetadata.model_validate_json(json.dumps({
            field: getattr(frame, field) for field in FrameMetadata.model_fields
        }))
        rows.append(_ExportRecord(kind="FRAME", record_ref=frame.media_ref,
                    camera_ids=(frame.camera_id,), time_range=(frame.timestamp, frame.timestamp),
                    region_ids=(), payload=metadata.model_dump(mode="json")))
    return tuple(sorted(rows, key=lambda row: (row.kind, row.record_ref)))


def _config_hash(
    source_hash: str, appearance: AppearanceConfig, stitching: StitchConfig,
    algorithms: dict[str, str], video_hash: str | None,
) -> str:
    return digest({"source_manifest_sha256": source_hash, "appearance_policy": appearance,
                   "stitch_policy": stitching, "algorithms": algorithms,
                   "video_fps": 15, "video_manifest_sha256": video_hash})


def _freeze_hash(
    base: LocalPilotService, receipt: FreezeReceipt, *, config_hash: str,
    source_documents: dict[str, str], perception_hash: str, appearance_hash: str,
    stitch_hash: str, export_hash: str,
) -> str:
    return digest({"version": "product.mode-freeze.v1", "resource_scope": base.scope,
                   "base_receipt": receipt, "source_documents": source_documents,
                   "config_sha256": config_hash, "perception_sha256": perception_hash,
                   "appearance_sha256": appearance_hash, "stitch_sha256": stitch_hash,
                   "canonical_export_sha256": export_hash})


def _records(scope: ProductScope, rows: tuple[_ExportRecord, ...]) -> tuple[CanonicalRecord, ...]:
    return tuple(CanonicalRecord.create(run_ref=scope.run_ref, kind=row.kind,
                    record_ref=row.record_ref, camera_ids=row.camera_ids,
                    time_range=row.time_range, region_ids=row.region_ids, payload=row.payload)
                 for row in rows)


def _validate_video(manifest: VideoManifest, base: LocalPilotService, video_pool: Path) -> None:
    if manifest.scope != base.scope or manifest.registry_sha256 != base.store.registry.sha256 or (
        manifest.fps != 15
        or set(a.camera_ref for a in manifest.artifacts) != set(base.cameras)
        or len(manifest.artifacts) != len(base.cameras)
    ):
        raise ProductRunError("VIDEO_BINDING_INVALID")
    for artifact in manifest.artifacts:
        camera = base.cameras.get(artifact.camera_ref)
        frames = sorted((frame for frame in base.frames.values()
                         if frame.camera_ref == artifact.camera_ref), key=lambda f: f.timestamp)
        if camera is None or not frames:
            raise ProductRunError("VIDEO_BINDING_INVALID")
        data = _file_bytes(video_pool, artifact.relative_path)
        cache = _file_bytes(video_pool, str(Path(artifact.relative_path).with_suffix(".json")))
        input_hash = digest([(f.media_ref, f.timestamp, f.sha256) for f in frames])
        expected_ref = opaque_ref("video", *scope_parts(base.scope), camera.camera_ref,
                                 input_hash, str(float(manifest.fps)), manifest.encoder_sha256,
                                 hashlib.sha256(Path(__file__).with_name("video.py").read_bytes())
                                 .hexdigest())
        if (
            digest(json.loads(cache)) != digest(artifact)
            or artifact.video_ref != expected_ref
            or artifact.sha256 != hashlib.sha256(data).hexdigest()
            or artifact.byte_count != len(data)
            or artifact.camera_id != camera.camera_id
            or artifact.input_frames_sha256 != input_hash
            or artifact.source_frame_refs != tuple(f.media_ref for f in frames)
            or artifact.start_time != frames[0].timestamp
            or artifact.end_time != frames[-1].timestamp
            or artifact.fps != 15
            or artifact.width != frames[0].width or artifact.height != frames[0].height
            or artifact.frame_count != round((artifact.end_time - artifact.start_time) * 15) + 1
        ):
            raise ProductRunError("VIDEO_CACHE_INVALID")


def build_product(
    source: Path, output: Path, *, video_pool: Path, encode_video: bool = True,
) -> ProductManifest:
    source, output, video_pool = source.resolve(), output.resolve(), video_pool.resolve()
    if output.is_relative_to(source) or source.is_relative_to(output) or (
        video_pool.is_relative_to(source)
    ):
        raise ProductRunError("SOURCE_WRITE_SCOPE_DENIED")
    if (output / _MANIFEST_FILE).exists():
        with load_product(output) as existing:
            if existing.source != source or existing.video_pool != video_pool or (
                (existing.video_manifest is not None) != encode_video
            ):
                raise ProductRunError("IMMUTABLE_OUTPUT_CONFLICT")
            return existing.manifest
    bases = load_services(source)
    package = ResearchPackage.model_validate_json(_file_bytes(source, "package.json"))
    source_manifest = json.loads(_file_bytes(source, "manifest.json"))
    source_documents = _documents(source, _SOURCE_DOCUMENTS)
    appearance_policy, stitch_policy = AppearanceConfig(), StitchConfig()
    algorithms = algorithm_hashes()
    video = (encode_videos(bases[0].store, bases[0].scope, video_pool, fps=15.0)
             if encode_video else None)
    video_hash = None if video is None else digest(video)
    if video is not None:
        _validate_video(video, bases[0], video_pool)
        _save(output, "video_manifest.json", video)
    config_hash = _config_hash(source_documents["manifest.json"], appearance_policy,
                               stitch_policy, algorithms, video_hash)
    mode_receipts = []
    with SQLiteProductStore(output / "catalog.sqlite") as repository:
        for base in bases:
            mode = base.guard.binding.observation_mode
            frozen, _, _, base_receipt = frozen_mode(source, mode, source_manifest)
            perception = (produce_perception(package.frames, model_id=package.model_id,
                                             run_id=package.run_id)
                          if mode == "photos_only" else frozen)
            if digest(perception) != digest(frozen):
                raise ProductRunError("PIXEL_RECOMPUTATION_MISMATCH")
            descriptors = build_appearance_bundle(perception, base.store, base.scope,
                source_manifest["frame_links"],
                input_config_sha256=base_receipt.binding.config_sha256,
                config=appearance_policy)
            stitches = build_stitch_bundle(perception, descriptors, scope=base.scope,
                                             config=stitch_policy)
            rows = _exports(base)
            perception_hash, appearance_hash, stitch_hash = (
                digest(perception), digest(descriptors), digest(stitches)
            )
            export_hash = digest(rows)
            freeze_hash = _freeze_hash(base, base_receipt, config_hash=config_hash,
                source_documents=source_documents, perception_hash=perception_hash,
                appearance_hash=appearance_hash, stitch_hash=stitch_hash, export_hash=export_hash)
            binding = base_receipt.binding
            scope = ProductScope(resource_scope=base.scope, observation_mode=mode,
                dataset_sha256=binding.dataset_sha256, config_sha256=config_hash,
                producer_sha256=binding.producer_sha256, registry_sha256=binding.registry_sha256,
                media_sha256=binding.media_sha256, inference_sha256=base_receipt.inference_sha256,
                freeze_sha256=freeze_hash)
            records = _records(scope, rows)
            record_set = RecordSetReceipt.create(scope, records)
            repository.import_records(scope, records, record_set)
            mode_receipts.append(ProductModeReceipt(observation_mode=mode, scope=scope,
                base_receipt=base_receipt, perception_sha256=perception_hash,
                appearance_sha256=appearance_hash, stitch_sha256=stitch_hash,
                canonical_export_sha256=export_hash, record_set_receipt=record_set,
                product_freeze_ref=opaque_ref("freeze", freeze_hash),
                photos_only_pixels_recomputed=mode == "photos_only"))
            _save(output, f"appearance_{mode}.json", descriptors)
            _save(output, f"stitch_{mode}.json", stitches)
            _save(output, f"record_set_{mode}.json", record_set)
    document_names = tuple(f"{prefix}_{mode}.json" for mode in MODES
                           for prefix in ("appearance", "stitch", "record_set"))
    if video is not None:
        document_names += ("video_manifest.json",)
    values: dict[str, object] = {"schema_version": "product.run.v1", "source": str(source),
              "video_pool": str(video_pool), "source_manifest_sha256": source_documents[
                  "manifest.json"], "source_documents": source_documents,
              "product_documents": _documents(output, document_names), "algorithms": algorithms,
              "appearance_policy": appearance_policy.model_dump(mode="json"),
              "stitch_policy": stitch_policy.model_dump(mode="json"),
              "product_config_sha256": config_hash,
              "modes": [receipt.model_dump(mode="json") for receipt in mode_receipts],
              "video_manifest_sha256": video_hash}
    # Defaults are serialized before hashing so the complete manifest is self-bound.
    values.update({"video_fps": 15, "external_model_calls": False,
                   "formal_phase1_acceptance": False})
    manifest = ProductManifest.model_validate_json(json.dumps(values | {
        "manifest_sha256": digest(values)
    }))
    _save(output, _MANIFEST_FILE, manifest)
    return manifest


def load_product(output: Path) -> ProductRuntime:
    output = output.resolve()
    repository: SQLiteProductStore | None = None
    try:
        manifest = ProductManifest.model_validate_json(_file_bytes(output, _MANIFEST_FILE))
        if manifest.algorithms != algorithm_hashes():
            raise ProductRunError("PRODUCT_IMPLEMENTATION_MISMATCH")
        source = manifest.source.resolve()
        if _documents(source, _SOURCE_DOCUMENTS) != manifest.source_documents:
            raise ProductRunError("SOURCE_DOCUMENT_MISMATCH")
        bases = load_services(source)
        source_manifest = json.loads(_file_bytes(source, "manifest.json"))
        expected_names = tuple(f"{prefix}_{mode}.json" for mode in MODES
                               for prefix in ("appearance", "stitch", "record_set"))
        if manifest.video_manifest_sha256 is not None:
            expected_names += ("video_manifest.json",)
        if set(manifest.product_documents) != set(expected_names) or (
            _documents(output, expected_names) != manifest.product_documents
        ):
            raise ProductRunError("PRODUCT_DOCUMENT_MISMATCH")
        video = (VideoManifest.model_validate_json(_file_bytes(output, "video_manifest.json"))
                 if manifest.video_manifest_sha256 is not None else None)
        if video is not None:
            if digest(video) != manifest.video_manifest_sha256:
                raise ProductRunError("VIDEO_BINDING_INVALID")
            _validate_video(video, bases[0], manifest.video_pool)
        if _config_hash(manifest.source_manifest_sha256, manifest.appearance_policy,
                        manifest.stitch_policy, manifest.algorithms,
                        manifest.video_manifest_sha256) != manifest.product_config_sha256:
            raise ProductRunError("PRODUCT_CONFIG_MISMATCH")
        if not (output / "catalog.sqlite").is_file() or (output / "catalog.sqlite").is_symlink():
            raise ProductRunError("PRODUCT_CATALOG_UNAVAILABLE")
        repository = SQLiteProductStore(output / "catalog.sqlite")
        services = []
        for base, saved in zip(bases, manifest.modes, strict=True):
            mode = base.guard.binding.observation_mode
            perception, _, _, base_receipt = frozen_mode(source, mode, source_manifest)
            descriptors = DescriptorBundle.model_validate_json(_file_bytes(output,
                                                        f"appearance_{mode}.json"))
            stitches = StitchBundle.model_validate_json(_file_bytes(output, f"stitch_{mode}.json"))
            rows = _exports(base)
            if (
                saved.observation_mode != mode or saved.base_receipt != base_receipt
                or saved.scope.resource_scope != base.scope
                or saved.scope.dataset_sha256 != base_receipt.binding.dataset_sha256
                or saved.scope.config_sha256 != manifest.product_config_sha256
                or saved.scope.producer_sha256 != base_receipt.binding.producer_sha256
                or saved.scope.registry_sha256 != base_receipt.binding.registry_sha256
                or saved.scope.media_sha256 != base_receipt.binding.media_sha256
                or saved.scope.inference_sha256 != base_receipt.inference_sha256
                or digest(perception) != saved.perception_sha256
                or digest(descriptors) != saved.appearance_sha256
                or digest(stitches) != saved.stitch_sha256
                or descriptors.scope != base.scope or stitches.scope != base.scope
                or descriptors.config != manifest.appearance_policy
                or stitches.config != manifest.stitch_policy
                or descriptors.perception_sha256 != saved.perception_sha256
                or stitches.perception_sha256 != saved.perception_sha256
                or stitches.appearance_sha256 != saved.appearance_sha256
                or descriptors.input_config_sha256 != base_receipt.binding.config_sha256
                or descriptors.algorithm_sha256 != manifest.algorithms["appearance.py"]
                or stitches.algorithm_sha256 != manifest.algorithms["stitching.py"]
                or digest(rows) != saved.canonical_export_sha256
                or _freeze_hash(base, base_receipt, config_hash=manifest.product_config_sha256,
                    source_documents=manifest.source_documents,
                    perception_hash=saved.perception_sha256,
                    appearance_hash=saved.appearance_sha256,
                    stitch_hash=saved.stitch_sha256, export_hash=saved.canonical_export_sha256)
                != saved.scope.freeze_sha256
            ):
                raise ProductRunError("PRODUCT_MODE_FREEZE_MISMATCH")
            expected_set = RecordSetReceipt.create(saved.scope, _records(saved.scope, rows))
            if expected_set != saved.record_set_receipt or expected_set != (
                RecordSetReceipt.model_validate_json(_file_bytes(output, f"record_set_{mode}.json"))
            ) or repository.get_scope(saved.scope.run_ref) != saved.scope or (
                repository.verify_run(saved.scope.run_ref) != expected_set
            ):
                raise ProductRunError("PRODUCT_RECORD_SET_MISMATCH")
            services.append(ProductService(base, repository, saved.scope, descriptors,
                product_freeze_ref=saved.product_freeze_ref,
                stitches=stitches.model_dump(mode="json")))
        if {scope.run_ref for scope in repository.list_runs()} != {
            saved.scope.run_ref for saved in manifest.modes
        }:
            raise ProductRunError("PRODUCT_CATALOG_SCOPE_MISMATCH")
        return ProductRuntime(manifest, tuple(services), video, manifest.video_pool, source)
    except (ValueError, OSError, KeyError, TypeError):
        if repository is not None:
            repository.close()
        raise ProductRunError("PRODUCT_FROZEN_INPUT_INVALID") from None
