"""Export a small graph/model comparison from the existing diagnostic image."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOPOLOGY = HERE / "frames/topology_context"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = TOPOLOGY / "topology_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    data_path = TOPOLOGY / "topology_data.json"
    if manifest["data"]["sha256"] != digest(data_path):
        raise ValueError("topology data differs from its source-bound receipt")
    data = json.loads(data_path.read_text())
    if data["result_type"] != "DIAGNOSTIC" or any(
        data[key] is not False
        for key in (
            "gt_used",
            "evaluation_files_read",
            "simulation_recipe_read",
            "physical_authority_changed",
            "formal_execution_enabled",
            "raw_graph_changed",
        )
    ):
        raise ValueError("topology preview must preserve diagnostic authority and GT isolation")
    if data["node_count"] != 2 or data["edge_count"] != 3:
        raise ValueError("preview only represents the existing two-node office graph")
    model = HERE / "frames/motion_context/motion_025.png"
    if (TOPOLOGY / data["model_frame"]["path"]).resolve() != model.resolve():
        raise ValueError("preview requires the existing public/inferred model frame")
    if digest(model) != data["model_frame"]["sha256"]:
        raise ValueError("original model image changed")
    output = TOPOLOGY / "topology_preview.png"
    receipt = TOPOLOGY / "preview_manifest.json"
    if output.exists() or receipt.exists():
        raise ValueError("preview output must be fresh; preserve previous previews")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.image as mpimg
    import matplotlib.patheffects as pe
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(14.4, 8.2), dpi=120, facecolor="white")
    fig.text(0.025, 0.955, "MODEL + TOPOLOGY LOCATION", fontsize=19, weight="bold")
    fig.text(
        0.025,
        0.92,
        "Same N1 / N2 and E1 / E2 / E3 labels in both views | CONFIGURED / DIAGNOSTIC",
        fontsize=11,
        color="#4b6372",
    )
    ax = fig.add_axes((0.025, 0.18, 0.655, 0.715))
    ax.imshow(mpimg.imread(model), extent=(0, 960, 600, 0))
    ax.set_xlim(0, 960)
    ax.set_ylim(600, 0)
    ax.axis("off")
    graph = fig.add_axes((0.73, 0.50, 0.24, 0.35))
    graph.set_title("2 nodes / 3 directed edges", fontsize=13, weight="bold")
    graph.axis("off")
    graph.set_xlim(1380, 1420)
    graph.set_ylim(1994, 2094)
    halo = [pe.withStroke(linewidth=3.5, foreground="white")]
    for edge in data["edges"]:
        points = edge["floor_pixels"]
        xs, ys = zip(*points, strict=True)
        ax.plot(xs, ys, color="#172b38", lw=1.7, zorder=5, path_effects=halo)
        middle = len(points) // 2
        a, b = points[middle - 1], points[middle]
        dx = {"E1": 8, "E2": -36, "E3": 10}[edge["alias"]]
        ax.text(
            (a[0] + b[0]) / 2 + dx,
            (a[1] + b[1]) / 2 + 4,
            edge["alias"],
            fontsize=12,
            weight="bold",
            zorder=8,
            bbox={"facecolor": "white", "edgecolor": "#172b38", "pad": 2},
        )
        ax.annotate(
            "",
            xy=b,
            xytext=(a[0] * 0.45 + b[0] * 0.55, a[1] * 0.45 + b[1] * 0.55),
            arrowprops={"arrowstyle": "->", "lw": 1.7, "color": "#172b38"},
            zorder=6,
        )
        raw = edge["raw_polyline_bu"]
        graph.plot([p[0] for p in raw], [p[1] for p in raw], color="#172b38", lw=1.6)
        for point in points[1:-1]:
            ax.scatter(point[0], point[1], s=34, facecolor="white", edgecolor="#172b38", zorder=8)
        for point in raw[1:-1]:
            graph.scatter(point[0], point[1], s=28, facecolor="white", edgecolor="#172b38")
        graph.annotate(
            "",
            xy=(raw[-1][0], raw[-1][1]),
            xytext=(raw[-2][0], raw[-2][1]),
            arrowprops={"arrowstyle": "->", "lw": 1.5, "color": "#172b38"},
        )
        a, b = raw[middle - 1], raw[middle]
        graph.text(
            (a[0] + b[0]) / 2 + {"E1": 1, "E2": -5, "E3": 1}[edge["alias"]],
            (a[1] + b[1]) / 2,
            edge["alias"],
            fontsize=11,
            weight="bold",
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 1},
        )
    for node in data["nodes"]:
        x, y = node["floor_pixel"]
        ax.scatter(x, y, s=76, color="#172b38", edgecolor="white", linewidth=1.6, zorder=9)
        ax.text(
            x - 42 if node["alias"] == "N1" else x + 13,
            y + 13,
            node["alias"],
            fontsize=13,
            weight="bold",
            zorder=9,
            bbox={"facecolor": "white", "edgecolor": "#172b38", "pad": 2},
        )
        p = node["raw_position_bu"]
        graph.scatter(p[0], p[1], s=64, color="#172b38", zorder=10)
        graph.text(p[0] + 2, p[1] - 2, node["alias"], fontsize=11, weight="bold")
    fig.text(
        0.725,
        0.445,
        "N1  projected_departure\n      FRONT last observation: t = 4.0 s\n"
        "N2  projected_recovery\n      REAR recovery observation: t = 9.0 s\n\n"
        "E1  pilot_route:direct\nE2  pilot_route:left\nE3  pilot_route:right\n\n"
        "Filled circles = graph nodes\nHollow circles = polyline vertices\n"
        "The four corners are not extra nodes.",
        fontsize=10,
        linespacing=1.5,
        va="top",
        color="#172b38",
    )
    fig.text(
        0.025,
        0.15,
        "Model overlay: pending HR-02 floor mapping; XY unchanged, Z offset = 55.049998 BU.\n"
        "Original graph remains at landmark Z = 75.128848 BU. No inference/geometry changed.\n"
        "E2 remains in the raw graph; its separate floor-support review rejects clearance.\n"
        "All three are configured hypotheses, not certified school routes or Case 2 branches.",
        fontsize=10,
        linespacing=1.5,
        color="#4b6372",
        va="top",
    )
    fig.savefig(output, dpi=120, facecolor="white", metadata={"Software": "Amidst review"})
    plt.close(fig)
    document = {
        "schema_version": "phase1-topology-static-preview-v1",
        "result_type": "DIAGNOSTIC",
        "gt_used": False,
        "physical_authority_changed": False,
        "raw_graph_changed": False,
        "topology_data_sha256": digest(data_path),
        "original_model_sha256": digest(model),
        "renderer_sha256": digest(Path(__file__)),
        "artifact": {"path": output.name, "bytes": output.stat().st_size, "sha256": digest(output)},
    }
    receipt.write_text(json.dumps(document, indent=2) + "\n")
    print(json.dumps(document["artifact"]))


if __name__ == "__main__":
    main()
