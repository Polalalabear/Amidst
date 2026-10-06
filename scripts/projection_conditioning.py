"""GT-free numeric and geometry diagnostics around unchanged inverse projection.

All coordinates/distances use native scene units. These controls are PILOT /
SYNTHETIC SAMPLE diagnostics with PROVISIONAL physical authority; perturbations
are immutable model copies and never rewrite Blender calibration or geometry.
"""

from __future__ import annotations

import math
from decimal import Decimal, localcontext
from typing import Any

import numpy as np

from amidst.domain.camera import Camera
from amidst.domain.common import Provenance
from amidst.domain.evidence import ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.geometry.inverse_projection import InverseProjectionError, InverseProjectionService
from amidst.simulation.virtual_camera import project_world

LABEL = "PILOT / SYNTHETIC SAMPLE"


def _reject_hidden_fields(model: Any, expected: type) -> None:
    if (
        type(model) is not expected
        or set(model.__dict__) - set(expected.model_fields)
        or model.model_extra
    ):
        raise ValueError(
            f"diagnostics require the exact {expected.__name__} contract without hidden fields"
        )


def _metadata() -> dict[str, Any]:
    return {
        "label": LABEL,
        "data_kind": "SYNTHETIC",
        "physical_validity": "PROVISIONAL",
        "coordinate_units": "BLENDER_SCENE_UNITS",
        "scale_authority": "UNVERIFIED",
        "ground_truth_used": False,
        "source_camera_or_plane_modified": False,
    }


def _ray_arrays(camera: Camera, plane: Plane, frame: ObservationFrame, dtype: Any = np.float64):
    u, v = frame.point_2d
    matrix = np.asarray(camera.camera_to_world, dtype=dtype)
    fx, fy, cx, cy = [dtype(x) for x in (camera.fx, camera.fy, camera.cx, camera.cy)]
    local = np.asarray(((dtype(u) - cx) / fx, (cy - dtype(v)) / fy, -1), dtype=dtype)
    origin, rotation = matrix[:3, 3], matrix[:3, :3]
    direction = rotation @ local
    normal, plane_point = (
        np.asarray(plane.normal, dtype=dtype),
        np.asarray(plane.point, dtype=dtype),
    )
    denominator = normal @ direction
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        depth = (normal @ (plane_point - origin)) / denominator
        point = origin + depth * direction
    return origin, rotation, direction, normal, denominator, depth, point


def decimal_reference(camera: Camera, plane: Plane, frame: ObservationFrame) -> dict[str, Any]:
    """Independent 60-digit scalar closed form on the exact binary64 input values."""
    if frame.point_2d is None:
        raise ValueError("Decimal reference requires observed pixel coordinates")
    with localcontext() as decimal_context:
        decimal_context.prec = 60

        def dec(value: float) -> Decimal:
            return Decimal.from_float(float(value))

        u, v = [dec(x) for x in frame.point_2d]
        fx, fy, cx, cy = [dec(x) for x in (camera.fx, camera.fy, camera.cx, camera.cy)]
        local = ((u - cx) / fx, (cy - v) / fy, Decimal(-1))
        matrix = [[dec(value) for value in row] for row in camera.camera_to_world]
        direction = [
            sum((matrix[row][column] * local[column] for column in range(3)), Decimal(0))
            for row in range(3)
        ]
        origin = [matrix[row][3] for row in range(3)]
        normal, plane_point = [dec(x) for x in plane.normal], [dec(x) for x in plane.point]
        denominator = sum((normal[i] * direction[i] for i in range(3)), Decimal(0))
        if denominator == 0:
            return {
                "status": "PARALLEL",
                "precision_decimal_digits": 60,
                "point_scene_units": None,
                "point_decimal_strings": None,
            }
        numerator = sum((normal[i] * (plane_point[i] - origin[i]) for i in range(3)), Decimal(0))
        depth = numerator / denominator
        point = [origin[i] + depth * direction[i] for i in range(3)]
        return {
            "status": "COMPUTED",
            "precision_decimal_digits": 60,
            "input_conversion": "EXACT_BINARY64_VALUES_DECIMAL_FROM_FLOAT",
            "point_decimal_strings": [str(x) for x in point],
            "point_scene_units": [float(x) for x in point],
            "axial_depth_decimal_string": str(depth),
        }


def _central_jacobian(
    camera: Camera, plane: Plane, frame: ObservationFrame, step: float
) -> dict[str, Any]:
    service = InverseProjectionService(camera, plane)
    columns = []
    failures = []
    for axis in range(2):
        points = []
        for sign in (-1, 1):
            pixel = list(frame.point_2d)
            pixel[axis] += sign * step
            perturbed = ObservationFrame.model_validate(frame.model_dump() | {"point_2d": pixel})
            try:
                points.append(np.asarray(service.project_frame(perturbed).world_position))
            except InverseProjectionError as error:
                failures.append({"axis": axis, "sign": sign, "failure": error.failure.value})
        if len(points) == 2:
            columns.append((points[1] - points[0]) / (2 * step))
    if failures:
        return {
            "status": "UNAVAILABLE_AT_SERVICE_CONTRACT_BOUNDARY",
            "step_pixels": step,
            "failures": failures,
            "jacobian_scene_units_per_pixel": None,
        }
    return {
        "status": "COMPUTED",
        "step_pixels": step,
        "jacobian_scene_units_per_pixel": np.column_stack(columns).tolist(),
        "failures": [],
    }


def diagnose_projection(
    camera: Camera,
    plane: Plane,
    frame: ObservationFrame,
    *,
    pixel_step: float = 0.001,
) -> dict[str, Any]:
    """Diagnose one service input; never substitute coordinates for a rejected frame."""
    _reject_hidden_fields(camera, Camera)
    _reject_hidden_fields(plane, Plane)
    _reject_hidden_fields(frame, ObservationFrame)
    if isinstance(pixel_step, bool) or not math.isfinite(pixel_step) or pixel_step <= 0:
        raise ValueError("central difference pixel step must be finite positive")
    report = _metadata() | {
        "camera_id": camera.camera_id,
        "plane_id": plane.plane_id,
        "frame_id": frame.frame_id,
        "timestamp": frame.timestamp,
        "pixel": frame.point_2d,
    }
    try:
        baseline = InverseProjectionService(camera, plane).project_frame(frame)
    except InverseProjectionError as error:
        return report | {
            "status": "REJECTED",
            "failure": error.failure.value,
            "failure_message": str(error),
            "baseline_projected_point": None,
            "jacobian": None,
            "high_precision": None,
            "roundtrip": None,
        }
    origin, rotation, ray, normal, denominator, depth, closed_point = _ray_arrays(
        camera, plane, frame
    )
    ray_length = float(np.linalg.norm(ray))
    unit_ray, unit_normal = ray / ray_length, normal / np.linalg.norm(normal)
    incidence = min(1.0, abs(float(unit_normal @ unit_ray)))
    normal_angle = math.degrees(math.acos(incidence))
    optical = -(rotation[:, 2]) / np.linalg.norm(rotation[:, 2])
    off_axis = math.degrees(math.acos(float(np.clip(optical @ unit_ray, -1, 1))))
    derivative = rotation @ np.asarray(((1 / camera.fx, 0), (0, -1 / camera.fy), (0, 0)))
    jacobian = depth * (derivative - np.outer(ray, normal @ derivative) / denominator)
    singular = np.linalg.svd(jacobian, compute_uv=False)
    central = _central_jacobian(camera, plane, frame, pixel_step)
    difference = None
    relative = None
    if central["status"] == "COMPUTED":
        difference = float(
            np.linalg.norm(np.asarray(central["jacobian_scene_units_per_pixel"]) - jacobian)
        )
        relative = difference / max(float(np.linalg.norm(jacobian)), 1e-30)
    reference = decimal_reference(camera, plane, frame)
    point = np.asarray(baseline.world_position)
    reference_point = np.asarray(reference["point_scene_units"])
    try:
        with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
            *_, float32_point = _ray_arrays(camera, plane, frame, np.float32)
        finite32 = bool(np.isfinite(float32_point).all())
        float32 = {
            "status": "COMPUTED" if finite32 else "NUMERICAL_FAILURE",
            "point_scene_units": float32_point.astype(float).tolist() if finite32 else None,
            "difference_from_service_scene_units": float(np.linalg.norm(float32_point - point))
            if finite32
            else None,
        }
    except (ValueError, OverflowError, FloatingPointError):
        float32 = {
            "status": "NUMERICAL_FAILURE",
            "point_scene_units": None,
            "difference_from_service_scene_units": None,
        }
    # This point comes exclusively from accepted 2D evidence; no GT point is used.
    forward = project_world(camera, baseline.world_position)
    recovered = None
    pixel_error = None
    if forward.point_2d is not None and forward.in_frustum:
        pixel_error = math.dist(frame.point_2d, forward.point_2d)
        try:
            recovered_frame = ObservationFrame.model_validate(
                frame.model_dump() | {"point_2d": forward.point_2d}
            )
            recovered = InverseProjectionService(camera, plane).project_frame(recovered_frame)
        except InverseProjectionError:
            pass
    return report | {
        "status": "ACCEPTED",
        "failure": None,
        "baseline_projected_point": baseline.model_dump(mode="json"),
        "geometry": {
            "camera_position_scene_units": origin.tolist(),
            "camera_point_euclidean_distance_scene_units": float(np.linalg.norm(point - origin)),
            "intersection_euclidean_distance_scene_units": float(depth * ray_length),
            "intersection_axial_depth_scene_units": float(depth),
            "forward_axial_depth_scene_units": forward.axial_depth,
            "optical_off_axis_ray_angle_degrees": off_axis,
            "acute_ray_normal_angle_degrees": normal_angle,
            "grazing_angle_degrees": 90 - normal_angle,
            "normalized_incidence": incidence,
            "service_projection_quality": baseline.projection_quality,
            "unit_world_ray": unit_ray.tolist(),
            "plane_unit_normal": unit_normal.tolist(),
        },
        "jacobian": {
            "formula": "t*(A - d*(n@A)/(n@d))",
            "ray_parameter_is_axial_depth": True,
            "analytic_scene_units_per_pixel": jacobian.tolist(),
            "singular_values_scene_units_per_pixel": singular.tolist(),
            "max_scene_units_per_pixel": float(singular[0]),
            "min_scene_units_per_pixel": float(singular[-1]),
            "central_difference": central,
            "central_difference_frobenius_error_scene_units_per_pixel": difference,
            "central_difference_relative_frobenius_error": relative,
        },
        "high_precision": reference
        | {
            "difference_from_service_scene_units": float(np.linalg.norm(reference_point - point)),
            "binary64_closed_form_difference_scene_units": float(
                np.linalg.norm(closed_point - point)
            ),
            "reference_is_numeric_not_ground_truth": True,
        },
        "float32_diagnostic": float32,
        "roundtrip": {
            "input_point_provenance": "PROJECTED",
            "forward_reason": forward.reason.value,
            "pixel_error": pixel_error,
            "forward_then_inverse_position_error_scene_units": math.dist(
                recovered.world_position, baseline.world_position
            )
            if recovered
            else None,
            "status": "COMPUTED" if recovered else "UNAVAILABLE_AT_SERVICE_CONTRACT_BOUNDARY",
        },
    }


def _rotation(axis: int, degrees: float) -> np.ndarray:
    angle = math.radians(degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    result = np.eye(3)
    first, second = ((1, 2), (2, 0), (0, 1))[axis]
    result[first, first] = result[second, second] = cosine
    result[first, second], result[second, first] = -sine, sine
    return result


def camera_perturbations(camera: Camera) -> list[tuple[dict[str, Any], Camera]]:
    """Validated diagnostic copies; local pitch/yaw right-multiply the original R."""
    _reject_hidden_fields(camera, Camera)
    Camera.model_validate(camera.model_dump())
    variants = []
    for parameter in ("fx", "fy"):
        for delta in (-0.001, 0.001):
            copy = Camera.model_validate(
                camera.model_dump() | {parameter: getattr(camera, parameter) * (1 + delta)}
            )
            variants.append(
                (
                    _metadata()
                    | {
                        "variant_id": f"{parameter}:{delta:+g}",
                        "parameter": parameter,
                        "delta": delta,
                        "delta_unit": "RELATIVE",
                    },
                    copy,
                )
            )
    for parameter in ("cx", "cy"):
        for delta in (-0.1, 0.1):
            copy = Camera.model_validate(
                camera.model_dump() | {parameter: getattr(camera, parameter) + delta}
            )
            variants.append(
                (
                    _metadata()
                    | {
                        "variant_id": f"{parameter}:{delta:+g}",
                        "parameter": parameter,
                        "delta": delta,
                        "delta_unit": "PIXELS",
                    },
                    copy,
                )
            )
    original = np.asarray(camera.camera_to_world, dtype=float)
    for name, axis in (("local_pitch", 0), ("local_yaw", 1)):
        for delta in (-0.01, 0.01):
            matrix = original.copy()
            matrix[:3, :3] = original[:3, :3] @ _rotation(axis, delta)
            copy = Camera.model_validate(camera.model_dump() | {"camera_to_world": matrix.tolist()})
            variants.append(
                (
                    _metadata()
                    | {
                        "variant_id": f"{name}:{delta:+g}",
                        "parameter": name,
                        "delta": delta,
                        "delta_unit": "DEGREES",
                        "rotation_convention": "R_new=R_original@R_local_axis",
                    },
                    copy,
                )
            )
    for axis, name in enumerate(("world_x", "world_y", "world_z")):
        for delta in (-0.1, 0.1):
            matrix = original.copy()
            matrix[axis, 3] += delta
            copy = Camera.model_validate(camera.model_dump() | {"camera_to_world": matrix.tolist()})
            variants.append(
                (
                    _metadata()
                    | {
                        "variant_id": f"{name}:{delta:+g}",
                        "parameter": name,
                        "delta": delta,
                        "delta_unit": "BLENDER_SCENE_UNITS",
                    },
                    copy,
                )
            )
    return variants


def joint_focal_perturbations(camera: Camera) -> list[tuple[dict[str, Any], Camera]]:
    """Separate focal-length controls scaling fx and fy together, without source edits."""
    _reject_hidden_fields(camera, Camera)
    Camera.model_validate(camera.model_dump())
    return [
        (
            _metadata()
            | {
                "variant_id": f"joint_focal:{delta:+g}",
                "parameter": "fx_and_fy",
                "delta": delta,
                "delta_unit": "RELATIVE",
                "diagnostic_family": "JOINT_FOCAL_LENGTH_ONLY",
            },
            Camera.model_validate(
                camera.model_dump() | {"fx": camera.fx * (1 + delta), "fy": camera.fy * (1 + delta)}
            ),
        )
        for delta in (-0.001, 0.001)
    ]


def plane_perturbations(
    plane: Plane,
    *,
    projected_anchor: tuple[float, float, float] | None = None,
) -> list[tuple[dict[str, Any], Plane]]:
    """Metadata-point tilts measure displacement; anchor tilts measure conditioning."""
    _reject_hidden_fields(plane, Plane)
    Plane.model_validate(plane.model_dump())
    variants = []
    for height in (0.01, 0.1):
        for sign in (-1, 1):
            delta = sign * height
            point = list(plane.point)
            point[2] += delta
            copy = Plane.model_validate(plane.model_dump() | {"point": point})
            variants.append(
                (
                    _metadata()
                    | {
                        "variant_id": f"height:{delta:+g}",
                        "parameter": "world_z_height",
                        "delta": delta,
                        "delta_unit": "BLENDER_SCENE_UNITS",
                        "pivot_policy": "METADATA_PLANE_POINT",
                        "pivot_scene_units": list(plane.point),
                    },
                    copy,
                )
            )
    pivots = [("METADATA_PLANE_POINT", plane.point)]
    if projected_anchor is not None:
        if len(projected_anchor) != 3 or not all(math.isfinite(x) for x in projected_anchor):
            raise ValueError("conditioning anchor must be a finite PROJECTED three-vector")
        pivots.append(("BASELINE_PROJECTED_ANCHOR_CONDITIONING_ONLY", projected_anchor))
    for pivot_policy, pivot in pivots:
        for axis, name in ((0, "world_x_tilt"), (1, "world_y_tilt")):
            for delta in (-0.01, 0.01):
                normal = _rotation(axis, delta) @ np.asarray(plane.normal)
                normal /= np.linalg.norm(normal)
                copy = Plane.model_validate(
                    plane.model_dump() | {"point": pivot, "normal": normal.tolist()}
                )
                variants.append(
                    (
                        _metadata()
                        | {
                            "variant_id": f"{pivot_policy}:{name}:{delta:+g}",
                            "parameter": name,
                            "delta": delta,
                            "delta_unit": "DEGREES",
                            "pivot_policy": pivot_policy,
                            "pivot_scene_units": list(pivot),
                        },
                        copy,
                    )
                )
    return variants


def diagnose_perturbations(camera: Camera, plane: Plane, frame: ObservationFrame) -> dict[str, Any]:
    baseline = diagnose_projection(camera, plane, frame)
    if baseline["status"] != "ACCEPTED":
        return _metadata() | {
            "baseline": baseline,
            "calibration_variants": [],
            "plane_variants": [],
        }
    point = tuple(baseline["baseline_projected_point"]["world_position"])
    calibration_rows = []
    for metadata, variant in camera_perturbations(camera):
        diagnosis = diagnose_projection(variant, plane, frame)
        calibration_rows.append(
            {
                "perturbation": metadata,
                "diagnostic": diagnosis,
                "displacement_from_baseline_scene_units": math.dist(
                    point, diagnosis["baseline_projected_point"]["world_position"]
                )
                if diagnosis["status"] == "ACCEPTED"
                else None,
            }
        )
    plane_rows = []
    for metadata, variant in plane_perturbations(plane, projected_anchor=point):
        diagnosis = diagnose_projection(camera, variant, frame)
        plane_rows.append(
            {
                "perturbation": metadata,
                "diagnostic": diagnosis,
                "displacement_from_baseline_scene_units": math.dist(
                    point, diagnosis["baseline_projected_point"]["world_position"]
                )
                if diagnosis["status"] == "ACCEPTED"
                else None,
            }
        )
    return _metadata() | {
        "baseline": baseline,
        "calibration_variants": calibration_rows,
        "plane_variants": plane_rows,
    }


def synthetic_conditioning_grid(
    distances: tuple[float, ...] = (100, 300, 800),
    grazing_degrees: tuple[float, ...] = (90, 30, 10, 5, 2, 1, 0.1, 0.01, 0),
    *,
    fx: float = 640,
) -> list[dict[str, Any]]:
    """Independent configured planes passing through a fixed center-ray intersection."""
    rows = []
    for distance in distances:
        if not math.isfinite(distance) or distance <= 0:
            raise ValueError("synthetic distance must be finite positive")
        for grazing in grazing_degrees:
            if not math.isfinite(grazing) or not 0 <= grazing <= 90:
                raise ValueError("synthetic grazing angle must lie in [0,90]")
            radians = math.radians(grazing)
            camera = Camera(
                camera_id="PILOT_SYNTHETIC_CONDITIONING",
                fx=fx,
                fy=fx,
                cx=640,
                cy=360,
                width=1280,
                height=720,
                clip_start=0.01,
                clip_end=1000,
                camera_to_world=np.eye(4).tolist(),
                floor_id="DIAGNOSTIC",
            )
            plane = Plane(
                plane_id="PILOT_CONFIGURED_PLANE",
                point=(0, 0, -distance),
                normal=(math.cos(radians), 0, math.sin(radians)),
                floor_id="DIAGNOSTIC",
            )
            frame = ObservationFrame(
                frame_id=0,
                timestamp=0,
                target_id="CONFIGURED_CENTER_RAY",
                camera_id=camera.camera_id,
                status=VisibilityStatus.OBSERVED,
                point_2d=(640, 360),
                provenance=Provenance.OBSERVED,
            )
            baseline = diagnose_projection(camera, plane, frame)
            baseline_point = (
                baseline["baseline_projected_point"]["world_position"]
                if baseline["status"] == "ACCEPTED"
                else None
            )
            service = InverseProjectionService(camera, plane)
            perturbations = []
            for axis, axis_name in enumerate(("u", "v")):
                for magnitude in (0.05, 0.25, 1):
                    for sign in (-1, 1):
                        delta = sign * magnitude
                        pixel = list(frame.point_2d)
                        pixel[axis] += delta
                        perturbed_frame = ObservationFrame.model_validate(
                            frame.model_dump() | {"point_2d": pixel}
                        )
                        try:
                            projected = service.project_frame(perturbed_frame)
                            result = {
                                "status": "ACCEPTED",
                                "failure": None,
                                "world_position_scene_units": list(projected.world_position),
                                "world_displacement_from_center_scene_units": math.dist(
                                    baseline_point, projected.world_position
                                )
                                if baseline_point is not None
                                else None,
                            }
                        except InverseProjectionError as error:
                            result = {
                                "status": "REJECTED",
                                "failure": error.failure.value,
                                "world_position_scene_units": None,
                                "world_displacement_from_center_scene_units": None,
                            }
                        perturbations.append(
                            {
                                "variant_id": f"{axis_name}:{delta:+g}",
                                "axis": axis_name,
                                "delta_pixels": delta,
                                "pixel": pixel,
                            }
                            | result
                        )
            rows.append(
                baseline
                | {
                    "control_distance_scene_units": distance,
                    "control_grazing_angle_degrees": grazing,
                    "control_kind": "SYNTHETIC_FACTORIAL_ONLY_NOT_SCHOOL",
                    "control_clip_start_scene_units": camera.clip_start,
                    "control_clip_end_scene_units": camera.clip_end,
                    "directional_pixel_perturbations": perturbations,
                }
            )
    return rows
