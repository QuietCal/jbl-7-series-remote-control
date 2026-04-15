from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


CONFIG_PATH = Path("lsr7_controller_config.json")
# Legacy migration-only fallback from the earlier HiQnet investigation build.
LEGACY_CONFIG_PATH = Path("hiqnet_config.json")
TREE_CACHE_PATH = Path("lsr7_tree_cache.json")
TREE_SUMMARY_PATH = Path("LSR7_TREE_SUMMARY.md")


@dataclass
class AppConfig:
    speaker_host: str = "192.168.2.145"
    network_interface: str = ""
    snapshot_root: str = "\\\\this"
    theme_mode: str = "light"
    instant_update: bool = False
    confirm_writes: bool = True
    auto_refresh_after_write: bool = True
    debug_protocol: bool = False
    notes: str = "Primary control path is the JBL LSR7 WebSocket API on tcp/19273."

    def as_dict(self) -> dict:
        return {
            "speaker_host": self.speaker_host,
            "network_interface": self.network_interface,
            "snapshot_root": self.snapshot_root,
            "theme_mode": self.theme_mode,
            "instant_update": self.instant_update,
            "confirm_writes": self.confirm_writes,
            "auto_refresh_after_write": self.auto_refresh_after_write,
            "debug_protocol": self.debug_protocol,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        speaker_host = str(data.get("speaker_host") or data.get("last_target_ip") or "192.168.2.145")
        snapshot_root = str(data.get("snapshot_root") or "\\\\this")
        notes = str(data.get("notes", "Primary control path is the JBL LSR7 WebSocket API on tcp/19273."))
        if notes == "Edit the mapping file as controls are confirmed.":
            notes = "Primary control path is the JBL LSR7 WebSocket API on tcp/19273."
        return cls(
            speaker_host=speaker_host,
            network_interface=str(data.get("network_interface") or ""),
            snapshot_root=snapshot_root,
            theme_mode=str(data.get("theme_mode") or "light"),
            instant_update=bool(data.get("instant_update", False)),
            confirm_writes=bool(data.get("confirm_writes", True)),
            auto_refresh_after_write=bool(data.get("auto_refresh_after_write", True)),
            debug_protocol=bool(data.get("debug_protocol", False)),
            notes=notes,
        )


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    if path == CONFIG_PATH and not path.exists() and LEGACY_CONFIG_PATH.exists():
        path = LEGACY_CONFIG_PATH
    if not path.exists():
        return AppConfig()
    with path.open("r", encoding="utf-8") as handle:
        return AppConfig.from_dict(json.load(handle))


def save_config(config: AppConfig, path: Path = CONFIG_PATH) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config.as_dict(), handle, indent=2)


def load_or_create_config() -> AppConfig:
    config = load_config()
    save_config(config)
    return config


def save_tree_cache(payload: dict, path: Path = TREE_CACHE_PATH) -> Path:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


def merge_tree_cache(payload: dict, path: Path = TREE_CACHE_PATH) -> Path:
    existing = load_tree_cache(path) or {}
    merged_tree = dict(existing.get("tree", {}))
    merged_tree.update(payload.get("tree", {}))

    roots = list(dict.fromkeys([*(existing.get("roots", [])), existing.get("root"), *(payload.get("roots", [])), payload.get("root")]))
    roots = [root for root in roots if root]

    merged_payload = dict(existing)
    merged_payload.update(payload)
    merged_payload["root"] = "\\\\this" if roots else payload.get("root", existing.get("root", "\\\\this"))
    merged_payload["roots"] = roots
    merged_payload["tree"] = merged_tree

    existing_step_stats = list(existing.get("step_stats", []))
    new_step_stats = list(payload.get("step_stats", []))
    if new_step_stats:
        merged_payload["step_stats"] = (existing_step_stats + new_step_stats)[-5000:]

    with path.open("w", encoding="utf-8") as handle:
        json.dump(merged_payload, handle, indent=2)
    return path


def load_tree_cache(path: Path = TREE_CACHE_PATH) -> dict | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
