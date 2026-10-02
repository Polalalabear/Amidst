"""Floor labels cannot create vertical connectivity or a disguised WALK edge."""

import pytest
from pydantic import ValidationError

from amidst.domain.trajectory import TerminationReason

from .graph_cases import graph_case_spec, infer_graph_case, load_graph_case


def test_cross_floor_endpoints_without_stairs_fail_closed() -> None:
    inputs = load_graph_case("missing_stair_connection")
    assert inputs.start_observation.floor_id == "1F"
    assert inputs.end_observation.floor_id == "2F"
    assert inputs.navigation.edges == inputs.topology.transitions == ()
    result, event = infer_graph_case("missing_stair_connection")
    assert result.termination_reason == event.termination_reason == (
        TerminationReason.NO_FEASIBLE_PATH
    )
    assert result.complete and not result.candidates and not event.trajectories
    assert result.rejection_reasons == ("NO_FEASIBLE_AUTHORIZED_ROUTE",)


def test_vertical_walk_edge_is_rejected_by_existing_schema() -> None:
    expected = graph_case_spec("vertical_walk_forgery")["expected"]
    with pytest.raises(ValidationError, match=expected["error_message"]):
        load_graph_case("vertical_walk_forgery")
