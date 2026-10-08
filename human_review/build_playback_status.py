"""Build a view-only progress snapshot from existing, hash-pinned receipts.

This display adapter does not apply decisions, run inference, recertify a scope,
or turn historical diagnostic media into formal dataset evidence. The source
checkpoint and validation date describe the receipts, not a new research run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_SHA = "883204af854bed301506b39d63ccb33312b79ff2"
SOURCE_FILES = {
    "validation": (
        "data/finalization/recovery_checkpoint_20261008/validation.json",
        "5562059a472d3b629a3f2a2cf8173a582490a037701d0e5b6445eaad995ddf96",
    ),
    "dataset": (
        "data/finalization/recovery_checkpoint_20261008/dataset_acceptance.json",
        "2a6787eeef91087c72c95ec3c95d2f4eb0acca0264c005a742b20d6c7516535e",
    ),
    "reproduction": (
        "data/finalization/recovery_checkpoint_20261008/reproduction.json",
        "30c882781afffdebcb85b26f5c7a84623939af484f89899317982daf9fef3bb9",
    ),
    "corridor_regeneration": (
        "data/finalization/recovery_checkpoint_20261008/corridor_result.json",
        "4bfd01591901d48a65015522a4af79941820071d4db6c6ec48b44987f265f91e",
    ),
    "review_application": (
        "data/finalization/human_review_applied_v1/review_receipt.json",
        "efedd2b4a8ddd881065cb3a0b1c58e9624c50be1f41235efa6f9af72cda9dbb8",
    ),
    "office_certificate": (
        "data/finalization/human_review_applied_v1/certificate_result.json",
        "7c5bfd112b50a082d70284c89242c54311f722ce507b9ca1ce22a871dfb04c81",
    ),
    "corridor_application": (
        "data/finalization/reviewed_corridor_scope_application_v1/result.json",
        "29cf95e571367ac63b623c3e7387a9cf6f870c247764fe481e0a0fc38e97e716",
    ),
    "decisions": (
        "human_review/decisions.json",
        "adf08bafb98f21006041beab990036d124a5f4c9efca12e40d89e4128d95a5a9",
    ),
}


def _receipts(root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    documents: dict[str, Any] = {}
    sources = []
    for name, (relative_path, expected_hash) in SOURCE_FILES.items():
        raw = (root / relative_path).read_bytes()
        actual_hash = hashlib.sha256(raw).hexdigest()
        if actual_hash != expected_hash:
            raise ValueError(f"Status receipt differs from {CHECKPOINT_SHA}: {relative_path}")
        document = json.loads(raw)
        if not isinstance(document, dict):
            raise ValueError(f"Status receipt must be an object: {relative_path}")
        documents[name] = document
        sources.append({"path": relative_path, "sha256": actual_hash})
    return documents, sources


def build_status(root: Path) -> dict[str, Any]:
    """Return the bounded public progress display for the pinned checkpoint."""
    receipts, sources = _receipts(root)
    validation = receipts["validation"]
    dataset = receipts["dataset"]
    reproduction = receipts["reproduction"]
    corridor = receipts["corridor_application"]
    office = receipts["office_certificate"]["result"]
    limits = validation["limits"]
    run = validation["fresh_existing_office_run"]
    engineering = validation["engineering_validation"]
    suite = engineering["final_full_suite"]
    decisions = receipts["decisions"]["items"]
    approved = sum(item["decision"] == "APPROVE" for item in decisions)
    approved_cells = sum(
        cell["status"] == "APPROVED_RESTRICTED_MULTI_HUMAN_REVIEWED_SCOPE"
        for cell in corridor["cell_checks"]
    )
    return {
        "schema_version": "phase1-viewer-status-v1",
        "mode": "VIEW_ONLY",
        "as_of": "2026-10-08",
        "recorded_at": validation["recorded_at"],
        "source_sha": validation["source_scene"]["sha256"],
        "source_commit": CHECKPOINT_SHA,
        "checkpoint_sha": CHECKPOINT_SHA,
        "phase1": {
            "status": limits["phase1"],
            "label": "Phase 1 收尾中",
            "detail": "Office 局部成果已重跑；Case 2 與 Case 3 繞路／搜尋成長尚待完成。",
            "full_exit_complete": limits["original_full_exit_complete"],
            "freeze_allowed": limits["freeze_allowed"],
        },
        "human_approvals": {
            "approved": approved,
            "total": len(decisions),
            "status": "APPROVED_AND_APPLIED",
            "label": f"原人工決策 {approved}/{len(decisions)} 已核准並套用",
            "detail": "HR01–HR04 已套用；reference movement 與精確 corridor scope 亦已核准。",
            "office_certificate_status": receipts["review_application"]["certificate_status"],
            "profiles": [
                {
                    "id": item["id"],
                    "decision": item["decision"],
                    "selected_option": item["selected_option"],
                }
                for item in decisions
            ],
        },
        "physical": {
            "status": "PARTIAL_APPROVED",
            "label": "局部物理範圍已認證",
            "detail": (
                f"Office 局部 certificate PASS；corridor {approved_cells}/"
                f"{len(corridor['cell_checks'])} cells 通過，union 重建 PASS。"
                "認證僅限核准範圍。"
            ),
            "office_certificate_status": office["status"],
            "corridor_certificate_status": corridor["status"],
            "corridor_regeneration": receipts["corridor_regeneration"]["status"],
            "corridor_case_readiness": receipts["corridor_regeneration"]["case_readiness"],
        },
        "cases": [
            {
                "id": "case1",
                "label": "Case 1 · 唯一路徑",
                "status": dataset["case_results"]["case1"],
                "detail": "核准 Office 局部正式執行完成，包含 A/B/C、評估與 demo。",
            },
            {
                "id": "case2",
                "label": "Case 2 · 分支 Top-K",
                "status": dataset["case_results"]["case2"],
                "detail": (
                    "新 corridor 已核准；scoped adapters、same-camera HOLD、"
                    "完整 route inventory、portal 證據與 fresh run 尚待完成。"
                ),
            },
            {
                "id": "case3",
                "label": "Case 3 · 長 GAP／時間歧義",
                "status": dataset["case_results"]["case3"],
                "detail": "Office 時間分量正式執行完成；繞路、候選成長與完整壓力驗證未完成。",
                "detour_growth_status": limits["case3_detour_growth"],
                "full_stress_complete": dataset["case3_full_stress_exit_complete"],
            },
        ],
        "checks": [
            {
                "label": "Dataset／A・B・C／ablations",
                "status": "PASS_SCOPED",
                "detail": (
                    f"既有 Office {run['sampling_fps']} Hz 重建；"
                    f"{run['benchmark_row_count']} 列 baseline、"
                    f"{run['ablation_row_count']} 列 ablation。"
                    "Case 2 保留 BLOCKED，尚未形成全案例 dataset。"
                ),
            },
            {
                "label": "GT isolation",
                "status": reproduction["gt_poison_status"],
                "detail": "已可執行的 Office 案例：GT poison 不改 inference，會改 evaluation。",
            },
            {
                "label": "重複執行／順序／終止",
                "status": reproduction["repeat_status"],
                "detail": "Office 案例的 candidate ordering 與 termination 比對通過。",
            },
            {
                "label": "Fresh-process replay",
                "status": reproduction["fresh_process_status"],
                "detail": "已可執行的 Office 案例通過；新 corridor 完整交付仍未重跑。",
            },
            {
                "label": "新 scope 完整 fresh checkout",
                "status": "NOT_RUN",
                "detail": "本次恢復尚未完成新 corridor dataset／報告／demo 的獨立完整比對。",
            },
            {
                "label": "Rerun 播放證據",
                "status": "PASS_SCOPED",
                "detail": "Case 1、Case 3 時間分量兩份 RRD／PNG 已由 reader 驗證。",
            },
            {
                "label": "來源 checkpoint 工程驗證",
                "status": suite["status"],
                "detail": (
                    f"2026-10-08 既有紀錄：{suite['passed']} passed／"
                    f"{suite['failed']} failed／{suite['skipped']} skipped；"
                    "Ruff、mypy 與 source CLI strict mypy PASS。此為來源 checkpoint 紀錄。"
                ),
            },
        ],
        "notes": [
            "此介面僅供查看與同步播放，沒有人工決策或套用入口。",
            "畫面沿用歷史 DIAGNOSTIC 審查素材；播放不代表新的正式模擬或 benchmark。",
            "狀態來自列出的固定 checkpoint receipts；本輪 UI 驗證另行記錄。",
            "Case 3 的時間分量完成，不代表 detour-growth／full-stress Exit Gate 完成。",
            "GT、重複執行與 fresh-process PASS 僅涵蓋當時已可執行的 Office 案例。",
            "Case 4 DEFERRED；Phase 2 FROZEN；Phase 1 尚未允許 freeze。",
        ],
        "reproduction_scope": reproduction["scope"],
        "media_status": "HISTORICAL_DIAGNOSTIC_REVIEW_VISUALS",
        "sources": sources,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.root / "human_review/playback/status_snapshot.json"
    status = build_status(args.root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
