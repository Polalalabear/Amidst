"""Verify additive storage preserves canonical evidence and rejects partial writes."""

from pathlib import Path

import pytest

from amidst.datasets.loading import load_dataset_case
from amidst.domain.observation import Observation
from amidst.domain.stream import BoundGapEvent, BoundObservation
from amidst.events import reconstruct_gaps
from amidst.experiments.versioning import load_experiment
from amidst.integration.local_repository import InMemoryRepository, LocalJsonRepository
from amidst.integration.repositories import (
    IntegrationRepository,
    PostgreSQLRepositorySettings,
    RepositoryConflictError,
    RepositorySnapshot,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def snapshot() -> RepositorySnapshot:
    config, dataset, manifest = load_experiment(ROOT / "configs/benchmarks/mock_stream_v1.json")
    case = dataset.cases[0]
    provider, pipeline = load_dataset_case(dataset, case, manifest)
    aggregation = provider.aggregate(provider.time_range, config.aggregation_policy)
    gaps = reconstruct_gaps(
        aggregation, pipeline, dataset_id=case.case_id, random_seed=config.seed,
        clock=lambda: 0.0,
    )
    return RepositorySnapshot(observations=aggregation.observations, gaps=gaps)


def _changed_observation(original: BoundObservation) -> BoundObservation:
    payload = original.model_dump(mode="python")
    payload["observation"]["zone_id"] = "CHANGED_SYNTHETIC_ZONE"
    return BoundObservation.model_validate(payload)


def _additional_observation(original: BoundObservation) -> BoundObservation:
    payload = original.observation.model_dump(mode="python")
    payload["observation_id"] = "additional-synthetic-observation"
    for point in payload["projected_path"]:
        point["observation_id"] = payload["observation_id"]
    return BoundObservation(
        binding=original.binding,
        observation=Observation.model_validate(payload),
        sample_ids=("additional-synthetic-sample",),
    )


@pytest.mark.parametrize("kind", ["memory", "json"])
def test_repository_roundtrip_is_exact_and_duplicates_are_idempotent(
    tmp_path: Path, snapshot: RepositorySnapshot, kind: str,
) -> None:
    repository: IntegrationRepository = (
        InMemoryRepository() if kind == "memory" else LocalJsonRepository(tmp_path / "store.json")
    )
    assert repository.snapshot() == RepositorySnapshot()
    repository.add(snapshot)
    first = repository.snapshot()
    repository.add(snapshot)
    assert repository.snapshot() == first == snapshot
    assert first.gaps[0].event.candidates == snapshot.gaps[0].search_result.candidates
    assert first.gaps[0].event.trajectories == snapshot.gaps[0].event.trajectories
    assert all(candidate.path_score is None for candidate in first.gaps[0].event.candidates)
    assert first.model_dump(mode="json") == snapshot.model_dump(mode="json")
    if kind == "json":
        reopened = LocalJsonRepository(tmp_path / "store.json")
        assert reopened.snapshot() == snapshot
        before = (tmp_path / "store.json").stat().st_ino
        reopened.add(snapshot)
        assert (tmp_path / "store.json").stat().st_ino == before


@pytest.mark.parametrize("kind", ["memory", "json"])
def test_observation_conflict_rejects_entire_merge_before_publication(
    tmp_path: Path, snapshot: RepositorySnapshot, kind: str,
) -> None:
    repository: IntegrationRepository = (
        InMemoryRepository(snapshot) if kind == "memory"
        else LocalJsonRepository(tmp_path / "store.json", snapshot)
    )
    incoming = RepositorySnapshot(observations=(
        _additional_observation(snapshot.observations[0]),
        _changed_observation(snapshot.observations[0]),
    ))
    before = (tmp_path / "store.json").read_bytes() if kind == "json" else None
    with pytest.raises(RepositoryConflictError, match="conflicting observation"):
        repository.add(incoming)
    assert repository.snapshot() == snapshot
    if before is not None:
        assert (tmp_path / "store.json").read_bytes() == before


@pytest.mark.parametrize("kind", ["memory", "json"])
def test_event_conflict_preserves_original_search_and_event(
    tmp_path: Path, snapshot: RepositorySnapshot, kind: str,
) -> None:
    repository: IntegrationRepository = (
        InMemoryRepository(snapshot) if kind == "memory"
        else LocalJsonRepository(tmp_path / "store.json", snapshot)
    )
    payload = snapshot.gaps[0].model_dump(mode="python")
    payload["event"]["termination_reason"] = "MAX_PATHS_REACHED"
    payload["search_result"].update(termination_reason="MAX_PATHS_REACHED", complete=False)
    changed = BoundGapEvent.model_validate(payload)
    incoming = RepositorySnapshot(observations=snapshot.observations, gaps=(changed,))
    with pytest.raises(RepositoryConflictError, match="conflicting event"):
        repository.add(incoming)
    assert repository.snapshot() == snapshot


def test_snapshot_requires_unique_ids_and_exact_present_endpoints(
    snapshot: RepositorySnapshot,
) -> None:
    with pytest.raises(ValueError, match="observation identities must be unique"):
        RepositorySnapshot(observations=snapshot.observations * 2)
    with pytest.raises(ValueError, match="event identities must be unique"):
        RepositorySnapshot(observations=snapshot.observations, gaps=snapshot.gaps * 2)
    with pytest.raises(ValueError, match="endpoints must exactly match"):
        RepositorySnapshot(gaps=snapshot.gaps)
    observations = (
        _changed_observation(snapshot.observations[0]), *snapshot.observations[1:],
    )
    with pytest.raises(ValueError, match="endpoints must exactly match"):
        RepositorySnapshot(observations=observations, gaps=snapshot.gaps)


def test_snapshot_rejects_real_binding_and_unchecked_schema_bypass(
    snapshot: RepositorySnapshot,
) -> None:
    original = snapshot.observations[0]
    real = original.model_copy(update={
        "binding": original.binding.model_copy(update={"data_kind": "REAL_CV"}),
    })
    with pytest.raises(ValueError, match="only SYNTHETIC"):
        RepositorySnapshot(observations=(real,))
    repository = InMemoryRepository(snapshot)
    malformed = RepositorySnapshot.model_construct(observations=(real,), gaps=())
    with pytest.raises(ValueError):
        repository.add(malformed)
    assert repository.snapshot() == snapshot
    with pytest.raises(ValueError):
        RepositorySnapshot.model_validate({"schema_version": "phase1", "unknown": True})


def test_local_store_reads_current_disk_and_can_merge_new_records(
    tmp_path: Path, snapshot: RepositorySnapshot,
) -> None:
    path = tmp_path / "store.json"
    reader = LocalJsonRepository(path)
    writer = LocalJsonRepository(path, snapshot)
    assert reader.snapshot() == snapshot
    additional = _additional_observation(snapshot.observations[0])
    writer.add(RepositorySnapshot(observations=(additional,)))
    assert reader.snapshot().observations == (*snapshot.observations, additional)
    assert reader.snapshot().gaps == snapshot.gaps


def test_local_store_never_replaces_invalid_existing_contents(
    tmp_path: Path, snapshot: RepositorySnapshot,
) -> None:
    path = tmp_path / "store.json"
    invalid = b'{"schema_version":"phase1-benchmark", "data":"preserve"}\n'
    path.write_bytes(invalid)
    with pytest.raises(ValueError):
        LocalJsonRepository(path, snapshot)
    assert path.read_bytes() == invalid
    path.unlink()
    repository = LocalJsonRepository(path, snapshot)
    path.write_bytes(invalid)
    with pytest.raises(ValueError):
        repository.snapshot()
    with pytest.raises(ValueError):
        repository.add(snapshot)
    assert path.read_bytes() == invalid


def test_local_store_rejects_non_json_destination(tmp_path: Path) -> None:
    path = tmp_path / "source.blend"
    with pytest.raises(ValueError, match="JSON file"):
        LocalJsonRepository(path)
    assert not path.exists()


def test_postgresql_settings_keep_dsn_secret_without_opening_a_database() -> None:
    dsn = "postgresql://synthetic-user:synthetic-password@localhost/future-interface"
    settings = PostgreSQLRepositorySettings(dsn=dsn)
    assert settings.dsn.get_secret_value() == dsn
    assert "synthetic-password" not in repr(settings)
    assert "synthetic-password" not in settings.model_dump_json()
    with pytest.raises(ValueError):
        PostgreSQLRepositorySettings(dsn="")
