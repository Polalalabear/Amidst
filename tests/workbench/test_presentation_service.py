"""Source display routes stay human-research-only and reference-bound."""
import pytest

from amidst.workbench.reviews import ReviewStore
from amidst.workbench.service import Denied, Workbench


def make(tmp_path, provider=None):
    reviews = ReviewStore(tmp_path / "review.db", {})
    return Workbench({}, reviews, presentation=provider,
                     presentation_media=lambda ref: ("image/png", b"pixels")
                     if ref == "frame-public" else (_ for _ in ()).throw(ValueError("private")))


def fixture_presentation():
    return {"presentation_ref": "source-public", "label": "Source display",
            "binding": {"run_ref": "fixed-run", "units": "METRES"}, "origin": "SYNTHETIC",
            "image_measurement": False, "authority": "DIAGNOSTIC", "meshes": [],
            "frames": [{"timestamp": 0, "world_position": [0, 0, 0]}]}


def test_research_reads_fixed_source_and_rejects_unknown_reference(tmp_path):
    workbench = make(tmp_path, fixture_presentation)
    token = workbench.session({"role": "research"})["session_ref"]
    assert "meshes" not in workbench.call("presentations", {"session_ref": token})["items"][0]
    assert workbench.call("presentation", {"session_ref": token,
        "presentation_ref": "source-public"})["presentation"]["frames"]
    with pytest.raises(Denied, match="REFERENCE_DENIED"):
        workbench.call("presentation", {"session_ref": token, "presentation_ref": "unknown"})
    assert workbench.presentation_media(token, "frame-public")[1] == b"pixels"
    with pytest.raises(ValueError):
        workbench.presentation_media(token, "unknown")


@pytest.mark.parametrize("action,fields", [("presentations", {}),
    ("presentation", {"presentation_ref": "source-public"})])
def test_management_cannot_read_source_display(tmp_path, action, fields):
    workbench = make(tmp_path, fixture_presentation)
    token = workbench.session({"role": "management"})["session_ref"]
    with pytest.raises(Denied, match="ROLE_DENIED"):
        workbench.call(action, {"session_ref": token, **fields})
    with pytest.raises(Denied, match="ROLE_DENIED"):
        workbench.presentation_media(token, "frame-public")


def test_missing_or_unverified_source_stays_unavailable(tmp_path):
    workbench = make(tmp_path)
    token = workbench.session({"role": "research"})["session_ref"]
    assert workbench.call("presentations", {"session_ref": token})["status"] == "UNAVAILABLE"
    workbench.presentation_provider = lambda: (_ for _ in ()).throw(ValueError("private path"))
    result = workbench.call("presentations", {"session_ref": token})
    assert result["status"] == "UNAVAILABLE" and "private" not in str(result)
