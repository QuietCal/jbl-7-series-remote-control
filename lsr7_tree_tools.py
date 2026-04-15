from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path


def family_for_path(path: str) -> str:
    parts = [part for part in path.split("\\") if part]
    for family in ("SV", "AT", "DA"):
        if family in parts:
            return family
    return "other"


def branch_prefix(path: str) -> str:
    parts = [part for part in path.split("\\") if part]
    if not parts:
        return path
    prefix: list[str] = []
    if parts[0] == "this":
        prefix = ["", "", "this"]
        parts = parts[1:]
    for part in parts:
        prefix.append(part)
        if part in {"SV", "AT", "DA"}:
            break
    return "\\".join(prefix) if prefix else path


def tree_stats(tree: dict[str, dict], step_stats: list[dict] | None = None) -> dict[str, object]:
    kind_counts = Counter(node.get("kind", "unknown") for node in tree.values())
    family_counts = Counter(node.get("family") or family_for_path(path) for path, node in tree.items())
    depth_counts = Counter(path.count("\\") - 1 for path in tree)
    top_level_children = tree.get("\\\\this", {}).get("children", [])
    branch_sizes: dict[str, int] = {}
    for child in top_level_children:
        prefix = f"\\\\this\\{child}"
        branch_sizes[prefix] = sum(1 for path in tree if path == prefix or path.startswith(prefix + "\\"))

    prefix_counts = Counter(branch_prefix(path) for path in tree)
    queue_deltas = Counter()
    explosive = Counter()
    if step_stats:
        for stat in step_stats:
            queue_deltas[stat.get("prefix", "")] += int(stat.get("queue_delta", 0))
            if int(stat.get("queue_delta", 0)) > 0:
                explosive[stat.get("prefix", "")] += int(stat.get("queue_delta", 0))

    return {
        "node_count": len(tree),
        "kind_counts": dict(kind_counts),
        "family_counts": dict(family_counts),
        "depth_counts": dict(sorted(depth_counts.items())),
        "branch_sizes": dict(sorted(branch_sizes.items())),
        "prefix_counts": dict(prefix_counts.most_common(20)),
        "queue_delta_by_prefix": dict(queue_deltas.most_common(20)),
        "explosive_prefixes": dict(explosive.most_common(20)),
    }


def summarize_tree_markdown(host: str, root: str, tree: dict[str, dict], *, step_stats: list[dict] | None = None) -> str:
    stats = tree_stats(tree, step_stats=step_stats)
    lines: list[str] = [
        "# LSR7 Tree Summary",
        "",
        f"Host: `{host}`",
        f"Root: `{root}`",
        "",
        "## Counts",
        "",
        f"- Total nodes: `{stats['node_count']}`",
    ]
    for kind, count in stats["kind_counts"].items():
        lines.append(f"- {kind}: `{count}`")

    lines.extend(["", "## Family Counts", ""])
    for family, count in stats["family_counts"].items():
        lines.append(f"- {family}: `{count}`")

    lines.extend(
        [
            "",
            "## Queue Growth Note",
            "",
            "- The queue can legitimately grow during a healthy crawl when a single branch expands into many children.",
            "- A positive queue delta means discovery is outpacing consumption for that branch.",
            "- This is most common in deep `DA` and indexed parameter subtrees.",
        ]
    )

    lines.extend(["", "## Top-Level Branch Sizes", ""])
    for branch, count in stats["branch_sizes"].items():
        lines.append(f"- `{branch}`: `{count}`")

    lines.extend(["", "## High-Value GUI Candidate Branches", ""])
    for candidate in [
        "\\\\this\\Node\\InputMixer\\SV",
        "\\\\this\\Node\\SpeakerGain\\SV",
        "\\\\this\\Node\\RoomDelay\\SV",
        "\\\\this\\Node\\RoomEQ\\SV",
        "\\\\this\\Node\\Limiter_Lo\\SV",
        "\\\\this\\Node\\Limiter_Hi\\SV",
        "\\\\this\\Node\\LSR7Hardware\\SV",
        "\\\\this\\Presets\\Presets\\SV",
    ]:
        count = sum(1 for path in tree if path == candidate or path.startswith(candidate + "\\"))
        if count:
            lines.append(f"- `{candidate}`: `{count}` nodes")

    lines.extend(["", "## Top Queue-Expanding Prefixes", ""])
    for prefix, delta in stats["explosive_prefixes"].items():
        if not prefix:
            continue
        lines.append(f"- `{prefix}`: `+{delta}` queued descendants")

    lines.extend(["", "## Deferred / Noisy Prefixes", ""])
    noisy = [path for path, node in tree.items() if node.get("kind") == "deferred_error"]
    if noisy:
        for path in noisy[:20]:
            lines.append(f"- `{path}`")
    else:
        lines.append("- None recorded in the current cache")

    lines.extend(["", "## Parameter Samples", ""])
    samples_by_prefix: dict[str, list[str]] = defaultdict(list)
    for path, node in tree.items():
        if node.get("kind") != "parameter":
            continue
        prefix = branch_prefix(path)
        if len(samples_by_prefix[prefix]) < 8:
            samples_by_prefix[prefix].append(path)
    for prefix in sorted(samples_by_prefix):
        lines.append("")
        lines.append(f"### `{prefix}`")
        lines.append("")
        for sample in samples_by_prefix[prefix]:
            value = tree[sample].get("snapshot", {}).get("value_text")
            if value:
                lines.append(f"- `{sample}` -> `{value}`")
            else:
                lines.append(f"- `{sample}`")
    lines.append("")
    return "\n".join(lines)


def write_tree_summary(host: str, root: str, tree: dict[str, dict], output_path: Path | str, *, step_stats: list[dict] | None = None) -> Path:
    output = Path(output_path)
    output.write_text(summarize_tree_markdown(host, root, tree, step_stats=step_stats), encoding="utf-8")
    return output
