"""Transient neutral surface shading for Blender Phase 1 renders.

The caller opens the source scene and uses this context around its render/export.
The context changes view-layer overrides only, restores them even on failure, and
never saves a Blender file. Original surface materials, image nodes and UVs remain.
Lighting and world settings are outside this surface-material policy.
Render the supplied scene without adding/removing view layers inside the context.
The policy targets shader-based rendering, not Solid/Wireframe/Workbench display.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

POLICY_ID = "phase1_neutral_surface_v1"
BASE_COLOR = (0.5, 0.5, 0.5, 1.0)
ROUGHNESS = 0.8


@contextmanager
def neutral_material_override(scene: Any) -> Iterator[Any]:
    """Apply texture-free opaque gray shading to every scene view layer temporarily."""
    import bpy  # type: ignore[import-not-found]

    material = bpy.data.materials.new(name=POLICY_ID)
    previous_overrides = [(layer, layer.material_override) for layer in scene.view_layers]
    try:
        material.diffuse_color = BASE_COLOR
        material.use_nodes = True
        nodes = material.node_tree.nodes
        nodes.clear()
        shader = nodes.new("ShaderNodeBsdfPrincipled")
        shader.inputs["Base Color"].default_value = BASE_COLOR
        shader.inputs["Metallic"].default_value = 0.0
        shader.inputs["Roughness"].default_value = ROUGHNESS
        shader.inputs["Alpha"].default_value = 1.0
        shader.inputs["Transmission Weight"].default_value = 0.0
        shader.inputs["Emission Color"].default_value = (0.0, 0.0, 0.0, 1.0)
        shader.inputs["Emission Strength"].default_value = 0.0
        output = nodes.new("ShaderNodeOutputMaterial")
        material.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
        for layer, _ in previous_overrides:
            layer.material_override = material
        yield material
    finally:
        for layer, previous in previous_overrides:
            layer.material_override = previous
        bpy.data.materials.remove(material)
