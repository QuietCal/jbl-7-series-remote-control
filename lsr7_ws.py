from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import os
from pathlib import Path
import socket
import struct
from typing import Any, Callable


WS_PORT = 19273
META_CHILDREN = {"$", "f", "%", "r", "*", "Min", "Max", "Sensor", "Enabled", "Type", "AT", "EN"}
SENSITIVE_NAME_MARKERS = {"password"}


class LSR7ProtocolError(RuntimeError):
    pass


@dataclass
class Response:
    kind: str
    path: str
    value: str | None = None
    children: list[str] | None = None
    raw: str = ""


@dataclass
class ParameterSnapshot:
    path: str
    value_text: str | None
    value_percent: str | None = None
    value_float: str | None = None
    value_raw: str | None = None
    min_text: str | None = None
    max_text: str | None = None
    type_name: str | None = None
    enabled: str | None = None
    is_sensor: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "value_text": self.value_text,
            "value_percent": self.value_percent,
            "value_float": self.value_float,
            "value_raw": self.value_raw,
            "min_text": self.min_text,
            "max_text": self.max_text,
            "type_name": self.type_name,
            "enabled": self.enabled,
            "is_sensor": self.is_sensor,
        }


def needs_redaction(path: str) -> bool:
    lower = path.lower()
    return any(marker in lower for marker in SENSITIVE_NAME_MARKERS)


class LSR7WebSocketClient:
    def __init__(self, host: str, port: int = WS_PORT, timeout: float = 3.0, debug_hook: Callable[[str, str], None] | None = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self.debug_hook = debug_hook

    def __enter__(self) -> "LSR7WebSocketClient":
        self.connect()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()

    def connect(self) -> None:
        if self.sock is not None:
            return
        self._debug("connect", f"Opening TCP connection to {self.host}:{self.port} timeout={self.timeout:.1f}s")
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        self._debug("handshake-send", request.decode("ascii", errors="replace").strip())
        self.sock.sendall(request)
        response = self.sock.recv(4096).decode("ascii", errors="replace")
        self._debug("handshake-recv", response.strip())
        if "101 WebSocket Protocol Handshake" not in response:
            raise LSR7ProtocolError(f"Unexpected handshake response: {response!r}")

    def close(self) -> None:
        if self.sock is None:
            return
        try:
            self._debug("close", f"Closing socket to {self.host}:{self.port}")
            self.sock.close()
        finally:
            self.sock = None

    def command(self, command: str) -> Response:
        payload = command.rstrip("\r\n") + "\r\n"
        attempts = 0
        last_error: Exception | None = None
        while attempts < 2:
            attempts += 1
            try:
                if self.sock is None:
                    self.connect()
                self._debug("tx", payload.rstrip())
                self._send_text(payload)
                raw = self._recv_text()
                self._debug("rx", raw.strip("\r\n"))
                return self._parse_response(raw)
            except (OSError, LSR7ProtocolError) as exc:
                last_error = exc
                self._debug("retry", f"Attempt {attempts} failed for {command!r}: {exc}")
                self.close()
                if attempts >= 2:
                    break
        raise LSR7ProtocolError(f"Command failed after retry: {command!r} ({last_error})")

    def list_children(self, path: str) -> list[str]:
        response = self.command(f'lc "{path}"')
        if response.kind == "error":
            raise LSR7ProtocolError(f"lc failed for {path}: {response.raw.strip()}")
        return response.children or []

    def try_list_children(self, path: str) -> list[str] | None:
        response = self.command(f'lc "{path}"')
        if response.kind == "error":
            return None
        return response.children or []

    def get_value(self, path: str) -> str | None:
        response = self.command(f'get "{path}"')
        if response.kind == "error":
            return None
        return response.value

    def get_identity(self) -> dict[str, str | None]:
        return {
            "class_name": self.get_value("\\\\this\\Node\\AT\\Class_Name"),
            "instance_name": self.get_value("\\\\this\\Node\\AT\\Instance_Name"),
            "software_version": self.get_value("\\\\this\\Node\\AT\\Software_Version"),
        }

    def set_text_value(self, path: str, value: str) -> str | None:
        response = self.command(f'set "{path}" "{value}"')
        if response.kind == "error":
            raise LSR7ProtocolError(f"set failed for {path}: {response.raw.strip()}")
        return response.value

    def set_percent_value(self, path: str, percent: float) -> str | None:
        response = self.command(f'set "{path}\\%" {percent:g}')
        if response.kind == "error":
            raise LSR7ProtocolError(f"set% failed for {path}: {response.raw.strip()}")
        return response.value

    def get_parameter_snapshot(self, path: str, *, redact_sensitive: bool = True) -> ParameterSnapshot:
        base_value = self.get_value(path)
        if redact_sensitive and needs_redaction(path):
            base_value = "<redacted>"
        return ParameterSnapshot(
            path=path,
            value_text=base_value,
            value_percent=self._safe_meta_value(path, "\\%", redact_sensitive),
            value_float=self._safe_meta_value(path, "\\f", redact_sensitive),
            value_raw=self._safe_meta_value(path, "\\r", redact_sensitive),
            min_text=self._safe_get_value(path + "\\Min"),
            max_text=self._safe_get_value(path + "\\Max"),
            type_name=self._safe_get_value(path + "\\Type"),
            enabled=self._safe_get_value(path + "\\Enabled"),
            is_sensor=self._safe_get_value(path + "\\Sensor"),
        )

    def read_path(self, path: str, *, redact_sensitive: bool = True) -> dict[str, Any]:
        children = self.try_list_children(path) or []
        if children and self._is_parameter_node(children):
            return self.get_parameter_snapshot(path, redact_sensitive=redact_sensitive).as_dict()
        return {
            "path": path,
            "value_text": self._maybe_redact(path, self.get_value(path), redact_sensitive),
            "value_percent": None,
            "value_float": None,
            "value_raw": None,
            "min_text": None,
            "max_text": None,
            "type_name": None,
            "enabled": None,
            "is_sensor": None,
        }

    def read_many(self, paths: dict[str, str]) -> dict[str, str | None]:
        return {label: self.get_value(path) for label, path in paths.items()}

    def write_text_and_confirm(self, path: str, value: str) -> dict[str, Any]:
        self.set_text_value(path, value)
        return self.read_path(path)

    def write_percent_and_confirm(self, path: str, percent: float) -> dict[str, Any]:
        self.set_percent_value(path, percent)
        return self.read_path(path)

    def enumerate_tree(self, root: str = "\\\\this") -> dict[str, Any]:
        queue = [root]
        seen: set[str] = set()
        tree: dict[str, Any] = {}
        while queue:
            path = queue.pop(0)
            if path in seen:
                continue
            seen.add(path)
            children = self.try_list_children(path)
            if children is None:
                tree[path] = {"kind": "error"}
                continue
            clean_children = [child for child in children if child]
            tree[path] = {"kind": "node", "children": clean_children}
            if self._is_parameter_node(clean_children):
                tree[path]["kind"] = "parameter"
                tree[path]["snapshot"] = self.get_parameter_snapshot(path).as_dict()
                continue
            for child in clean_children:
                if child == "*":
                    continue
                queue.append(path + "\\" + child)
        return tree

    def pull_configuration(self, root: str = "\\\\this", *, redact_sensitive: bool = True) -> dict[str, Any]:
        queue = [root]
        seen: set[str] = set()
        snapshot: dict[str, Any] = {}
        while queue:
            path = queue.pop(0)
            if path in seen:
                continue
            seen.add(path)
            children = self.try_list_children(path)
            if children is None:
                snapshot[path] = {"kind": "error"}
                continue
            clean_children = [child for child in children if child]
            if self._is_parameter_node(clean_children):
                snapshot[path] = {
                    "kind": "parameter",
                    "snapshot": self.get_parameter_snapshot(path, redact_sensitive=redact_sensitive).as_dict(),
                }
                continue
            entry: dict[str, Any] = {"kind": "node", "children": clean_children}
            if path.endswith("\\AT"):
                values: dict[str, str | None] = {}
                for child in clean_children:
                    child_path = path + "\\" + child
                    value = self.get_value(child_path)
                    if redact_sensitive and needs_redaction(child_path):
                        value = "<redacted>"
                    values[child] = value
                entry["values"] = values
            snapshot[path] = entry
            for child in clean_children:
                if child == "*":
                    continue
                queue.append(path + "\\" + child)
        return snapshot

    def export_configuration(self, output_path: Path | str, root: str = "\\\\this") -> Path:
        output = Path(output_path)
        payload = {
            "host": self.host,
            "port": self.port,
            "root": root,
            "configuration": self.pull_configuration(root=root),
        }
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return output

    def _send_text(self, payload_text: str) -> None:
        if self.sock is None:
            raise LSR7ProtocolError("Socket is not connected")
        payload = payload_text.encode("utf-8")
        mask = os.urandom(4)
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.sock.sendall(bytes(header) + mask + masked)

    def _recv_text(self) -> str:
        if self.sock is None:
            raise LSR7ProtocolError("Socket is not connected")
        self.sock.settimeout(self.timeout)
        header = self.sock.recv(2)
        if not header:
            raise LSR7ProtocolError("Socket closed")
        first, second = header
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self.sock.recv(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self.sock.recv(8))[0]
        if second & 0x80:
            self.sock.recv(4)
        payload = bytearray()
        while len(payload) < length:
            payload.extend(self.sock.recv(length - len(payload)))
        return payload.decode("utf-8", errors="replace")

    def _parse_response(self, raw: str) -> Response:
        stripped = raw.strip("\r\n")
        if stripped.startswith("error "):
            return Response(kind="error", path=self._extract_path(stripped), raw=raw)
        if stripped.startswith("lc "):
            lines = stripped.splitlines()
            path = self._extract_path(lines[0])
            children = []
            for line in lines[1:]:
                line = line.strip()
                if not line or line == "endlc":
                    continue
                children.append(line)
            return Response(kind="lc", path=path, children=children, raw=raw)
        if stripped.startswith("get ") or stripped.startswith("setr "):
            kind = "setr" if stripped.startswith("setr ") else "get"
            return Response(kind=kind, path=self._extract_path(stripped), value=self._extract_value(stripped), raw=raw)
        raise LSR7ProtocolError(f"Unrecognized response: {raw!r}")

    def _extract_path(self, response: str) -> str:
        start = response.find('"')
        if start < 0:
            return ""
        end = response.find('"', start + 1)
        if end < 0:
            return ""
        return response[start + 1:end]

    def _extract_value(self, response: str) -> str | None:
        parts = response.split('"')
        if len(parts) >= 4:
            return parts[3]
        return ""

    def _is_parameter_node(self, children: list[str]) -> bool:
        return bool(children) and set(children).issubset(META_CHILDREN)

    def _maybe_redact(self, path: str, value: str | None, redact_sensitive: bool) -> str | None:
        if redact_sensitive and needs_redaction(path):
            return "<redacted>"
        return value

    def _safe_get_value(self, path: str) -> str | None:
        try:
            return self.get_value(path)
        except LSR7ProtocolError:
            return None

    def _safe_meta_value(self, path: str, suffix: str, redact_sensitive: bool) -> str | None:
        return self._maybe_redact(path, self._safe_get_value(path + suffix), redact_sensitive)

    def _debug(self, event: str, message: str) -> None:
        if self.debug_hook:
            try:
                self.debug_hook(event, message)
            except Exception:
                pass
