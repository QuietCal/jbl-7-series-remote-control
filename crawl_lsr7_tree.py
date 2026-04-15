from __future__ import annotations

import json
from pathlib import Path
import sys
import time

from lsr7_storage import TREE_CACHE_PATH, TREE_SUMMARY_PATH, save_tree_cache
from lsr7_tree_tools import write_tree_summary
from lsr7_ws import LSR7WebSocketClient


def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.2.145"
    root = sys.argv[2] if len(sys.argv) > 2 else "\\\\this"
    started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    with LSR7WebSocketClient(host, timeout=5.0) as client:
        identity = client.get_identity()
        tree = client.enumerate_tree(root=root)
    payload = {
        "host": host,
        "root": root,
        "started_at": started_at,
        "identity": identity,
        "tree": tree,
    }
    save_tree_cache(payload, TREE_CACHE_PATH)
    write_tree_summary(host, root, tree, TREE_SUMMARY_PATH)
    print(json.dumps({"cache": str(TREE_CACHE_PATH), "summary": str(TREE_SUMMARY_PATH), "nodes": len(tree)}, indent=2))


if __name__ == "__main__":
    main()
