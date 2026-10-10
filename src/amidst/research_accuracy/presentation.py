"""Review-card presentation only; immutable inference and first exports stay unchanged."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any

from amidst.engineering.access import digest
from amidst.engineering.local_pilot import _save, benchmark_queries
from amidst.research_accuracy.adapter import adapter_contract, load_service


def _display_reference(value: str) -> str:
    import textwrap

    if ":" in value and len(value.rsplit(":", 1)[-1]) >= 24:
        value = value.split(":", 1)[0] + " (ref ..." + value[-12:] + ")"
    return "\n".join(textwrap.wrap(value.replace("_", " "), width=47))


def export_evidence(output: Path, *, directory: str = "cards_review") -> dict[str, Any]:
    if not directory or "/" in directory or ".." in directory:
        raise ValueError("one named evidence directory is required")
    evidence_root = output / directory
    if evidence_root.exists() and any(evidence_root.iterdir()):
        raise ValueError("evidence export requires a new empty evidence directory")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image

    service = load_service(output)
    chosen: dict[tuple[str, str], dict[str, Any]] = {}
    for event in service.events.values():
        key = (event["kind"], event["support_state"])
        previous = chosen.get(key)

        def richness(row: dict[str, Any]) -> tuple[bool, int, int, int]:
            return (
                bool(row["candidates"]),
                len(row["candidates"]),
                len(row["trajectories"]),
                len(row["media_refs"]),
            )

        if previous is None or richness(event) > richness(previous):
            chosen[key] = event
    cards = []
    session = {"session_ref": service.guard.session_ref}
    for (kind, support), event in chosen.items():
        figure = plt.figure(figsize=(15, 7), layout="constrained")
        grid = figure.add_gridspec(2, 5, height_ratios=(1, 1.5))
        for index, ref in enumerate(event["media_refs"]):
            frame = service.frames[ref]
            axis = figure.add_subplot(grid[0, index])
            with Image.open(BytesIO(service.store.media_bytes(service.scope, ref))) as image:
                axis.imshow(image)
            axis.set_title(f"{frame.camera_id} / {frame.timestamp:.2f}s / RGB", fontsize=9)
            axis.axis("off")
        axis3d = figure.add_subplot(grid[1, :3], projection="3d")
        axis3d.set(
            xlabel="x (m)", ylabel="y (m)", zlabel="z (m)", xlim=(0, 16), ylim=(0, 8), zlim=(0, 2.5)
        )
        for i, candidate in enumerate(event["candidates"]):
            points = candidate["polyline"]
            axis3d.plot(
                [p[0] for p in points],
                [p[1] for p in points],
                [p[2] for p in points],
                label=f"INFERRED alternative {i + 1}",
            )
        points = [p["world_position"] for p in event["projected_path"]]
        if points:
            axis3d.scatter(
                [p[0] for p in points],
                [p[1] for p in points],
                [p[2] for p in points],
                color="black",
                s=14,
                label="visible RGB projected contacts",
            )
        axis3d.view_init(elev=32, azim=-60)
        axis3d.legend(fontsize=7, loc="upper left")
        info = figure.add_subplot(grid[1, 3:])
        info.axis("off")
        info.text(
            0,
            1,
            f"{kind}\n{support}\n{event['time_range']} synthetic seconds\n"
            f"{len(event['candidates'])} routes / {len(event['trajectories'])} timings\n"
            "Observed RGB above; derived geometry below.\n"
            "Identity provisional; scores uncalibrated.\n\n"
            + "\n".join(
                _display_reference(v)
                for v in event["conflicts"]
                if not v.startswith("ASSOCIATION_")
            )
            + "\n\n"
            + "Alternative hypotheses and full references remain in replay.",
            va="top",
            fontsize=9,
            wrap=True,
        )
        figure.suptitle("Amidst accuracy v2 / " + kind + " / " + support)
        path = evidence_root / (kind.lower() + "_" + support.lower() + ".png")
        path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(path, dpi=130)
        plt.close(figure)
        start, end = event["time_range"]
        replay = service.call(
            "get_replay",
            session | {"event_ref": event["event_ref"], "timestamp": (start + end) / 2},
        )
        replay_path = path.with_suffix(".replay.json")
        _save(replay_path, replay)
        cards.append(
            {
                "kind": kind,
                "support_state": support,
                "event_ref": event["event_ref"],
                "path": path.relative_to(output).as_posix(),
                "sha256": sha256(path.read_bytes()).hexdigest(),
                "source_frames": event["source_frames"],
                "replay_path": replay_path.relative_to(output).as_posix(),
                "replay_sha256": digest(replay),
            }
        )
    receipt = {
        "schema_version": "accuracy.review-cards.v2",
        "presentation_algorithm_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "cards": cards,
        "actual_source_rgb": True,
        "gt_overlay": False,
        "clock_and_unit": "SYNTHETIC_SECONDS_METRES",
        "contract": adapter_contract(output),
        "indexed_query_telemetry": benchmark_queries(service),
    }
    _save(evidence_root / "receipt.json", receipt)
    return {
        "cards": len(cards),
        "GT_overlay": False,
        "receipt": str(evidence_root / "receipt.json"),
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_evidence(args.source)))
