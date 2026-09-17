#!/usr/bin/env python3
"""Shared constants and Blender helpers for render policy v0.1.1."""

from __future__ import annotations

import math
from typing import Any

import bpy
from mathutils import Vector


POLICY_ID = "amidst.school.texture-agnostic-render/0.1.1"
POLICY_VERSION = "0.1.1"
CONFIG_ID = "amidst.school.first-slice-render/0.1.1"
MATERIAL_NAME = "AMIDST_FirstSlice_Neutral_v0_1_1"
WORLD_NAME = "AMIDST_FirstSlice_World_v0_1_1"
OUTPUT_NAME = "school_v1_first_slice_texture_agnostic_v0_1_1_r2.blend"

BASE_COLOR = (0.35, 0.35, 0.35, 1.0)
METALLIC = 0.0
ROUGHNESS = 0.8
IOR = 1.45
ALPHA = 1.0
PRINCIPLED_WEIGHT = 1.0
TRANSMISSION_WEIGHT = 0.0

WORLD_COLOR = (0.02, 0.02, 0.02, 1.0)
WORLD_STRENGTH = 0.25

SUN_ENERGY = 0.75
SUN_COLOR = (1.0, 1.0, 1.0)
SUN_ANGLE_RADIANS = math.radians(10.0)
SUN_SPECS = (
    ("AMIDST_FirstSlice_Sun_PosX_v0_1_1", (1.0, 0.0, 0.0)),
    ("AMIDST_FirstSlice_Sun_NegX_v0_1_1", (-1.0, 0.0, 0.0)),
    ("AMIDST_FirstSlice_Sun_PosY_v0_1_1", (0.0, 1.0, 0.0)),
    ("AMIDST_FirstSlice_Sun_NegY_v0_1_1", (0.0, -1.0, 0.0)),
    ("AMIDST_FirstSlice_Sun_PosZ_v0_1_1", (0.0, 0.0, 1.0)),
    ("AMIDST_FirstSlice_Sun_NegZ_v0_1_1", (0.0, 0.0, -1.0)),
)


def finite_value(value: Any) -> Any:
    if hasattr(value, "__len__") and not isinstance(value, str):
        return [finite_value(item) for item in value]
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            raise RuntimeError(f"Non-finite render-policy value: {number}")
        return number
    return value


def socket_by_identifier(node: Any, identifier: str) -> Any:
    matches = [socket for socket in node.inputs if socket.identifier == identifier]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one {node.name} input identifier {identifier!r}, "
            f"found {len(matches)}"
        )
    return matches[0]


def set_socket(node: Any, identifier: str, value: Any) -> None:
    socket_by_identifier(node, identifier).default_value = value


def create_material() -> Any:
    if bpy.data.materials.get(MATERIAL_NAME) is not None:
        raise RuntimeError(f"Refusing to replace material: {MATERIAL_NAME}")
    material = bpy.data.materials.new(MATERIAL_NAME)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    output.name = "AMIDST_Material_Output_v0_1_1"
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.name = "AMIDST_Neutral_Opaque_v0_1_1"
    set_socket(shader, "Base Color", BASE_COLOR)
    set_socket(shader, "Metallic", METALLIC)
    set_socket(shader, "Roughness", ROUGHNESS)
    set_socket(shader, "IOR", IOR)
    set_socket(shader, "Alpha", ALPHA)
    set_socket(shader, "Weight", PRINCIPLED_WEIGHT)
    set_socket(shader, "Transmission Weight", TRANSMISSION_WEIGHT)
    material.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    material.diffuse_color = BASE_COLOR
    material["render_resource_policy_id"] = POLICY_ID
    material["semantic_encoding"] = False
    return material


def principled_input_record(material: Any) -> dict[str, Any]:
    shaders = [
        node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"
    ]
    if len(shaders) != 1:
        raise RuntimeError(f"Expected one Principled shader, found {len(shaders)}")
    return {
        socket.identifier: finite_value(socket.default_value)
        for socket in shaders[0].inputs
        if hasattr(socket, "default_value")
    }


def create_world() -> Any:
    if bpy.data.worlds.get(WORLD_NAME) is not None:
        raise RuntimeError(f"Refusing to replace world: {WORLD_NAME}")
    world = bpy.data.worlds.new(WORLD_NAME)
    world.use_nodes = True
    nodes = world.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputWorld")
    output.name = "AMIDST_World_Output_v0_1_1"
    background = nodes.new("ShaderNodeBackground")
    background.name = "AMIDST_World_Background_v0_1_1"
    background.inputs["Color"].default_value = WORLD_COLOR
    background.inputs["Strength"].default_value = WORLD_STRENGTH
    world.node_tree.links.new(background.outputs["Background"], output.inputs["Surface"])
    world["render_resource_policy_id"] = POLICY_ID
    return world


def create_lights(scene: Any) -> list[Any]:
    created = []
    for name, direction in SUN_SPECS:
        if bpy.data.objects.get(name) is not None or bpy.data.lights.get(name) is not None:
            raise RuntimeError(f"Refusing to replace deterministic light: {name}")
        data = bpy.data.lights.new(name, type="SUN")
        data.energy = SUN_ENERGY
        data.color = SUN_COLOR[:3]
        data.angle = SUN_ANGLE_RADIANS
        data.use_shadow = False
        data["render_resource_policy_id"] = POLICY_ID
        obj = bpy.data.objects.new(name, data)
        obj.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()
        obj["render_resource_policy_id"] = POLICY_ID
        scene.collection.objects.link(obj)
        created.append(obj)
    return created


def light_record(obj: Any) -> dict[str, Any]:
    direction = -(obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0)))
    return {
        "object_name": obj.name,
        "data_name": obj.data.name,
        "type": obj.data.type,
        "direction_world": finite_value(direction),
        "matrix_world": [finite_value(row) for row in obj.matrix_world],
        "energy": finite_value(obj.data.energy),
        "color_linear_rgb": finite_value(obj.data.color),
        "angle_radians": finite_value(obj.data.angle),
        "angle_degrees": math.degrees(float(obj.data.angle)),
        "use_shadow": bool(obj.data.use_shadow),
        "hide_render": bool(obj.hide_render),
    }


def unlink_policy_lights(scene: Any) -> list[Any]:
    lights = []
    expected_names = {name for name, _direction in SUN_SPECS}
    for obj in list(scene.objects):
        if obj.name in expected_names:
            lights.append(obj)
            for collection in list(obj.users_collection):
                collection.objects.unlink(obj)
    return lights
