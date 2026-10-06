"""Assemble pending, source-bound human questions without reading GT or approving them."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "human_review"


def immutable_document(document: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(document)
    result.pop("review_payload_sha256", None)
    result["metadata"].pop("reviewer", None)
    result["metadata"].pop("submitted_at", None)
    for item in result["items"]:
        item.pop("decision", None)
        item.pop("selected_option", None)
    return result


def content_hash(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def main() -> None:
    if (HERE / "decisions.json").exists():
        current = json.loads((HERE / "decisions.json").read_text())
        if any(item.get("decision") is not None for item in current["items"]):
            raise ValueError("do not overwrite human decisions; create a new review version")
    geometry = json.loads((HERE / "geometry_evidence.json").read_text())
    settings = json.loads((HERE / "settings_evidence.json").read_text())
    visuals = json.loads((HERE / "frames/visual_manifest.json").read_text())
    if geometry["gt_used"] or visuals["gt_used"]:
        raise ValueError("human semantics cannot use Ground Truth")
    office = next(row for row in settings["streams"] if row["site_id"] == "office")
    common_location: dict[str, Any] = {
        "floor": "1F",
        "area": "AREA_1F_OFFICE / WALK_1F_OFFICE",
        "portal": "無；本次候選在 office 內，不核准任何門洞或跨區路徑",
        "nearby_object": "group_0；office obstacle 僅供位置辨認",
        "outliner_search": ["group_0", "AREA_1F_OFFICE", "WALK_1F_OFFICE"],
    }
    all_cases = [1, 2, 3]
    geometry_item: dict[str, Any] = {
        "id": "HR-01",
        "title": "一樓 office 行走帶：地板接縫與房間內部的物理語意",
        "category": "GEOMETRY",
        "blocks": all_cases,
        "location": common_location,
        "why_it_blocks": [
            (
                "Case 1–3 的 local scope certificate 目前被 group_0 的零面積"
                "接縫與未知 enclosure ownership 阻塞。"
            ),
            (
                "不處理時可以保留診斷候選，但不能宣稱 floor/body collision 或"
                "局部物理有效性已正式認證。"
            ),
            (
                "只核准下列 body guard 範圍內的 source-surface 語意；不核准整"
                "個 group_0、其他房間、WALL 或 portal。"
            ),
        ],
        "evidence": {
            "images": [
                {
                    "path": "frames/office_scope_closeup.png",
                    "caption": "HR-01 範圍近看：紫色 1975/2398 接縫、blue body guard、"
                    "人物 cylinder / clearance；畫面只有候選 hypothesis。",
                },
                {
                    "path": "frames/office_scope_top_closeup.png",
                    "caption": "HR-01 俯視近看：exact body guard 與 footpoint domain；"
                    "左路徑 AUTO_REJECT，direct/right 仍 NOT_CERTIFIED。",
                },
                {
                    "path": "frames/office_top.png",
                    "caption": "Blender evaluated source 俯視；紅線是接縫，紅色左路徑已自動淘汰。",
                },
                {
                    "path": "frames/office_side.png",
                    "caption": (
                        "側視：approved source floor、landmark projected dots 與待核准 offset；"
                        "cylinder / clearance 請看連續 frames。"
                    ),
                },
                {
                    "path": "frames/office_oblique.png",
                    "caption": "局部 source geometry、WALKABLE、PORTAL context 與候選行走帶。",
                },
            ],
            "sequence": "frames/player.html",
            "objects": ["group_0 / component-00000000", "WALK_1F_OFFICE", "AREA_1F_OFFICE"],
            "faces": [
                {
                    "object": "group_0",
                    "evaluated_source_face": row["source_face_index"],
                    "evaluated_triangle": row["source_triangle_index"],
                    "mesh_sha256": row["source_geometry_sha256"],
                    "machine_status": row["machine_status"],
                }
                for row in geometry["findings"]
            ],
            "bounds": {
                "footpoint_bu": geometry["prospective_footpoint_bounds_bu"],
                "footpoint_m": geometry["prospective_footpoint_bounds_m"],
                "body_guard_bu": geometry["body_envelope_bounds_bu"],
                "body_guard_m": geometry["body_envelope_bounds_m"],
                "seam_bounds_bu": geometry["findings"][0]["bounds_bu"],
                "seam_bounds_m": [
                    [v * 0.0247 for v in p] for p in geometry["findings"][0]["bounds_bu"]
                ],
            },
            "centroid": {
                "bu": geometry["findings"][0]["centroid_bu"],
                "m": geometry["findings"][0]["centroid_m"],
            },
            "measurements": [
                (
                    "radius 0.30 m = 12.145749 BU；height 1.70 m = 68.825911 BU；"
                    "clearance 0.05 m = 2.024291 BU（既有 APPROVED）。"
                ),
                (
                    "左側 route 最小 support clearance 7.674678 BU / 0.189565 m <"
                    " 14.170040 BU / 0.35 m：AUTO_REJECT，不需人工決策。"
                ),
                (
                    "direct / right support clearance >= 19.674678 BU / 0.485965 "
                    "m；完整 body/source certificate 仍 NOT_CERTIFIED。"
                ),
                (
                    "body guard 相交 source triangles 共 12：10 個已核准支撐三角"
                    "形，2 個 exact-zero-area seams。"
                ),
            ],
            "current_authority": [
                "Architectural scale / body policy / WALK_1F_OFFICE source support：APPROVED。",
                (
                    "source seams / component interior：HUMAN_REVIEW；local certi"
                    "ficate：REVIEW / DEGENERATE_SOURCE_BODY_CONTEXT_TRIANGLE。"
                ),
                (
                    "OBSTACLE_1F_OFFICE_01 / 02 的語意已核准，但 approved solid c"
                    "omponents = 0；不把它們當 hard collider。"
                ),
            ],
            "relevant_frames": (
                "Front frame 20 / t=4.0 s → 全視角 GAP → Rear frame 45 / t=9."
                "0 s；10 秒 preview 只顯示 public observations / inferred can"
                "didates。"
            ),
        },
        "machine_conclusion": {
            "known": [
                (
                    "兩個 source faces 1975 / 2398 精確為零面積；floor 高度、body"
                    " guard 與 support clearance 可自動計算。"
                ),
                "source atlas / mesh hashes 已固定；沒有缺省擴充整棟 authority。",
            ],
            "unknown": [
                (
                    "請確認這條接縫不代表實際佔用體積，且這個 bounded room interi"
                    "or 是由 source boundary surfaces 表示的自由空間。"
                ),
                "數值上的零面積不能自行代替 physical semantics；APPROVE 不會自動產生 PASS。",
            ],
        },
        "recommended_decision": "APPROVE",
        "recommended_option": "LOCAL_SOURCE_SURFACE_ONLY",
        "recommendation_reason": (
            "若畫面與 source scene 一致，採最小範圍 surface 語意即可；所"
            "有非零面積 source surfaces 仍照原 collision / support 檢查。"
        ),
        "approve_options": [
            {
                "id": "LOCAL_SOURCE_SURFACE_ONLY",
                "label": "局部 boundary surfaces；零面積接縫不佔體積（建議）",
                "why": (
                    "只聲明 body guard 內 group_0/component-00000000 的 interior "
                    "不作實心 collider，與指定兩個接縫沒有 solid ownership。"
                ),
                "payload": {
                    "source_object_id": "group_0",
                    "source_component_id": "component-00000000",
                    "region_id": "BODY:WALK_1F_OFFICE",
                    "zero_area_source_face_indices": [1975, 2398],
                    "component_interior": "SURFACE_ONLY_NO_SOLID_INTERIOR_IN_BOUND",
                    "body_envelope_bounds_bu": geometry["body_envelope_bounds_bu"],
                    "source_geometry_modified": False,
                    "whole_component_approved": False,
                },
            },
            {
                "id": "EXACT_DERIVED_SURFACE_REPAIR",
                "label": "相同局部語意；另允許精確接縫的 derived repair",
                "why": (
                    "只允許在衍生 surface context 中排除這兩個 exact-zero-area fa"
                    "ces；原 .blend 與非零面積 geometry 保持原樣。"
                ),
                "payload": {
                    "source_object_id": "group_0",
                    "source_component_id": "component-00000000",
                    "region_id": "BODY:WALK_1F_OFFICE",
                    "zero_area_source_face_indices": [1975, 2398],
                    "component_interior": "SURFACE_ONLY_NO_SOLID_INTERIOR_IN_BOUND",
                    "body_envelope_bounds_bu": geometry["body_envelope_bounds_bu"],
                    "source_geometry_modified": False,
                    "whole_component_approved": False,
                    "derived_exact_surface_repair_allowed": True,
                },
            },
        ],
        "decision": None,
        "selected_option": None,
    }
    items: list[dict[str, Any]] = [geometry_item]
    proposed = settings["review_decisions"]
    for index, old in enumerate(proposed, start=2):
        item = copy.deepcopy(old)
        item["id"] = f"HR-{index:02d}"
        item["recommended_decision"] = "APPROVE"
        item["selected_option"] = None
        item["approve_options"] = [
            {
                "id": option["id"],
                "label": option["id"],
                "payload": {key: value for key, value in option.items() if key != "id"},
            }
            for option in old["approve_options"]
        ]
        items.append(item)
    binding, coverage, timing = items[1:]
    binding["location"] = copy.deepcopy(common_location)
    binding["location"]["outliner_search"] += ["CAM_1F_AUDITORIUM_FRONT", "CAM_1F_AUDITORIUM_REAR"]
    binding["why_it_blocks"] = [
        "Case 1–3 需要 camera → 可見 landmark → approved floor contact 的正式綁定。",
        (
            "目前 projected marker 位於地板上方約 1.36 m；直接當人物落點"
            "會破壞 support、collision 與 metric reference。"
        ),
        (
            "Office 合法同步雙視角為 0/50；若不允許有 provenance 的 singl"
            "e-view fallback，GAP endpoints 無法正式提供。"
        ),
    ]
    binding["evidence"] = {
        "images": [
            {
                "path": row["path"],
                "caption": (
                    f"{row['camera_id']}：frame {row['frame_id']} / "  # Camera identity.
                    f"t={row['timestamp']} s；bounded source snapshot，"
                    "不是整場景 occlusion proof。"
                ),
            }
            for row in visuals["camera_stills"]
        ]
        + [
            {
                "path": "frames/office_side.png",
                "caption": (
                    "Landmark 與 approved floor 高度差；cylinder placement 是待核准的 hypothesis。"
                ),
            }
        ],
        "sequence": "frames/player.html",
        "objects": binding["location"]["outliner_search"],
        "faces": (
            "group_0 的 approved source floor binding：完整 source faces "
            "/ hashes 在 floor_support_details 與 geometry_evidence.json"
            "；camera 不是 mesh face。"
        ),
        "bounds": {
            "approved_local_footpoint_bu": geometry["prospective_footpoint_bounds_bu"],
            "approved_local_footpoint_m": geometry["prospective_footpoint_bounds_m"],
        },
        "centroid": "N/A（camera / plane binding）；floor plane normal = (0,0,1)。",
        "measurements": [
            f"landmark Z={office['landmark_z_bu']} BU / {office['landmark_z_m']} m。",
            f"floor Z={office['floor_support_z_bu']} BU / {office['floor_support_z_m']} m。",
            (
                f"精確 offset={office['rigid_landmark_to_floor_offset_bu']} BU / "
                f"{office['rigid_landmark_to_floor_offset_m']} m；"
                "由已核准 support 與 inference plane 相減，不由 GT 求值。"
            ),
            (
                "Camera calibration / pose / pixel UV 保存在 settings_evidenc"
                "e.json；以 source hash + observations hash 綁定。"
            ),
        ],
        "current_authority": (
            "floor / scale APPROVED；camera intrinsics/pose SOURCE_BOUND"
            "；camera-landmark-floor semantics HUMAN_REVIEW；legacy conte"
            "xt DIAGNOSTIC。"
        ),
        "relevant_frames": [
            {key: row[key] for key in ("camera_id", "frame_id", "timestamp", "public_uv")}
            for row in visuals["camera_stills"]
        ],
    }
    binding["machine_conclusion"] = {
        "known": [
            "固定 calibration、offset、timestamp 與單視角 availability 都已算出。",
            "不用 GT 選 pair 或 hypothesis；multiview unavailable 不等於 inference failure。",
        ],
        "unknown": [
            (
                "請核准所觀測 marker 的正式語意，以及這兩個 camera 對 bounded"
                " office floor 的綁定與 fallback。"
            ),
            "新 dataset 的 FOV / occlusion / scope containment 仍須自動驗證。",
        ],
    }
    binding["recommendation_reason"] = (
        "保留 source-bound marker 與現有 observation producer，只新增"
        "精確 landmark→footpoint adapter；新 formal observations 必須"
        " fresh export。"
    )
    binding["approve_options"][0]["label"] = "保留固定 marker；精確扣 Z offset 到地板（建議）"
    binding["approve_options"][0]["why"] = (
        "保留 XY 與 calibration；inference 的位置語意統一為 FLOOR_CON"
        "TACT_POINT；single-view fallback 保留 method / confidence / "
        "uncertainty。"
    )
    binding["approve_options"][1]["label"] = "改用可見足點 marker；offset=0，重新 export"
    binding["approve_options"][1]["why"] = (
        "足點不可見就保留 GAP；不得從其他 marker 或 GT 偽造觀测。"
    )
    coverage["location"] = {key: "N/A；Case 1–3 共用研究設定" for key in common_location}
    coverage["why_it_blocks"] = (
        "Case 1–3 的 Coverage@K 必須預先固定 epsilon；目前 formal epsilon=null，未決定只能報 N/A。"
    )
    coverage["evidence"] = {
        "images": [],
        "objects": "N/A",
        "faces": "N/A",
        "bounds": "N/A",
        "centroid": "N/A",
        "measurements": (
            "兩個研究選項：ADE < 0.50 m（20.242915 BU）或 < 1.00 m（40.485830 BU）；不是實測結果。"
        ),
        "current_authority": (
            "UNRESOLVED_RESEARCH_SETTING；protocol Case1 initial target 0"
            ".50 m / Case3 FDE initial target 1.00 m 只提供尺度依據，沒有"
            " Coverage approval。"
        ),
        "relevant_frames": "N/A；不需要視覺或 GT 來決定研究容差。",
    }
    coverage["machine_conclusion"] = {
        "known": [
            "現有唯一支援 D=ADE、3D Euclidean arithmetic mean、strictly < epsilon；K=1/2/3。"
        ],
        "unknown": ["研究者接受的正式 Coverage 容差；不能從 accuracy 結果反推。"],
    }
    coverage["recommendation_reason"] = (
        "0.50 m 與既有 Case1 target 尺度一致；所有 Case / method / K 共用，執行後不可改。"
    )
    coverage["approve_options"][0]["label"] = "全體 ADE < 0.50 m（建議）"
    coverage["approve_options"][1]["label"] = "全體 ADE < 1.00 m"
    timing["location"] = copy.deepcopy(common_location)
    timing["location"]["nearby_object"] = "N/A；運動模型 research setting"
    timing["why_it_blocks"] = (
        "Case1/2 travel-time pruning、Case3 長 GAP / detour / slack "
        "需要正式 speed ceiling 與已支援的 timing hypothesis policy。"
        "32 BU/s 目前只是 diagnostic setting。"
    )
    timing["evidence"] = {
        "images": [
            {
                "path": "frames/sequence_030.png",
                "caption": "t=6.0 s 的 GAP；人物與路徑均是 public candidate hypothesis，不是 GT。",
            }
        ],
        "sequence": "frames/player.html",
        "objects": "WALK_1F_OFFICE",
        "faces": "N/A；timing contract",
        "bounds": {
            "candidate_footpoint_bu": geometry["prospective_footpoint_bounds_bu"],
            "candidate_footpoint_m": geometry["prospective_footpoint_bounds_m"],
        },
        "centroid": "N/A",
        "measurements": [
            "最大速度 32 BU/s = 0.7904 m/s；direct slack 1.0 s。",
            (
                "departure waypoint dwell 是現有唯一 waiting alternative；uni"
                "form continuous timing 仍第一順位。"
            ),
            "preview 的 GAP endpoint duration=5.0 s；它不是正式 Case3 長 GAP。",
        ],
        "current_authority": (
            "Speed ceiling：PROPOSED；dwell/uniform：EXISTING_SUPPORTED_C"
            "ONTRACT；沒有 measured-person speed authority。"
        ),
        "relevant_frames": (
            "Office t=4.0→9.0 s GAP endpoint evidence；正式 Case3 必須另"
            "由 protocol stress inventory 固定並 fresh export。"
        ),
    }
    timing["machine_conclusion"] = {
        "known": [
            "現有速度上限、scale 換算、slack 與 timing supported variants 已確認。",
            "5 Hz 可由公開 timestamps 推導，直接沿用，不需人工算。",
        ],
        "unknown": [
            (
                "是否正式採用這個 research speed ceiling，以及是否保留 existi"
                "ng departure dwell alternative。"
            ),
            (
                "正式 Case3 stress instance 必須通過凍結前自動 timing feasibi"
                "lity / termination proof。"
            ),
        ],
    }
    timing["recommendation_reason"] = (
        "沿用現有 32 BU/s ceiling、1 s slack 與 supported dwell；不新增速度或 waiting model。"
    )
    timing["approve_options"][0]["label"] = "0.7904 m/s；均速 + 已支援 departure dwell（建議）"
    timing["approve_options"][1]["label"] = "0.7904 m/s；只保留均速 timing"
    input_hashes = {row["path"]: row["sha256"] for row in settings["input_hashes"]}
    input_hashes.update(geometry["input_hashes"])
    input_hashes.update({row["path"]: row["sha256"] for row in visuals["inputs"]})
    for name in ("geometry_evidence.json", "settings_evidence.json", "frames/visual_manifest.json"):
        path = HERE / name
        input_hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in (
        "src/amidst/local_semantic_review.py",
        "human_review/certificate_application.py",
        "human_review/apply_decisions.py",
    ):
        input_hashes[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    blocker_ids = [item["id"] for item in items]
    case_map = {
        str(case): {
            "blocker_count": 4,
            "blocker_ids": blocker_ids,
            "immediately_run_after_approve": False,
            "automatic_exit_checks": checks,
        }
        for case, checks in {
            1: [
                "bounded certificate PASS",
                "合法 visibility→GAP→visibility",
                "school route inventory 的唯一主要可行 route proof",
            ],
            2: [
                "bounded certificate PASS",
                (
                    "至少兩條真正可行且有 route diversity 的 school routes；目前 "
                    "direct/right 平行 offset 不足以證明 branching"
                ),
            ],
            3: [
                "bounded certificate PASS",
                (
                    "現有 protocol 長 GAP stress instance 的 speed/time feasibili"
                    "ty、候選增長與 termination proof"
                ),
            ],
        }.items()
    }
    document = {
        "metadata": {
            "schema_version": "phase1-human-review-decisions-v1",
            "checkpoint_sha": settings["checkpoint_sha"],
            "source_sha256": geometry["source_sha256"],
            "reviewer": "",
            "submitted_at": None,
            "automatic_settings": settings["automatic_settings"],
            "case_blocker_map": case_map,
            "input_hashes": [
                {"path": path, "sha256": value} for path, value in sorted(input_hashes.items())
            ],
            "scope_limitations": [
                "所有 decisions 都仍未決定；推薦值不等於 authority。",
                (
                    "geometry / binding 只限 bounded 1F office，不核准 corridor、"
                    "auditorium、stair、73 HC / 1422 HUMAN_REVIEW WALL 或8個 port"
                    "al conflicts。"
                ),
                (
                    "全部 APPROVE 後先自動 certificate / case-inventory / source-"
                    "bound formal adapter checks；不把原 diagnostic streams relab"
                    "el FORMAL。"
                ),
                (
                    "目前 configured direct/right 平行 routes 未證明正式 Case2 br"
                    "anching；Case1 uniqueness 與 Case3 long-gap instance 也尚未"
                    "完成。"
                ),
                (
                    "只在新的 geometry contradiction、超出已核准 body guard 或必"
                    "要新 landmark semantics 時重開人工 gate；其餘由 agent 完成自"
                    "動工作。"
                ),
            ],
            "formal_execution_enabled": False,
            "gt_used_for_review": False,
        },
        "items": items,
    }
    document["review_payload_sha256"] = content_hash(immutable_document(document))
    write_json(HERE / "decisions.json", document)
    write_json(HERE / "review_template.json", document)
    print(
        json.dumps(
            {"human_decisions": len(items), "payload_sha256": document["review_payload_sha256"]}
        )
    )


if __name__ == "__main__":
    main()
