import pytest
from pydantic import ValidationError

from amidst.product.contracts import PixelObservation


def pixels() -> dict[str, object]:
    return {
        "observation_ref": "observation:" + "a" * 24,
        "local_track_ref": "track:" + "b" * 24,
        "camera_refs": ["camera:" + "c" * 24], "camera_ids": ["A"],
        "time_range": [0, 1], "media_refs": ["media:" + "d" * 24],
        "measurements": [{"frame_ref": "media:" + "d" * 24, "timestamp": 0,
                          "bbox": [0, 0, 2, 2], "point_2d": [1, 2],
                          "visible_features": [0.2, 0.3, 0.4]}],
        "origin": "SYNTHETIC", "image_measurement": True,
        "authority": "RGB_PIXELS_WITH_SYNTHETIC_CONFIG", "uncertainty": "merged pixels",
    }


def test_pixel_input_dto_never_acquires_geometry_defaults() -> None:
    actual = PixelObservation.model_validate(pixels()).model_dump(mode="json")
    assert "region_ids" not in actual and "projected_path" not in actual


@pytest.mark.parametrize("extra", ["region_ids", "projected_path", "private_path", "gt"])
def test_strict_pixel_allowlist(extra: str) -> None:
    with pytest.raises(ValidationError):
        PixelObservation.model_validate(pixels() | {extra: "secret"})


def test_nested_response_extra_is_denied() -> None:
    value = pixels()
    value["measurements"] = [{"frame_ref": "media:" + "d" * 24, "timestamp": 0,
                              "bbox": [0, 0, 2, 2], "point_2d": [1, 2],
                              "visible_features": [0.2], "actor_identity": "secret"}]
    with pytest.raises(ValidationError):
        PixelObservation.model_validate(value)
