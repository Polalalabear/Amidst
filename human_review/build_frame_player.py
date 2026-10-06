"""Create an offline player for the rendered, GT-free Blender review sequence."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT / "human_review" / "frames"


def main() -> None:
    manifest = json.loads((FRAMES / "visual_manifest.json").read_text())
    records = manifest["frames"]
    assert len(records) >= 40 and manifest["gt_used"] is False
    encoded = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    html = (FRAMES / "player_template.html").read_text()
    (FRAMES / "player.html").write_text(html.replace("__RECORDS__", encoded))
    print("Generated offline review player:", FRAMES / "player.html")


if __name__ == "__main__":
    main()
