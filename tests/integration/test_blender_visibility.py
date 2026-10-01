"""Physical evaluated-mesh raycasting regressions in unsaved factory fixtures."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _blender() -> str:
    executable = os.environ.get("BLENDER_BIN") or shutil.which("blender")
    if executable is None:
        installed = Path("/Applications/Blender.app/Contents/MacOS/blender")
        executable = str(installed) if installed.is_file() else None
    if executable is None:
        pytest.skip("Blender CLI unavailable")
    return executable


def _run(body: str) -> None:
    # Only the fresh factory default cube is removed, never a source asset.
    setup = f"""
import sys
sys.path.insert(0, {str(REPO_ROOT / "src")!r})
import bpy
from amidst.simulation.blender_visibility import BlenderMeshRaycaster
scene = bpy.context.scene
bpy.data.objects.remove(bpy.data.objects['Cube'], do_unlink=True)
def cube(name, center, scale, collection=None):
    mesh = bpy.data.meshes.new(name + 'Mesh')
    vertices = [(x,y,z) for z in (-1,1)
                for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]]
    mesh.from_pydata(vertices, [], [(0,3,2,1),(4,5,6,7),(0,1,5,4),
                                  (1,2,6,5),(2,3,7,6),(3,0,4,7)])
    obj = bpy.data.objects.new(name, mesh)
    (collection or scene.collection).objects.link(obj)
    obj.location, obj.scale = center, scale
    bpy.context.view_layer.update()
    return obj
def check(result, reason, occluder=None):
    assert result.reason == reason, result
    assert result.occluded == (reason != 'CLEAR'), result
    if occluder is not None:
        assert result.occluder_id == occluder, result
"""
    completed = subprocess.run(
        [
            _blender(),
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "-noaudio",
            "--python-exit-code",
            "2",
            "--python-expr",
            setup + body + "\nprint('PHYSICAL_RAYCAST_OK')",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=90,
    )
    assert "PHYSICAL_RAYCAST_OK" in completed.stdout


def test_actual_mesh_occlusion_clear_nearest_endpoint_and_origin_inside() -> None:
    _run("""
wall = cube('Wall', (5,0,0), (0.1,2,2))
raycaster = BlenderMeshRaycaster(scene)
check(raycaster((0,0,0), (10,0,0)), 'OCCLUDED', 'Wall')
check(raycaster((0,5,0), (10,5,0)), 'CLEAR')
check(raycaster((5,0,0), (10,0,0)), 'OCCLUDED', 'Wall')
floor = cube('Floor', (0,0,-0.5), (10,10,0.5))
raycaster.refresh()
check(raycaster((0,0,5), (0,0,0)), 'CLEAR')
near = cube('NearWall', (2,0,0), (0.1,2,2))
raycaster.refresh()
check(raycaster((0,0,1), (10,0,1)), 'OCCLUDED', 'NearWall')
wall.hide_render = True
near.hide_render = True
bpy.context.view_layer.update()
raycaster.refresh()
check(raycaster((0,0,1), (10,0,1)), 'OCCLUDED', 'NearWall')
check(raycaster((0,0,0), (0,0,0)), 'GEOMETRY_UNCERTAIN')
check(raycaster((float('nan'),0,0), (10,0,0)), 'GEOMETRY_UNCERTAIN')
""")


def test_annotation_proxy_exclusion_does_not_skip_thin_or_coincident_walls() -> None:
    _run("""
areas = bpy.data.collections.new('Areas')
scene.collection.children.link(areas)
annotation = cube('AREA_HELPER', (2,0,0), (0.5,2,2), areas)
proxy = cube('OWNED_TARGET_PROXY', (1,0,0), (0.2,0.2,1))
raycaster = BlenderMeshRaycaster(scene, excluded_objects=(proxy,))
check(raycaster((0,0,0), (10,0,0)), 'CLEAR')
thin = cube('ThinPhysicalWall', (2.00002,0,0), (0.000005,2,2))
raycaster.refresh()
check(raycaster((0,0,0), (10,0,0)), 'OCCLUDED', 'ThinPhysicalWall')
included_proxy = BlenderMeshRaycaster(scene)
check(included_proxy((0,0,0), (10,0,0)), 'OCCLUDED', 'OWNED_TARGET_PROXY')
coincident = cube('CoincidentPhysicalWall', (1.5,0,0), (0.000005,2,2))
raycaster.refresh()
check(raycaster((0,0,0), (10,0,0)), 'OCCLUDED', 'CoincidentPhysicalWall')
""")


def test_scaled_rotated_collection_instances_and_instance_parent_exclusion() -> None:
    _run("""
prototype = bpy.data.collections.new('UnlinkedWallPrototype')
source = cube('InstancedWall', (0,0,0), (0.15,1,1), prototype)
instancer = bpy.data.objects.new('WallInstance', None)
instancer.instance_type = 'COLLECTION'
instancer.instance_collection = prototype
scene.collection.objects.link(instancer)
instancer.location = (5,0,0)
instancer.rotation_euler = (0,0,0.37)
instancer.scale = (2,0.5,3)
bpy.context.view_layer.update()
raycaster = BlenderMeshRaycaster(scene)
assert len(raycaster._meshes) == 1, len(raycaster._meshes)
check(raycaster((0,0,0), (10,0,0)), 'OCCLUDED', 'InstancedWall')
excluded_instance = BlenderMeshRaycaster(scene, excluded_objects=(instancer,))
check(excluded_instance((0,0,0), (10,0,0)), 'CLEAR')
rotated = cube('RotatedScaledWall', (7,4,0), (0.1,2,1))
rotated.rotation_euler = (0,0,0.5)
bpy.context.view_layer.update()
raycaster.refresh()
check(raycaster((0,4,0), (10,4,0)), 'OCCLUDED', 'RotatedScaledWall')
""")


def test_budget_frame_refresh_singular_transform_and_query_failure_fail_closed() -> None:
    _run("""
wall = cube('AnimatedWall', (5,0,0), (0.1,1,1))
wall.keyframe_insert(data_path='location', frame=1)
wall.location = (5,10,0)
wall.keyframe_insert(data_path='location', frame=2)
scene.frame_set(1)
raycaster = BlenderMeshRaycaster(scene)
check(raycaster((0,0,0), (10,0,0)), 'OCCLUDED', 'AnimatedWall')
limited = BlenderMeshRaycaster(scene, max_candidates=0)
check(limited((0,0,0), (10,0,0)), 'RAYCAST_LIMIT')
check(limited((0,5,0), (10,5,0)), 'CLEAR')
scene.frame_set(2)
check(raycaster((0,0,0), (10,0,0)), 'CLEAR')
mutable = cube('MutableWall', (8,10,0), (0.1,1,1))
raycaster.refresh()
check(raycaster((0,0,0), (10,0,0)), 'CLEAR')
mutable.location = (8,0,0)
bpy.context.view_layer.update()
raycaster.refresh()
check(raycaster((0,0,0), (10,0,0)), 'OCCLUDED', 'MutableWall')
singular = cube('SingularWall', (3,0,0), (0,1,1))
raycaster.refresh()
check(raycaster((0,0,0), (10,0,0)), 'GEOMETRY_UNCERTAIN', 'SingularWall')
bpy.data.objects.remove(singular, do_unlink=True)
raycaster.refresh()
from dataclasses import replace
class UnavailableQuery:
    def ray_cast(self, *args, **kwargs):
        raise RuntimeError('unavailable query')
raycaster._meshes = tuple(replace(mesh, obj=UnavailableQuery())
                          for mesh in raycaster._meshes)
check(raycaster((0,0,0), (10,0,0)), 'GEOMETRY_UNCERTAIN')
""")
