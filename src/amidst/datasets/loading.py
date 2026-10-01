"""Content-bound dataset input loading; no evaluation-reference files are opened."""

from pathlib import Path

from amidst.datasets.providers import BlenderDataset, JsonFrameDataset, MockDataset
from amidst.domain.calibration import CameraCalibrationCatalog
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.experiment import DatasetCase, DatasetManifest
from amidst.domain.pipeline import PipelineConfig
from amidst.domain.stream import StreamBinding
from amidst.experiments.versioning import read_reference
from amidst.geometry.calibration import validate_camera_calibration_catalog
from amidst.observation.aggregation import validate_stream_model


def load_case_calibration(
    dataset: DatasetManifest,
    case: DatasetCase,
    manifest_path: Path,
) -> CameraCalibrationCatalog | None:
    """Verify every declared calibration artifact before presenting it as a binding."""
    dataset = validate_stream_model(dataset, DatasetManifest)
    case = validate_stream_model(case, DatasetCase)
    if case not in dataset.cases:
        raise ValueError("dataset case must belong to the selected manifest")
    if case.camera_calibration is None:
        return None
    catalog = validate_camera_calibration_catalog(
        CameraCalibrationCatalog.model_validate_json(
            read_reference(case.camera_calibration, manifest_path)
        )
    )
    if catalog.source_asset_sha256 != case.source_asset_sha256:
        raise ValueError("camera calibration and dataset source asset SHA-256 must match")
    if catalog.camera_config_version != dataset.camera_config_version:
        raise ValueError("camera calibration version must match the dataset manifest")
    return catalog


def load_dataset_case(
    dataset: DatasetManifest,
    case: DatasetCase,
    manifest_path: Path,
) -> tuple[JsonFrameDataset, PipelineConfig]:
    dataset = validate_stream_model(dataset, DatasetManifest)
    case = validate_stream_model(case, DatasetCase)
    if case not in dataset.cases:
        raise ValueError("dataset case must belong to the selected manifest")
    pipeline = PipelineConfig.model_validate_json(read_reference(case.pipeline, manifest_path))
    if (
        pipeline.navigation.spatial_context_id != case.spatial_context_id
        or pipeline.topology.spatial_context_id != case.spatial_context_id
        or pipeline.navigation.source_asset_sha256 != case.source_asset_sha256
        or pipeline.topology.source_asset_sha256 != case.source_asset_sha256
    ):
        raise ValueError("dataset manifest and pipeline source/context must match")
    frames = FrameSampleDataset.model_validate_json(read_reference(case.frames, manifest_path))
    calibration = load_case_calibration(dataset, case, manifest_path)
    if calibration is not None:
        calibrated_ids = {item.camera.camera_id for item in calibration.cameras}
        required_ids = {sample.camera_id for sample in frames.samples} | {
            node.camera_id for node in pipeline.topology.nodes
        }
        if not required_ids <= calibrated_ids:
            raise ValueError("all frame and topology cameras must exist in the calibration catalog")
    binding = StreamBinding(
        source_id=case.source_id,
        spatial_context_id=case.spatial_context_id,
        source_asset_sha256=case.source_asset_sha256,
    )
    provider_class = MockDataset if dataset.provider_kind == "MOCK_JSON" else BlenderDataset
    return provider_class(frames, binding), pipeline
