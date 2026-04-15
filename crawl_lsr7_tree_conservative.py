from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

from lsr7_storage import TREE_CACHE_PATH, TREE_SUMMARY_PATH, merge_tree_cache
from lsr7_tree_tools import write_tree_summary
from lsr7_ws import LSR7WebSocketClient, META_CHILDREN


CHECKPOINT_PATH = Path("lsr7_tree_checkpoint.json")
GUI_DA_ALLOWLIST = [
    "\\\\this\\Node\\Limiter_Lo\\DA",
    "\\\\this\\Node\\Limiter_Hi\\DA",
    "\\\\this\\Node\\CompLowpass_Lo\\DA",
    "\\\\this\\Node\\CompHighpass_Hi\\DA",
    "\\\\this\\Node\\CompDelay_Hi\\DA",
    "\\\\this\\Node\\CompGain_Hi\\DA",
    "\\\\this\\Node\\AnalogInputMeter\\DA",
    "\\\\this\\Node\\AES1InputMeter\\DA",
    "\\\\this\\Node\\AES2InputMeter\\DA",
    "\\\\this\\Node\\OutputHiMeter\\DA",
    "\\\\this\\Node\\OutputLoMeter\\DA",
    "\\\\this\\Node\\ChannelInputMeter\\DA",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Conservative JBL LSR7 tree crawler")
    parser.add_argument("host", nargs="?", default="192.168.2.145")
    parser.add_argument("root", nargs="?", default="\\\\this")
    parser.add_argument("pause_seconds", nargs="?", type=float, default=1.5)
    parser.add_argument("timeout", nargs="?", type=float, default=5.0)
    parser.add_argument("max_failures", nargs="?", type=int, default=2)
    parser.add_argument("batch_size", nargs="?", type=int, default=15)
    parser.add_argument("batch_cooldown", nargs="?", type=float, default=20.0)
    parser.add_argument("max_steps", nargs="?", type=int, default=0)
    parser.add_argument("--mode", choices=["full", "sv_at_only", "sv_first"], default=None)
    parser.add_argument("--include-prefix", action="append", default=[])
    parser.add_argument("--exclude-prefix", action="append", default=[])
    return parser


def is_parameter_node(children: list[str]) -> bool:
    return bool(children) and set(children).issubset(META_CHILDREN)


def load_checkpoint() -> dict:
    if not CHECKPOINT_PATH.exists():
        return {}
    return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))


def save_checkpoint(payload: dict) -> None:
    CHECKPOINT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def normalize_path(path: str) -> str:
    return path.rstrip("\\")


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


def path_matches_prefix(path: str, prefixes: list[str]) -> bool:
    normalized = normalize_path(path)
    for prefix in prefixes:
        prefix_norm = normalize_path(prefix)
        if normalized == prefix_norm or normalized.startswith(prefix_norm + "\\"):
            return True
    return False


def mode_defaults(mode: str) -> tuple[list[str], list[str]]:
    if mode == "sv_at_only":
        return (list(GUI_DA_ALLOWLIST), ["\\\\this\\Node\\DA", "\\\\this\\Presets\\DA"])
    if mode == "sv_first":
        return ([], ["\\\\this\\Node\\DA", "\\\\this\\Presets\\DA", "\\\\this\\Node\\AT", "\\\\this\\Presets\\AT"])
    return ([], [])


def should_expand(path: str, mode: str, include_prefixes: list[str], exclude_prefixes: list[str]) -> bool:
    family = family_for_path(path)
    if path_matches_prefix(path, include_prefixes):
        return True
    if path_matches_prefix(path, exclude_prefixes):
        return False
    if mode == "sv_at_only" and family == "DA":
        return False
    if mode == "sv_first" and family in {"DA", "AT"}:
        return False
    return True


def single_list_children(host: str, path: str, timeout: float) -> list[str] | None:
    with LSR7WebSocketClient(host, timeout=timeout) as client:
        return client.try_list_children(path)


def single_read_parameter(host: str, path: str, timeout: float) -> dict:
    with LSR7WebSocketClient(host, timeout=timeout) as client:
        return client.get_parameter_snapshot(path).as_dict()


def persist_state(
    *,
    host: str,
    root: str,
    started_at: str,
    tree: dict,
    queue: list[str],
    seen: set[str],
    failures: dict[str, int],
    mode: str,
    include_prefixes: list[str],
    exclude_prefixes: list[str],
    last_error: str | None,
    failed_at: str | None,
    step_stats: list[dict],
) -> None:
    payload = {
        "host": host,
        "root": root,
        "started_at": started_at,
        "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "include_prefixes": include_prefixes,
        "exclude_prefixes": exclude_prefixes,
        "tree": tree,
        "step_stats": step_stats,
    }
    merge_tree_cache(payload, TREE_CACHE_PATH)
    merged_cache = json.loads(TREE_CACHE_PATH.read_text(encoding="utf-8"))
    write_tree_summary(
        host,
        merged_cache.get("root", root),
        merged_cache.get("tree", {}),
        TREE_SUMMARY_PATH,
        step_stats=merged_cache.get("step_stats", step_stats),
    )
    save_checkpoint(
        {
            "host": host,
            "root": root,
            "queue": queue,
            "seen": sorted(seen),
            "tree": tree,
            "failures": failures,
            "started_at": started_at,
            "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_error": last_error,
            "failed_at": failed_at,
            "mode": mode,
            "include_prefixes": include_prefixes,
            "exclude_prefixes": exclude_prefixes,
            "step_stats": step_stats,
        }
    )


def main() -> None:
    args = build_parser().parse_args()
    checkpoint = load_checkpoint()

    requested_mode = args.mode
    default_mode = requested_mode or "full"
    include_defaults, exclude_defaults = mode_defaults(default_mode)
    include_prefixes = list(dict.fromkeys(include_defaults + args.include_prefix))
    exclude_prefixes = list(dict.fromkeys(exclude_defaults + args.exclude_prefix))

    if checkpoint.get("host") == args.host and checkpoint.get("root") == args.root:
        queue = list(checkpoint.get("queue", []))
        seen = set(checkpoint.get("seen", []))
        tree = dict(checkpoint.get("tree", {}))
        failures = dict(checkpoint.get("failures", {}))
        started_at = str(checkpoint.get("started_at") or time.strftime("%Y-%m-%d %H:%M:%S"))
        mode = str(checkpoint.get("mode") or default_mode)
        include_prefixes = list(checkpoint.get("include_prefixes", include_prefixes))
        exclude_prefixes = list(checkpoint.get("exclude_prefixes", exclude_prefixes))
        step_stats = list(checkpoint.get("step_stats", []))
        if requested_mode and requested_mode != mode:
            mode = requested_mode
            include_defaults, exclude_defaults = mode_defaults(mode)
            include_prefixes = list(dict.fromkeys(include_defaults + args.include_prefix))
            exclude_prefixes = list(dict.fromkeys(exclude_defaults + args.exclude_prefix))
            queue = [path for path in queue if should_expand(path, mode, include_prefixes, exclude_prefixes)]
            print(f"MODE_SWITCH old={checkpoint.get('mode')} new={mode} queue={len(queue)}")
    else:
        queue = [args.root]
        seen: set[str] = set()
        tree: dict[str, dict] = {}
        failures = {}
        started_at = time.strftime("%Y-%m-%d %H:%M:%S")
        mode = default_mode
        step_stats: list[dict] = []

    steps = 0

    while queue:
        if args.max_steps and steps >= args.max_steps:
            persist_state(
                host=args.host,
                root=args.root,
                started_at=started_at,
                tree=tree,
                queue=queue,
                seen=seen,
                failures=failures,
                mode=mode,
                include_prefixes=include_prefixes,
                exclude_prefixes=exclude_prefixes,
                last_error=None,
                failed_at=None,
                step_stats=step_stats,
            )
            print(f"PAUSE steps={steps} nodes={len(tree)} queue={len(queue)} mode={mode}")
            return

        path = queue.pop(0)
        if path in seen:
            continue
        prefix = branch_prefix(path)
        family = family_for_path(path)
        print(f"READ {path}")
        queue_before = len(queue) + 1
        try:
            children = single_list_children(args.host, path, args.timeout)
            seen.add(path)
            node_kind = "error"
            child_count = 0
            enqueued = 0

            if children is None:
                tree[path] = {"kind": "error", "family": family}
            else:
                clean_children = [child for child in children if child]
                child_count = len(clean_children)
                tree[path] = {"kind": "node", "children": clean_children, "family": family}
                node_kind = "node"
                if is_parameter_node(clean_children):
                    snapshot = single_read_parameter(args.host, path, args.timeout)
                    tree[path] = {"kind": "parameter", "children": clean_children, "snapshot": snapshot, "family": family}
                    node_kind = "parameter"
                elif should_expand(path, mode, include_prefixes, exclude_prefixes):
                    for child in clean_children:
                        if child == "*":
                            continue
                        child_path = path + "\\" + child
                        if child_path not in seen:
                            queue.append(child_path)
                            enqueued += 1
                else:
                    tree[path]["expansion"] = "filtered"
                    node_kind = "filtered_node"

            queue_after = len(queue)
            delta = queue_after - queue_before
            stat = {
                "path": path,
                "kind": node_kind,
                "family": family,
                "prefix": prefix,
                "children": child_count,
                "enqueued": enqueued,
                "queue_before": queue_before,
                "queue_after": queue_after,
                "queue_delta": delta,
                "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            step_stats.append(stat)

            persist_state(
                host=args.host,
                root=args.root,
                started_at=started_at,
                tree=tree,
                queue=queue,
                seen=seen,
                failures=failures,
                mode=mode,
                include_prefixes=include_prefixes,
                exclude_prefixes=exclude_prefixes,
                last_error=None,
                failed_at=None,
                step_stats=step_stats,
            )

            steps += 1
            print(
                f"OK {path} kind={node_kind} family={family} children={child_count} enqueued={enqueued} "
                f"delta={delta:+d} queue={len(queue)} nodes={len(tree)} prefix={prefix}"
            )
            time.sleep(args.pause_seconds)
            if args.batch_size > 0 and steps % args.batch_size == 0:
                print(f"COOLDOWN {args.batch_cooldown}s after {steps} steps")
                time.sleep(args.batch_cooldown)
        except Exception as exc:
            failures[path] = int(failures.get(path, 0)) + 1
            if failures[path] >= args.max_failures:
                seen.add(path)
                tree[path] = {
                    "kind": "deferred_error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "failures": failures[path],
                    "family": family,
                }
                step_stats.append(
                    {
                        "path": path,
                        "kind": "deferred_error",
                        "family": family,
                        "prefix": prefix,
                        "children": 0,
                        "enqueued": 0,
                        "queue_before": queue_before,
                        "queue_after": len(queue),
                        "queue_delta": len(queue) - queue_before,
                        "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                persist_state(
                    host=args.host,
                    root=args.root,
                    started_at=started_at,
                    tree=tree,
                    queue=queue,
                    seen=seen,
                    failures=failures,
                    mode=mode,
                    include_prefixes=include_prefixes,
                    exclude_prefixes=exclude_prefixes,
                    last_error=f"{type(exc).__name__}: {exc}",
                    failed_at=path,
                    step_stats=step_stats,
                )
                print(f"SKIP {path}: {type(exc).__name__}: {exc} failures={failures[path]}")
                time.sleep(args.pause_seconds)
                continue

            persist_state(
                host=args.host,
                root=args.root,
                started_at=started_at,
                tree=tree,
                queue=[path] + queue,
                seen=seen,
                failures=failures,
                mode=mode,
                include_prefixes=include_prefixes,
                exclude_prefixes=exclude_prefixes,
                last_error=f"{type(exc).__name__}: {exc}",
                failed_at=path,
                step_stats=step_stats,
            )
            print(f"FAIL {path}: {type(exc).__name__}: {exc}")
            raise

    persist_state(
        host=args.host,
        root=args.root,
        started_at=started_at,
        tree=tree,
        queue=[],
        seen=seen,
        failures=failures,
        mode=mode,
        include_prefixes=include_prefixes,
        exclude_prefixes=exclude_prefixes,
        last_error=None,
        failed_at=None,
        step_stats=step_stats,
    )
    print(f"DONE nodes={len(tree)} mode={mode}")


if __name__ == "__main__":
    main()
