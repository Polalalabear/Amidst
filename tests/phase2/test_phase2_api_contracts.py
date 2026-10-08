"""Backend envelopes preserve strict Phase 1 schemas and explicit synthetic time."""

import pytest
from pydantic import ValidationError

from amidst.integration.contracts import IntegrationMetadata, ObservationPage, RecordQuery


@pytest.mark.parametrize("time_range", [(3, 2), (-1, 2), (0, float("nan")), (True, 2)])
def test_query_rejects_invalid_time_ranges(time_range: tuple[float, float]) -> None:
    with pytest.raises(ValidationError):
        RecordQuery(time_range=time_range)


def test_point_query_and_json_schema_keep_synthetic_inclusive_contract() -> None:
    query = RecordQuery(time_range=(2, 2), camera_id="MOCK_CAMERA")
    page = ObservationPage(query=query, items=())
    assert ObservationPage.model_validate_json(page.model_dump_json()) == page
    assert page.metadata == IntegrationMetadata()
    assert page.metadata.time_interval == "CLOSED"
    assert page.metadata.time_basis == "CONFIGURED_SECONDS"
    assert ObservationPage.model_json_schema()["additionalProperties"] is False


def test_query_and_metadata_reject_production_or_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RecordQuery.model_validate({"time_range": [0, 1], "utc": True})
    with pytest.raises(ValidationError):
        IntegrationMetadata.model_validate({"data_kind": "REAL_CV"})
