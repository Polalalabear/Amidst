"""Composition root reuses mock providers and unchanged gap reconstruction."""

from collections.abc import Callable
from pathlib import Path
from time import monotonic

from amidst.datasets.loading import load_dataset_case
from amidst.domain.experiment import DatasetManifest
from amidst.domain.interfaces import ObservationProvider
from amidst.domain.stream import BoundGapEvent, BoundObservation
from amidst.events import reconstruct_gaps
from amidst.experiments.versioning import read_reference, resolve_reference
from amidst.integration.config import load_service_config
from amidst.integration.local_repository import InMemoryRepository, LocalJsonRepository
from amidst.integration.replay import load_benchmark_snapshot
from amidst.integration.repositories import IntegrationRepository, RepositorySnapshot
from amidst.integration.service import MockIntegrationService
from amidst.portability.paths import resolve_local_path


def build_mock_service(
    config_path: Path, *, search_clock: Callable[[], float] = monotonic,
) -> MockIntegrationService:
    """Build once; API reads do not rerun inference or open evaluation references."""
    config_path = resolve_local_path(config_path, base=Path.cwd())
    config = load_service_config(config_path)
    if config.repository_kind == "POSTGRESQL":
        raise NotImplementedError("PostgreSQL is an interface only in Integration Foundation")
    manifest_path = resolve_reference(config.dataset_manifest, config_path)
    dataset = DatasetManifest.model_validate_json(read_reference(
        config.dataset_manifest, config_path,
    ))
    if dataset.provider_kind != config.provider_kind:
        raise ValueError("Integration Foundation requires the existing MOCK_JSON dataset")

    # This is the same Phase 1 orchestration; no new search/ranking/reconstruction behavior.
    observations: list[BoundObservation] = []
    gaps: list[BoundGapEvent] = []
    providers: dict[str, ObservationProvider] = {}
    for case in dataset.cases:
        provider, pipeline = load_dataset_case(dataset, case, manifest_path)
        providers[case.case_id] = provider
        aggregation = provider.aggregate(provider.time_range, config.aggregation_policy)
        observations.extend(aggregation.observations)
        gaps.extend(reconstruct_gaps(
            aggregation, pipeline, dataset_id=case.case_id, random_seed=dataset.seed,
            clock=search_clock,
        ))
    snapshot = RepositorySnapshot(observations=tuple(observations), gaps=tuple(gaps))
    repository: IntegrationRepository
    if config.repository_kind == "LOCAL_JSON":
        assert config.repository_path is not None
        store = resolve_local_path(config.repository_path, base=config_path.parent)
        # Never write over any declared input, including evaluation-only references.
        protected = {config_path, manifest_path}
        for case in dataset.cases:
            references = (case.pipeline, case.frames, case.camera_calibration, case.constraints)
            protected.update(resolve_reference(ref, manifest_path)
                             for ref in references if ref is not None)
            protected.update(resolve_reference(ref, manifest_path)
                             for ref in case.evaluation_references)
        if store in protected:
            raise ValueError("repository_path must not replace a dataset or service input")
        repository = LocalJsonRepository(store)
    else:
        repository = InMemoryRepository()
    repository.add(snapshot)
    return MockIntegrationService(repository, providers)


def build_replay_service(output_directory: Path) -> MockIntegrationService:
    """Read existing completed benchmark/replay artifacts without invoking the runner."""
    return MockIntegrationService(InMemoryRepository(load_benchmark_snapshot(output_directory)))
