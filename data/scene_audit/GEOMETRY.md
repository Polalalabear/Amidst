# Read-only geometry follow-up / 唯讀幾何補充分析

[English](#english) | [繁體中文](#繁體中文)

## English

Evidence: [school_v2_geometry_audit.json](school_v2_geometry_audit.json).
The verified source is the same `school_v2.blend` as the inventory audit.
No save or render was performed; source SHA-256, size and mtime remained unchanged.

- This follow-up inspects 370 `group_0*` structural mesh objects, with 25,098 evaluated triangles. It excludes all `Areas` annotation geometry. It is not an exhaustive full-scene navigation audit.
- Main floor candidates are near `z=20.07885` and `z=161.811096`, inferred from world-space upward horizontal faces, connected patches and overlap with floor-labelled AREA volumes. Generic object names do not prevent geometric identification.
- At `z≈20.08`, 15/16 `AREA_1F_*` volumes have at least 0.9 raw XY overlap; at `z≈161.81`, 12/12 `AREA_2F_*` volumes do. The courtyard is the exception, with a large candidate patch near `z=0.000112` requiring further interpretation.
- Raw overlap is a sum of clipped triangle areas, may exceed 1 due to overlapping geometry, and is **not walkability or a probability**. Floor candidates still require obstacle, clearance, headroom and traversal checks.
- Both stair annotation regions have no detected 5–55 degree sloped surfaces or a continuous tread-height sequence. All 81 fixed-grid top-surface samples per region hit `z=161.8111`. This flags a potentially unrepresented/blocked stair connection; it does not prove that no stair exists anywhere outside these regions.
- Do not infer a school cross-floor path from AREA names or connect through an intact slab. School stair configuration remains disabled pending confirmation; generic algorithms and validated same-floor/synthetic fixtures may proceed through M2–M8.

Reproduce without altering the source asset:

```sh
uv run python scripts/run_geometry_audit.py --blender /Applications/Blender.app/Contents/MacOS/blender
```

## 繁體中文

證據：[school_v2_geometry_audit.json](school_v2_geometry_audit.json)。來源與原盤點相同，未儲存或渲染；原檔 SHA-256、大小與修改時間保持不變。

- 檢查 370 個 `group_0*` 結構 Mesh、25,098 個求值後三角面，排除 `Areas` 語意 box；不是全場完整的導航稽核。
- 可由世界座標面法向、連通面與 AREA 樓層範圍辨識兩個主要地板候選：`z≈20.079`、`z≈161.811`，不需要物件一定命名為 floor。
- 一樓 15/16、二樓 12/12 個 AREA 的對應高度 raw XY overlap 至少 0.9。庭院是例外，另有 `z≈0` 大面候選，仍需進一步解讀。
- Raw overlap 是裁切三角面面積加總，重疊幾何可能使比例大於 1；不是可行走率。地板候選仍須障礙、淨空、碰撞與通行條件檢查。
- 兩處樓梯標示區未檢出 5–55 度坡面或連續踏階高度序列，各 81 個固定網格樣本最高表面都在 `z≈161.811`。這表示標示區的樓梯連接可能缺失或被樓板阻擋，不代表全場其他位置一定沒有樓梯。
- 不能直接用樓梯名稱虛構 school 跨樓層連接或穿越樓板。school 樓梯配置在確認前停用；通用演算法及已驗證同樓層／合成 fixture 可繼續完成 M2–M8。
