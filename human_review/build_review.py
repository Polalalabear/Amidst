"""Regenerate minimal source-bound review evidence without opening or editing Blender.

All plotted vertices come from the committed semantic audit or failed scope witnesses.
The plot is a diagnostic geometry preview, never a source render or a navigation proof.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/amidst-finalization-review-mpl")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "human_review"
BUNDLE = ROOT / "data/scene_audit/phase1_physical_policy_approval_20261006"
SCALE = 0.0247
PHYSICAL_SHA = "f264db1579882e54cecba22db24ec8798822fd0c"
PROJECTION_SHA = "8f4055ffcdc3bf6efd723c7956ac685e1fe033f1"
FILES = [
    BUNDLE / "local_physical_scopes.json",
    BUNDLE / "floor_authority_map.json",
    BUNDLE / "body_clearance_policy.json",
    BUNDLE / "physical_authority.json",
    ROOT / "data/scene_audit/school_v3_semantic_audit.json",
    ROOT / "configs/benchmarks/protocol_v1.json",
]


def read(path: Path) -> dict:
    return json.loads(path.read_text())


local, floors, body, physical, audit, protocol = [read(path) for path in FILES]
assert local["approved_scope_count"] == 0 and local["approved_scopes"] == []
assert audit["source_sha256"] == local["source_sha256"] == floors["source_sha256"]
objects = {row["object"]: row for row in audit["objects"]}
floor_reviews = {row["walkable_id"]: row for row in floors["walkable_reviews"]}
regions = []
for row in local["regions"]:
    witnesses = []
    # A few localization excerpts per region suffice; full evidence stays referenced.
    reasons = set()
    for witness in row["review_witnesses"]:
        reason = witness["reason"]
        if reason in reasons:
            continue
        reasons.add(reason)
        extracted = dict(witness)
        if "location_bu" in witness:
            extracted["location_m"] = [value * SCALE for value in witness["location_bu"]]
        if "triangle_bu" in witness:
            extracted["triangle_m"] = [
                [value * SCALE for value in p] for p in witness["triangle_bu"]
            ]
            extracted["location_bu"] = [
                sum(p[axis] for p in witness["triangle_bu"]) / 3 for axis in range(3)
            ]
            extracted["location_m"] = [value * SCALE for value in extracted["location_bu"]]
        witnesses.append(extracted)
    proxy = objects[row["walkable_id"]]
    floor = floor_reviews[row["walkable_id"]]
    regions.append(
        {
            "region_id": row["region_id"],
            "walkable_id": row["walkable_id"],
            "floor_id": floor["floor_id"],
            "area_id": proxy["custom_properties"].get("source_area_id"),
            "portal_id": None,
            "portal_required_for_this_bounded_review": False,
            "floor_support_authority": floor["authority"],
            "full_annotation_supported": floor["full_annotation_supported"],
            "floor_support_z_bu": floor["source_support_height_bu"],
            "floor_support_z_m": floor["source_support_height_m"],
            "floor_support_area_m2": floor["support_area_m2"],
            "body_or_ceiling_clearance_approved": floors["body_or_ceiling_clearance_approved"],
            "physical_scope_status": row["status"],
            "certificate": row["certificate"],
            "searched_window_count": row["searched_window_count"],
            "search_is_exhaustive_geometric_window_enumeration": row[
                "search_is_exhaustive_geometric_window_enumeration"
            ],
            "preview_proxy_vertices_bu": proxy["vertices"],
            "preview_proxy_triangles": proxy["triangles"],
            "witness_excerpts": witnesses,
            "full_witness_reference": (
                "data/scene_audit/phase1_physical_policy_approval_20261006/"
                f"local_physical_scopes.json#{row['region_id']}"
            ),
        }
    )

choices = ["APPROVE", "REJECT", "FIX_GEOMETRY", "KEEP_REVIEW"]
gate = {
    "schema_version": "phase1-finalization-human-review-v1",
    "gate_id": "PHASE1-FINALIZATION-LOCAL-AUTHORITY-AND-FORMAL-SETTINGS",
    "status": "BLOCKED",
    "classification": "DIAGNOSTIC",
    "physical_checkpoint_sha": PHYSICAL_SHA,
    "projection_checkpoint_sha": PROJECTION_SHA,
    "source_sha256": local["source_sha256"],
    "metres_per_blender_unit": SCALE,
    "original_source_modified": False,
    "case_ids_blocked": ["case1", "case2", "case3"],
    "allowed_choices": choices,
    "approved": {
        "architectural_scale": "APPROVED",
        "body_policy": body["policy_metres"],
        "supported_walkable_subdomains": floors["approved_supported_subdomain_count"],
        "known_collision_components": 58,
        "complete_local_physical_scopes": 0,
    },
    "minimal_blockers": [
        {
            "id": "LOCAL_NAVIGATION_AUTHORITY",
            "current_authority": "REVIEW / NOT_CERTIFIED",
            "issue": (
                "No complete source-bound local physical scope certificate "
                "exists. Shared unclassified group_0 enclosure has uncertain "
                "solid interior; sampled windows can also encounter contact or "
                "degenerate triangles."
            ),
            "required_decision_payload": (
                "Select a limited review domain and decide intended surface/solid "
                "ownership only for source faces relevant to that domain, or "
                "authorize a traceable derived-geometry correction. No whole "
                "group_0 component approval is requested. The agent computes "
                "clearance and exact local certification after this semantic "
                "decision; failures remain REVIEW."
            ),
            "not_requested": [
                "global school approval",
                "1422 WALL patch reviews",
                "73 provisional WALL collider upgrades",
                "eight unrelated portal approvals",
                "Stair A/B approval",
                "whole group_0 component authority",
                "human calculation of clearance or local certificates",
            ],
        },
        {
            "id": "CAMERA_LANDMARK_AND_FLOOR_SEMANTIC_BINDING",
            "current_authority": "UNRESOLVED_RESEARCH_SETTING",
            "issue": (
                "Existing calibration/diagnostic pilot bindings do not establish "
                "approved case-specific floor/contact plane, endpoint access, "
                "camera topology and unique/branched feasible route inventory."
            ),
            "required_decision_payload": (
                "Confirm the observed landmark definition and its intended "
                "floor/contact-plane relation for the selected local domain "
                "and existing source-bound cameras. The agent extracts and "
                "verifies calibration, endpoint access and topology, then "
                "computes route uniqueness, branch count and feasible route "
                "inventory after geometry semantics are resolved."
            ),
        },
        {
            "id": "FORMAL_METRIC_SETTINGS",
            "current_authority": protocol["status"],
            "issue": (
                "Formal Coverage distance/epsilon and temporal "
                "alignment/interpolation/reference sampling are still null in "
                "committed protocol. Historical diagnostic epsilon is not a "
                "formal choice."
            ),
            "required_decision_payload": (
                "Declare Coverage D and strictly positive epsilon in metres plus "
                "supported alignment/interpolation/reference sampling settings "
                "before any formal run. Requested K=[1,2,3] is already supplied "
                "by this Sprint request."
            ),
            "configuration": "configs/benchmarks/protocol_v1.json",
            "current_formal_settings": protocol["coverage"]["formal_settings"],
            "epsilon_proposed_by_this_package": None,
        },
    ],
    "programmatic_checks_after_semantic_decision": [
        "source and calibration hash verification",
        "clearance, floor containment and exact local scope certification",
        "endpoint access and authorized adjacency extraction",
        "Case1 route uniqueness and Case2 branch count",
        "feasible route inventory, speed/time pruning and timing hypotheses",
        "independent simulation/evaluation movement and dwell annotations",
        "formal input versioning and all Sprint exit gates",
    ],
    "choice_semantics": {
        "APPROVE": (
            "Approve only a fully specified, source-bound "
            "scope/binding/setting payload. Geometry still must pass the "
            "existing programmatic certificate and all finalization exit "
            "gates."
        ),
        "REJECT": (
            "Exclude the reviewed proposed domain or settings; retain "
            "approved component/floor evidence and seek an independently "
            "eligible bounded replacement."
        ),
        "FIX_GEOMETRY": (
            "Authorize a separate traceable derived geometry/evidence "
            "correction plan; original school_v3.blend remains immutable. "
            "Regenerate and validate source bindings before approval."
        ),
        "KEEP_REVIEW": (
            "Keep this gate pending and prohibit formal Case1-3/freeze while "
            "preserving completed independent work."
        ),
    },
    "candidate_region_evidence": regions,
    "scope_domain_warning": (
        "Listed regions are existing bounded search candidates, not "
        "approved navigation routes. No route is invented here."
    ),
    "source_component_summary": {
        "source_object_id": "group_0",
        "source_component_id": "component-00000000",
        "triangle_count": 17596,
        "degenerate_triangle_count": 1456,
        "nonmanifold_edge_count": 11635,
        "boundary_edge_count": 0,
        "closed_consistent_nonzero_volume": False,
    },
    "case_impact": {
        "case1": (
            "Unique feasible route and full body clearance cannot be "
            "certified from a floor-support approval alone."
        ),
        "case2": (
            "Two or three routes must be independently authorized; timing "
            "duplicates or hand-made branch offsets are not feasible-route "
            "evidence."
        ),
        "case3": (
            "Long-gap feasibility needs the same approved routes plus frozen "
            "speed/timing and independent movement/dwell reference policy."
        ),
    },
    "source_files": [
        {
            "path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in FILES
    ],
}
(OUT / "gate.json").write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n")

# Exact XY vertices from the committed audit; this is an annotation/evidence plot.
fig, ax = plt.subplots(figsize=(11, 10), layout="constrained")
colors = ["#2171b5", "#6baed6", "#31a354", "#fd8d3c", "#e6550d"]
for region, color in zip(regions, colors, strict=True):
    vertices = region["preview_proxy_vertices_bu"]
    polygons = [
        [(vertices[i][0] * SCALE, vertices[i][1] * SCALE) for i in tri]
        for tri in region["preview_proxy_triangles"]
    ]
    ax.add_collection(PolyCollection(polygons, facecolor=color, edgecolor=color, alpha=0.35))
    xy = [(p[0] * SCALE, p[1] * SCALE) for p in vertices]
    x = (min(p[0] for p in xy) + max(p[0] for p in xy)) / 2
    y = (min(p[1] for p in xy) + max(p[1] for p in xy)) / 2
    ax.annotate(
        region["walkable_id"].replace("WALK_", "") + "\nFloor support APPROVED; body scope REVIEW",
        (x, y),
        xytext=(8, 10),
        textcoords="offset points",
        fontsize=8,
        color=color,
        bbox={"facecolor": "white", "alpha": 0.9, "edgecolor": color},
    )
    witness = next(w for w in region["witness_excerpts"] if "location_m" in w)
    ax.scatter(
        [witness["location_m"][0]],
        [witness["location_m"][1]],
        marker="x",
        s=65,
        color="#b2182b",
        linewidth=2,
    )
ax.autoscale()
ax.set_aspect("equal")
ax.set_xlabel("Source X (m); native BU × 0.0247")
ax.set_ylabel("Source Y (m); native BU × 0.0247")
ax.set_title(
    (
        "DIAGNOSTIC: five existing candidate body regions\nExact audit "
        "annotation footprints; witness ×; no approved routes or local "
        "certificates"
    ),
    fontsize=12,
)
ax.grid(alpha=0.25)
fig.savefig(OUT / "candidate_regions_xy.png", dpi=170)
plt.close(fig)

# Triangle from a real contact witness; no invented building/body geometry is drawn.
witness = regions[0]["witness_excerpts"][0]
triangle = witness["triangle_m"]
fig = plt.figure(figsize=(9, 7), layout="constrained")
ax = fig.add_subplot(111, projection="3d")
ax.add_collection3d(
    Poly3DCollection([triangle], facecolors="#ef8a62", edgecolors="#b2182b", alpha=0.65)
)
for i, point in enumerate(triangle):
    ax.scatter(*point, color="#b2182b", s=35)
    ax.text(*point, f"  V{i}", fontsize=9)
xs, ys, zs = [[p[i] for p in triangle] for i in range(3)]
for setter, values in zip([ax.set_xlim, ax.set_ylim, ax.set_zlim], [xs, ys, zs], strict=True):
    low, high = min(values), max(values)
    pad = max((high - low) * 0.08, 0.08)
    setter(low - pad, high + pad)
ax.set_box_aspect((0.3, max(ys) - min(ys), max(zs) - min(zs)))
ax.set_xticks([triangle[0][0]])
ax.set_xlabel("X (m)", labelpad=12)
ax.set_ylabel("Y (m)")
ax.set_zlabel("Z (m)", labelpad=12)
ax.set_title(
    (
        "DIAGNOSTIC: evaluated source triangle\ngroup_0.003 / face 1030 — "
        "unclassified body contact witness"
    ),
    fontsize=12,
)
fig.savefig(OUT / "source_body_contact_face1030.png", dpi=170)
plt.close(fig)

(OUT / "manifest.json").write_text(
    json.dumps(
        {
            "schema_version": "phase1-review-manifest-v1",
            "source_sha256": local["source_sha256"],
            "result_type": "DIAGNOSTIC",
            "source_scene_modified": False,
            "plot_kind": (
                "EXACT_COMMITTED_SOURCE_WITNESS_AND_ANNOTATION_GEOMETRY_NOT_BLENDER_SCREENSHOT"
            ),
            "regeneration_command": "uv run python human_review/build_review.py",
            "artifact_hashes": {
                name: hashlib.sha256((OUT / name).read_bytes()).hexdigest()
                for name in [
                    "README.md",
                    "build_review.py",
                    "gate.json",
                    "candidate_regions_xy.png",
                    "source_body_contact_face1030.png",
                ]
            },
            "input_hashes": gate["source_files"],
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n"
)
print("Generated diagnostic human review JSON, manifest and two exact-evidence PNG previews.")
