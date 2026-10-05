"""Derived WALL selections must preserve physical visibility and source identity."""

from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[2]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


export = load_script("export_blender_pilot")
validation = load_script("validate_blender_pilot")


class Object(dict):
    def __init__(self, name: str, **properties):
        super().__init__(properties)
        self.name = name
        self.type = "MESH"


def test_wall_annotations_excluded_without_reclassifying_physical_source():
    physical = Object("group_0", semantic_class="WALL")
    named = Object("WALL_1F_PATCH_001")
    explicit = Object("unrelated_selection_name", annotation_only=True)
    collection_only = Object("selection_in_wall_collection")
    false_flag = Object("group_0.123", annotation_only=False)
    bpy = SimpleNamespace(data=SimpleNamespace(collections={
        "WALL_ANNOTATIONS": SimpleNamespace(all_objects=[collection_only]),
    }))
    scene = SimpleNamespace(objects=[physical, named, explicit, collection_only, false_flag])
    excluded = export.annotation_objects(bpy, scene)
    assert {obj.name for obj in excluded} == {
        named.name, explicit.name, collection_only.name,
    }
    assert physical.name not in {obj.name for obj in excluded}
    assert false_flag.name not in {obj.name for obj in excluded}


def marking_scene_and_lineage():
    values = {
        "phase1_wall_marking_source_sha256": "1" * 64,
        "phase1_wall_marking_candidate_sidecar_sha256": "2" * 64,
        "phase1_wall_marking_physical_geometry_sha256": "3" * 64,
        "phase1_wall_marking_count": 1,
    }
    scene = SimpleNamespace(
        get=values.get,
        objects=[Object("WALL_1F_PATCH_1", annotation_only=True, semantic_class="WALL")],
    )
    lineage = {
        "original_source_sha256": "1" * 64,
        "wall_candidate_sidecar_sha256": "2" * 64,
        "original_physical_geometry_sha256": "3" * 64,
        "wall_semantic_marking_count": 1,
    }
    return scene, lineage


def test_export_rejects_lineage_from_other_saved_marking_context():
    scene, lineage = marking_scene_and_lineage()
    export.verify_lineage_metadata(scene, lineage)
    lineage["wall_candidate_sidecar_sha256"] = "4" * 64
    with pytest.raises(ValueError, match="saved scene"):
        export.verify_lineage_metadata(scene, lineage)


def test_export_rejects_missing_wall_selection_even_with_matching_metadata():
    scene, lineage = marking_scene_and_lineage()
    scene.objects.clear()
    with pytest.raises(ValueError, match="annotation count"):
        export.verify_lineage_metadata(scene, lineage)


@pytest.fixture
def lineage_data(tmp_path: Path):
    original = tmp_path / "original.blend"
    original.write_bytes(b"immutable original mesh")
    derived = tmp_path / "derived.blend"
    derived.write_bytes(b"original mesh plus semantic selections")
    stat = original.stat()
    return {
        "source_scene": {"path": str(derived)},
        "source_lineage": {
            "original_source_path": str(original),
            "original_source_sha256": validation.sha256(original),
            "original_source_size": stat.st_size,
            "original_source_mtime_ns": stat.st_mtime_ns,
            "original_source_identity_verified": True,
            "wall_candidate_sidecar_sha256": "1" * 64,
            "original_physical_geometry_sha256": "2" * 64,
            "wall_semantic_marking_count": 81,
            "wall_semantic_marking_policy": "ANNOTATION_ONLY_PHYSICAL_ROLE_NOT_APPROVED",
        },
    }


def test_live_original_identity_verified_for_separate_derived_scene(lineage_data):
    result, errors = validation.check_source_lineage(lineage_data, verify_source=True)
    assert errors == []
    assert result["verified"]


def test_changed_original_rejected_despite_unchanged_recorded_lineage(lineage_data):
    Path(lineage_data["source_lineage"]["original_source_path"]).write_bytes(b"changed mesh")
    result, errors = validation.check_source_lineage(lineage_data, verify_source=True)
    assert not result["verified"]
    assert any("hash/size/mtime differs" in error for error in errors)


@pytest.mark.parametrize("key,value", [
    ("original_source_identity_verified", False),
    ("wall_semantic_marking_policy", "PHYSICAL_COLLIDER_APPROVED"),
    ("wall_semantic_marking_count", True),
    ("wall_candidate_sidecar_sha256", "not-a-digest"),
])
def test_invalid_lineage_authority_or_identity_rejected(lineage_data, key, value):
    data = deepcopy(lineage_data)
    data["source_lineage"][key] = value
    result, errors = validation.check_source_lineage(data, verify_source=True)
    assert not result["verified"]
    assert errors


def test_source_check_skip_does_not_claim_original_verified(lineage_data):
    result, errors = validation.check_source_lineage(lineage_data, verify_source=False)
    assert errors == []
    assert not result["verified"]


def test_original_asset_cannot_be_claimed_as_separate_derived_scene(lineage_data):
    lineage_data["source_scene"]["path"] = lineage_data["source_lineage"]["original_source_path"]
    result, errors = validation.check_source_lineage(lineage_data, verify_source=True)
    assert not result["verified"]
    assert any("separate derived scene" in error for error in errors)
