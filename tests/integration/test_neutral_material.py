"""Validate temporary material overrides in a fresh Blender process, without rendering."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@pytest.mark.parametrize("source_scene", [None, REPO_ROOT / "blender/school_v2.blend"])
def test_neutral_override_restores_original_data_on_success_and_failure(
    source_scene: Path | None,
) -> None:
    blender = os.environ.get("BLENDER_BIN") or shutil.which("blender")
    if not blender:
        pytest.skip("Blender CLI is unavailable")
    if source_scene is not None and not source_scene.is_file():
        pytest.skip("The local school_v2 source asset is unavailable")
    source_hash = _sha256(source_scene) if source_scene else None
    source_dir = str(REPO_ROOT / "src")
    code = f"""
import sys
sys.path.insert(0, {source_dir!r})
import bpy
from amidst.simulation.neutral_material import neutral_material_override

scene = bpy.context.scene
scene.view_layers.new('Additional')
mesh = bpy.data.meshes.new('TestMesh')
obj = bpy.data.objects.new('TestObject', mesh)
scene.collection.objects.link(obj)
original = bpy.data.materials.new('OriginalTexturedSurface')
original.use_nodes = True
image = bpy.data.images.new('OriginalImage', width=1, height=1)
texture = original.node_tree.nodes.new('ShaderNodeTexImage')
texture.image = image
obj.data.materials.append(original)
scene.view_layers[0].material_override = original
layers_before = [layer.material_override for layer in scene.view_layers]
materials_before = set(bpy.data.materials.keys())
slots_before = list(obj.data.materials)

for should_fail in (False, True):
    try:
        with neutral_material_override(scene) as material:
            assert all(layer.material_override == material for layer in scene.view_layers)
            assert set(node.bl_idname for node in material.node_tree.nodes) == {{
                'ShaderNodeBsdfPrincipled', 'ShaderNodeOutputMaterial'}}
            shader = next(node for node in material.node_tree.nodes
                          if node.bl_idname == 'ShaderNodeBsdfPrincipled')
            assert abs(shader.inputs['Roughness'].default_value - 0.8) < 1e-6
            assert shader.inputs['Metallic'].default_value == 0.0
            assert shader.inputs['Alpha'].default_value == 1.0
            assert shader.inputs['Transmission Weight'].default_value == 0.0
            assert list(obj.data.materials) == slots_before
            assert texture.image == image
            if should_fail:
                raise RuntimeError('test exception')
    except RuntimeError:
        assert should_fail
    assert [layer.material_override for layer in scene.view_layers] == layers_before
    assert set(bpy.data.materials.keys()) == materials_before
    assert list(obj.data.materials) == slots_before
    assert texture.image == image
print('NEUTRAL_MATERIAL_VALIDATION_OK')
"""
    command = [
        blender,
        "--background",
        "--factory-startup",
        "--disable-autoexec",
        "-noaudio",
    ]
    if source_scene:
        command.append(str(source_scene))
    command.extend(
        [
            "--python-exit-code",
            "2",
            "--python-expr",
            code,
        ]
    )
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        if source_scene:
            assert _sha256(source_scene) == source_hash
    assert "NEUTRAL_MATERIAL_VALIDATION_OK" in result.stdout
