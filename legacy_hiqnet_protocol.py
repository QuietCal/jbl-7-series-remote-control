"""Legacy HiQnet protocol definitions.

These constants and helpers are retained only for historical reverse-
engineering notes. The active controller uses the LSR7 WebSocket API on
tcp/19273 and does not import this module at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
import ipaddress
import socket
import struct
import uuid
from typing import Iterable


HIQNET_PORT = 3804
PROTOCOL_VERSION = 0x02

FLAG_REQ_ACK = 0x0001
FLAG_ACK = 0x0002
FLAG_INFO = 0x0004
FLAG_ERROR = 0x0008
FLAG_GUARANTEED = 0x0020
FLAG_MULTIPART = 0x0040
FLAG_SESSION = 0x0100


class MessageID(IntEnum):
    DISCO_INFO = 0x0000
    GET_NETWORK_INFO = 0x0002
    REQUEST_ADDRESS = 0x0004
    SET_ADDRESS = 0x0006
    GOODBYE = 0x0007
    HELLO = 0x0008
    MULTI_PARAM_SET = 0x0100
    MULTI_OBJECT_PARAM_SET = 0x0101
    PARAM_SET_PERCENT = 0x0102
    MULTI_PARAM_GET = 0x0103
    MULTI_PARAM_SUBSCRIBE = 0x010F
    PARAM_SUBSCRIBE_PERCENT = 0x0111
    MULTI_PARAM_UNSUBSCRIBE = 0x0112
    SUBSCRIBE_EVENT_LOG = 0x0115
    GET_VD_LIST = 0x011A
    GET_ATTRIBUTES = 0x010D
    LOCATE = 0x0129


class DataType(IntEnum):
    BYTE = 0
    UBYTE = 1
    WORD = 2
    UWORD = 3
    LONG = 4
    ULONG = 5
    FLOAT32 = 6
    FLOAT64 = 7
    BLOCK = 8
    STRING = 9
    LONG64 = 10
    ULONG64 = 11


@dataclass(frozen=True)
class HiQnetAddress:
    device: int
    virtual_device: int = 0
    object_1: int = 0
    object_2: int = 0
    object_3: int = 0

    @property
    def object_tuple(self) -> tuple[int, int, int]:
        return (self.object_1, self.object_2, self.object_3)

    def to_bytes(self) -> bytes:
        return struct.pack(
            "!HBBBB",
            self.device & 0xFFFF,
            self.virtual_device & 0xFF,
            self.object_1 & 0xFF,
            self.object_2 & 0xFF,
            self.object_3 & 0xFF,
        )

    @classmethod
    def from_bytes(cls, payload: bytes) -> "HiQnetAddress":
        if len(payload) != 6:
            raise ValueError(f"HiQnetAddress requires 6 bytes, got {len(payload)}")
        device, vd, obj1, obj2, obj3 = struct.unpack("!HBBBB", payload)
        return cls(device, vd, obj1, obj2, obj3)

    @classmethod
    def broadcast(cls) -> "HiQnetAddress":
        return cls(0xFFFF, 0, 0, 0, 0)

    def short_label(self) -> str:
        return f"{self.device}.{self.virtual_device}.{self.object_1}.{self.object_2}.{self.object_3}"


@dataclass
class HiQnetMessage:
    source: HiQnetAddress
    destination: HiQnetAddress
    message_id: int
    flags: int = 0
    hop_count: int = 0x05
    sequence_number: int = 1
    payload: bytes = b""
    session_number: int | None = None
    error_code: int | None = None
    error_text: str | None = None

    def encode(self) -> bytes:
        header = bytearray()
        header.append(PROTOCOL_VERSION)
        header.append(0)
        header.extend(b"\x00\x00\x00\x00")
        header.extend(self.source.to_bytes())
        header.extend(self.destination.to_bytes())
        header.extend(struct.pack("!H", self.message_id & 0xFFFF))
        header.extend(struct.pack("!H", self.flags & 0xFFFF))
        header.append(self.hop_count & 0xFF)
        header.extend(struct.pack("!H", self.sequence_number & 0xFFFF))

        if self.flags & FLAG_ERROR:
            header.extend(struct.pack("!H", self.error_code or 0))
            header.extend(encode_string(self.error_text or ""))
        if self.flags & FLAG_MULTIPART:
            raise NotImplementedError("Multipart HiQnet messages are not implemented in v1")
        if self.flags & FLAG_SESSION:
            if self.session_number is None:
                raise ValueError("Session flag set but no session_number supplied")
            header.extend(struct.pack("!H", self.session_number & 0xFFFF))

        message_length = len(header) + len(self.payload)
        header[1] = len(header)
        header[2:6] = struct.pack("!I", message_length)
        return bytes(header) + self.payload

    @classmethod
    def decode(cls, data: bytes) -> "HiQnetMessage":
        if len(data) < 21:
            raise ValueError("HiQnet packet too small")

        version = data[0]
        if version != PROTOCOL_VERSION:
            raise ValueError(f"Unsupported HiQnet version {version}")

        header_length = data[1]
        message_length = struct.unpack("!I", data[2:6])[0]
        if message_length > len(data):
            raise ValueError("Incomplete HiQnet packet")

        source = HiQnetAddress.from_bytes(data[6:12])
        destination = HiQnetAddress.from_bytes(data[12:18])
        message_id = struct.unpack("!H", data[18:20])[0]
        flags = struct.unpack("!H", data[20:22])[0]
        hop_count = data[22]
        sequence_number = struct.unpack("!H", data[23:25])[0]

        index = 25
        error_code = None
        error_text = None
        session_number = None

        if flags & FLAG_ERROR:
            error_code = struct.unpack("!H", data[index:index + 2])[0]
            index += 2
            error_text, consumed = decode_string(data[index:header_length])
            index += consumed

        if flags & FLAG_MULTIPART:
            raise NotImplementedError("Multipart HiQnet messages are not implemented in v1")

        if flags & FLAG_SESSION:
            session_number = struct.unpack("!H", data[index:index + 2])[0]
            index += 2

        payload = data[header_length:message_length]
        return cls(
            source=source,
            destination=destination,
            message_id=message_id,
            flags=flags,
            hop_count=hop_count,
            sequence_number=sequence_number,
            payload=payload,
            session_number=session_number,
            error_code=error_code,
            error_text=error_text,
        )


FLAG_LABELS: list[tuple[int, str]] = [
    (FLAG_REQ_ACK, "REQ_ACK"),
    (FLAG_ACK, "ACK"),
    (FLAG_INFO, "INFO"),
    (FLAG_ERROR, "ERROR"),
    (FLAG_GUARANTEED, "GUARANTEED"),
    (FLAG_MULTIPART, "MULTIPART"),
    (FLAG_SESSION, "SESSION"),
]


def message_id_name(message_id: int) -> str:
    try:
        return MessageID(message_id).name
    except ValueError:
        return f"UNKNOWN_0x{message_id:04X}"


def flag_names(flags: int) -> list[str]:
    names = [label for value, label in FLAG_LABELS if flags & value]
    return names or ["NONE"]


def format_flags(flags: int) -> str:
    return "|".join(flag_names(flags))


def format_session(session_number: int | None) -> str:
    return "-" if session_number is None else str(session_number)


def format_hex(data: bytes, limit: int = 64) -> str:
    if not data:
        return "-"
    rendered = data[:limit].hex(" ").upper()
    if len(data) > limit:
        return f"{rendered} ... (+{len(data) - limit} bytes)"
    return rendered


@dataclass
class IPv4NetworkInfo:
    mac_address: str
    dhcp_or_autoip: bool
    ip_address: str
    subnet_mask: str = "0.0.0.0"
    gateway: str = "0.0.0.0"

    def encode(self) -> bytes:
        mac_hex = self.mac_address.replace(":", "").replace("-", "")
        mac_bytes = bytes.fromhex(mac_hex.zfill(12))[:6]
        return (
            mac_bytes
            + struct.pack("!B", 1 if self.dhcp_or_autoip else 0)
            + ip_to_bytes(self.ip_address)
            + ip_to_bytes(self.subnet_mask)
            + ip_to_bytes(self.gateway)
        )

    @classmethod
    def decode(cls, payload: bytes) -> "IPv4NetworkInfo":
        if len(payload) < 19:
            raise ValueError("IPv4 network info requires 19 bytes")
        mac = ":".join(f"{part:02X}" for part in payload[:6])
        dhcp = payload[6] == 1
        ip_addr = bytes_to_ip(payload[7:11])
        subnet = bytes_to_ip(payload[11:15])
        gateway = bytes_to_ip(payload[15:19])
        return cls(mac, dhcp, ip_addr, subnet, gateway)


@dataclass
class DiscoveryInfo:
    source_address: HiQnetAddress
    requested_device: int
    cost: int
    serial_number: bytes
    max_message_size: int
    keep_alive_ms: int
    network_id: int
    network_info: IPv4NetworkInfo | bytes | None
    sender_ip: str | None = None

    @property
    def serial_hex(self) -> str:
        return self.serial_number.hex().upper()

    def summary(self) -> str:
        network_bits = []
        if isinstance(self.network_info, IPv4NetworkInfo):
            network_bits.append(f"ip={self.network_info.ip_address}")
            network_bits.append(f"mac={self.network_info.mac_address}")
        elif isinstance(self.network_info, bytes):
            network_bits.append(f"network_raw={format_hex(self.network_info, limit=19)}")
        network_suffix = f" {' '.join(network_bits)}" if network_bits else ""
        return (
            f"requested={self.requested_device} cost={self.cost} serial={self.serial_hex} "
            f"max={self.max_message_size} keepalive={self.keep_alive_ms}ms network_id={self.network_id}"
            f"{network_suffix}"
        )


@dataclass
class ParamValue:
    param_id: int
    data_type: DataType
    value: object

    def summary(self) -> str:
        return f"param={self.param_id} type={self.data_type.name} value={self.value!r}"


@dataclass
class ControlMapping:
    name: str
    address: HiQnetAddress
    parameter_index: int
    data_type: str
    min_value: float | int | None = None
    max_value: float | int | None = None
    use_percent: bool = False
    notes: str = ""
    group: str = "general"

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "address": {
                "device": self.address.device,
                "virtual_device": self.address.virtual_device,
                "object_1": self.address.object_1,
                "object_2": self.address.object_2,
                "object_3": self.address.object_3,
            },
            "parameter_index": self.parameter_index,
            "data_type": self.data_type,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "use_percent": self.use_percent,
            "notes": self.notes,
            "group": self.group,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ControlMapping":
        address_data = data.get("address", {})
        return cls(
            name=data["name"],
            address=HiQnetAddress(
                device=int(address_data.get("device", 0)),
                virtual_device=int(address_data.get("virtual_device", 0)),
                object_1=int(address_data.get("object_1", 0)),
                object_2=int(address_data.get("object_2", 0)),
                object_3=int(address_data.get("object_3", 0)),
            ),
            parameter_index=int(data["parameter_index"]),
            data_type=str(data["data_type"]),
            min_value=data.get("min_value"),
            max_value=data.get("max_value"),
            use_percent=bool(data.get("use_percent", False)),
            notes=str(data.get("notes", "")),
            group=str(data.get("group", "general")),
        )


def encode_string(value: str) -> bytes:
    encoded = value.encode("utf-16-be") + b"\x00\x00"
    return struct.pack("!H", len(encoded)) + encoded


def decode_string(payload: bytes) -> tuple[str, int]:
    if len(payload) < 2:
        raise ValueError("String payload too small")
    length = struct.unpack("!H", payload[:2])[0]
    raw = payload[2:2 + length]
    text = raw.decode("utf-16-be", errors="ignore").rstrip("\x00")
    return text, 2 + length


def encode_block(data: bytes) -> bytes:
    return struct.pack("!H", len(data)) + data


def decode_block(payload: bytes, offset: int = 0) -> tuple[bytes, int]:
    length = struct.unpack("!H", payload[offset:offset + 2])[0]
    start = offset + 2
    end = start + length
    return payload[start:end], end - offset


def ip_to_bytes(ip_value: str) -> bytes:
    return ipaddress.IPv4Address(ip_value).packed


def bytes_to_ip(data: bytes) -> str:
    return str(ipaddress.IPv4Address(data))


def get_local_network_info(preferred_ip: str | None = None) -> IPv4NetworkInfo:
    if preferred_ip is None:
        preferred_ip = determine_local_ip()
    node = uuid.getnode()
    mac = ":".join(f"{(node >> shift) & 0xFF:02X}" for shift in range(40, -1, -8))
    return IPv4NetworkInfo(
        mac_address=mac,
        dhcp_or_autoip=True,
        ip_address=preferred_ip,
        subnet_mask="0.0.0.0",
        gateway="0.0.0.0",
    )


def determine_local_ip(target_ip: str = "255.255.255.255") -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((target_ip, 1))
        return sock.getsockname()[0]
    except OSError:
        return "0.0.0.0"
    finally:
        sock.close()


def build_disco_info_payload(
    requested_device: int,
    serial_number: bytes,
    max_message_size: int,
    keep_alive_ms: int,
    network_info: IPv4NetworkInfo,
    cost: int = 1,
    network_id: int = 1,
) -> bytes:
    return (
        struct.pack("!H", requested_device & 0xFFFF)
        + struct.pack("!B", cost & 0xFF)
        + encode_block(serial_number)
        + struct.pack("!I", max_message_size & 0xFFFFFFFF)
        + struct.pack("!H", keep_alive_ms & 0xFFFF)
        + struct.pack("!B", network_id & 0xFF)
        + network_info.encode()
    )


def parse_disco_info(message: HiQnetMessage, sender_ip: str | None = None) -> DiscoveryInfo:
    payload = message.payload
    requested_device = struct.unpack("!H", payload[:2])[0]
    cost = payload[2]
    serial_number, consumed = decode_block(payload, 3)
    index = 3 + consumed
    max_message_size = struct.unpack("!I", payload[index:index + 4])[0]
    index += 4
    keep_alive_ms = struct.unpack("!H", payload[index:index + 2])[0]
    index += 2
    network_id = payload[index]
    index += 1
    network_info_data = payload[index:]
    network_info: IPv4NetworkInfo | bytes | None
    if network_id == 1 and len(network_info_data) >= 19:
        network_info = IPv4NetworkInfo.decode(network_info_data[:19])
    else:
        network_info = network_info_data or None
    return DiscoveryInfo(
        source_address=message.source,
        requested_device=requested_device,
        cost=cost,
        serial_number=serial_number,
        max_message_size=max_message_size,
        keep_alive_ms=keep_alive_ms,
        network_id=network_id,
        network_info=network_info,
        sender_ip=sender_ip,
    )


def build_hello_payload(session_number: int, flag_mask: int = 0x01FF) -> bytes:
    return struct.pack("!HH", session_number & 0xFFFF, flag_mask & 0xFFFF)


def parse_hello_payload(payload: bytes) -> tuple[int, int]:
    if len(payload) < 4:
        raise ValueError("Hello payload too small")
    return struct.unpack("!HH", payload[:4])


def build_multi_param_get_payload(param_ids: Iterable[int]) -> bytes:
    param_ids = list(param_ids)
    payload = bytearray(struct.pack("!H", len(param_ids)))
    for param_id in param_ids:
        payload.extend(struct.pack("!H", param_id & 0xFFFF))
    return bytes(payload)


def parse_multi_param_get_payload(payload: bytes) -> list[ParamValue]:
    count = struct.unpack("!H", payload[:2])[0]
    index = 2
    values: list[ParamValue] = []
    for _ in range(count):
        param_id = struct.unpack("!H", payload[index:index + 2])[0]
        index += 2
        data_type = DataType(payload[index])
        index += 1
        value, consumed = decode_typed_value(data_type, payload[index:])
        index += consumed
        values.append(ParamValue(param_id, data_type, value))
    return values


def build_multi_param_set_payload(values: Iterable[ParamValue]) -> bytes:
    values = list(values)
    payload = bytearray(struct.pack("!H", len(values)))
    for value in values:
        payload.extend(struct.pack("!H", value.param_id & 0xFFFF))
        payload.extend(struct.pack("!B", int(value.data_type)))
        payload.extend(encode_typed_value(value.data_type, value.value))
    return bytes(payload)


def build_param_set_percent_payload(pairs: Iterable[tuple[int, float]]) -> bytes:
    pairs = list(pairs)
    payload = bytearray(struct.pack("!H", len(pairs)))
    for param_id, percent in pairs:
        payload.extend(struct.pack("!H", param_id & 0xFFFF))
        payload.extend(struct.pack("!H", percent_to_fixed(percent)))
    return bytes(payload)


def percent_to_fixed(percent: float) -> int:
    clamped = max(-100.0, min(100.0, percent))
    if clamped >= 100.0:
        return 0x7FFF
    if clamped <= -100.0:
        return 0x8000
    fraction = clamped / 100.0
    signed = int(round(fraction * 32768.0))
    return signed & 0xFFFF


def encode_typed_value(data_type: DataType, value: object) -> bytes:
    if data_type == DataType.BYTE:
        return struct.pack("!b", int(value))
    if data_type == DataType.UBYTE:
        return struct.pack("!B", int(value))
    if data_type == DataType.WORD:
        return struct.pack("!h", int(value))
    if data_type == DataType.UWORD:
        return struct.pack("!H", int(value))
    if data_type == DataType.LONG:
        return struct.pack("!i", int(value))
    if data_type == DataType.ULONG:
        return struct.pack("!I", int(value))
    if data_type == DataType.FLOAT32:
        return struct.pack("!f", float(value))
    if data_type == DataType.FLOAT64:
        return struct.pack("!d", float(value))
    if data_type == DataType.LONG64:
        return struct.pack("!q", int(value))
    if data_type == DataType.ULONG64:
        return struct.pack("!Q", int(value))
    if data_type == DataType.BLOCK:
        return encode_block(bytes(value))
    if data_type == DataType.STRING:
        return encode_string(str(value))
    raise ValueError(f"Unsupported HiQnet data type {data_type}")


def decode_typed_value(data_type: DataType, payload: bytes) -> tuple[object, int]:
    if data_type == DataType.BYTE:
        return struct.unpack("!b", payload[:1])[0], 1
    if data_type == DataType.UBYTE:
        return payload[0], 1
    if data_type == DataType.WORD:
        return struct.unpack("!h", payload[:2])[0], 2
    if data_type == DataType.UWORD:
        return struct.unpack("!H", payload[:2])[0], 2
    if data_type == DataType.LONG:
        return struct.unpack("!i", payload[:4])[0], 4
    if data_type == DataType.ULONG:
        return struct.unpack("!I", payload[:4])[0], 4
    if data_type == DataType.FLOAT32:
        return struct.unpack("!f", payload[:4])[0], 4
    if data_type == DataType.FLOAT64:
        return struct.unpack("!d", payload[:8])[0], 8
    if data_type == DataType.LONG64:
        return struct.unpack("!q", payload[:8])[0], 8
    if data_type == DataType.ULONG64:
        return struct.unpack("!Q", payload[:8])[0], 8
    if data_type == DataType.BLOCK:
        return decode_block(payload)
    if data_type == DataType.STRING:
        return decode_string(payload)
    raise ValueError(f"Unsupported HiQnet data type {data_type}")


def summarize_payload(message: HiQnetMessage) -> str:
    try:
        if message.message_id == MessageID.DISCO_INFO:
            sender_ip = None
            info = parse_disco_info(message, sender_ip=sender_ip)
            return info.summary()
        if message.message_id == MessageID.HELLO:
            session_number, flag_mask = parse_hello_payload(message.payload)
            return f"hello_session={session_number} supported_flags=0x{flag_mask:04X}"
        if message.message_id == MessageID.MULTI_PARAM_GET:
            if message.flags & FLAG_INFO:
                values = parse_multi_param_get_payload(message.payload)
                return ", ".join(value.summary() for value in values) or "no values"
            count = struct.unpack("!H", message.payload[:2])[0]
            params = [
                str(struct.unpack("!H", message.payload[2 + index * 2:4 + index * 2])[0])
                for index in range(count)
            ]
            return f"request_count={count} params={','.join(params)}"
        if message.message_id == MessageID.MULTI_PARAM_SET:
            count = struct.unpack("!H", message.payload[:2])[0]
            index = 2
            values: list[str] = []
            for _ in range(count):
                param_id = struct.unpack("!H", message.payload[index:index + 2])[0]
                index += 2
                data_type = DataType(message.payload[index])
                index += 1
                value, consumed = decode_typed_value(data_type, message.payload[index:])
                index += consumed
                values.append(f"param={param_id} type={data_type.name} value={value!r}")
            return ", ".join(values) or "no values"
        if message.message_id == MessageID.PARAM_SET_PERCENT:
            count = struct.unpack("!H", message.payload[:2])[0]
            index = 2
            parts: list[str] = []
            for _ in range(count):
                param_id = struct.unpack("!H", message.payload[index:index + 2])[0]
                fixed = struct.unpack("!H", message.payload[index + 2:index + 4])[0]
                index += 4
                parts.append(f"param={param_id} fixed=0x{fixed:04X}")
            return ", ".join(parts) or "no values"
        if message.message_id == MessageID.MULTI_PARAM_SUBSCRIBE:
            count = struct.unpack("!H", message.payload[:2])[0]
            return f"subscription_count={count}"
    except Exception as exc:
        return f"payload_parse_error={exc}"
    if not message.payload:
        return "empty"
    return f"raw={format_hex(message.payload)}"
