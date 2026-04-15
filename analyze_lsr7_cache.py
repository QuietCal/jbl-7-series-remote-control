from __future__ import annotations

import json
from pathlib import Path
import sys

from lsr7_tree_tools import tree_stats, write_tree_summary


def main() -> None:
    cache_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("lsr7_tree_cache.json")
    if not cache_path.exists():
        raise SystemExit(f"Missing cache file: {cache_path}")
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    tree = payload.get("tree", {})
    step_stats = payload.get("step_stats", [])
    host = str(payload.get("host") or "?")
    root = str(payload.get("root") or "\\\\this")
    stats = tree_stats(tree, step_stats=step_stats)
    write_tree_summary(host, root, tree, "LSR7_TREE_SUMMARY.md", step_stats=step_stats)
    report = {
        "host": host,
        "root": root,
        "node_count": stats["node_count"],
        "kind_counts": stats["kind_counts"],
        "family_counts": stats["family_counts"],
        "explosive_prefixes": stats["explosive_prefixes"],
        "branch_sizes": stats["branch_sizes"],
    }
    Path("lsr7_cache_analysis.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
