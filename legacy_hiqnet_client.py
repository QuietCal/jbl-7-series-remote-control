"""Legacy HiQnet research client.

This module is retained only as investigation history from the earlier
HiQnet/FTP phase. It is not part of the current JBL 7 Series controller
runtime, which uses the LSR7 WebSocket API on tcp/19273.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import errno
import random
import select
import socket
import threading
import time
from typing import Callable

from legacy_hiqnet_protocol import (
    FLAG_GUARANTEED,
    FLAG_INFO,
    FLAG_SESSION,
    HIQNET_PORT,
    DataType,
    DiscoveryInfo,
    HiQnetAddress,
    HiQnetMessage,
    MessageID,
    ParamValue,
    build_disco_info_payload,
    build_hello_payload,
    build_multi_param_get_payload,
    build_multi_param_set_payload,
    build_param_set_percent_payload,
    determine_local_ip,
    format_flags,
    format_hex,
    format_session,
    get_local_network_info,
    message_id_name,
    parse_disco_info,
    parse_hello_payload,
    parse_multi_param_get_payload,
    summarize_payload,
)


LogCallback = Callable[[str], None]


@dataclass
class ConnectionState:
    target_ip: str
    target_address: HiQnetAddress
    tcp_connected: bool = False
    remote_session: int | None = None
    local_session: int | None = None
    keep_alive_ms: int = 10000
    last_activity: float = 0.0


@dataclass
class PacketEvent:
    timestamp: str
    direction: str
    transport: str
    target_ip: str
    message_id: int
    message_name: str
    sequence_number: int
    flags: int
    flags_text: str
    source: str
    destination: str
    session_number: int | None
    payload_length: int
    payload_summary: str
    raw_hex: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "direction": self.direction,
            "transport": self.transport,
            "target_ip": self.target_ip,
            "message_id": self.message_id,
            "message_name": self.message_name,
            "sequence_number": self.sequence_number,
            "flags": self.flags,
            "flags_text": self.flags_text,
            "source": self.source,
            "destination": self.destination,
            "session_number": self.session_number,
            "payload_length": self.payload_length,
            "payload_summary": self.payload_summary,
            "raw_hex": self.raw_hex,
        }


@dataclass
class TargetProbeResult:
    target_ip: str
    local_ip: str
    udp_discovery_sent: bool
    udp_reply_received: bool
    udp_reply_summary: str | None
    tcp_3804_open: bool
    tcp_error: str | None = None

    def lines(self) -> list[str]:
        lines = [
            f"Probe target={self.target_ip} local_ip={self.local_ip}",
            f"UDP unicast DiscoInfo sent={self.udp_discovery_sent} reply={self.udp_reply_received}",
            f"TCP 3804 open={self.tcp_3804_open}",
        ]
        if self.udp_reply_summary:
            lines.append(f"UDP reply summary: {self.udp_reply_summary}")
        if self.tcp_error:
            lines.append(f"TCP detail: {self.tcp_error}")
        return lines


class LegacyHiQnetClient:
    def __init__(
        self,
        source_device: int = 0x7FFE,
        logger: LogCallback | None = None,
        verbose_debug: bool = False,
        include_hex_dump: bool = False,
    ) -> None:
        self.source_device = source_device
        self.logger = logger or (lambda message: None)
        self.verbose_debug = verbose_debug
        self.include_hex_dump = include_hex_dump
        self.sequence_number = 1
        self.sock: socket.socket | None = None
        self.reader_thread: threading.Thread | None = None
        self.keepalive_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.connected = ConnectionState(
            target_ip="",
            target_address=HiQnetAddress(0),
        )
        self.discovery_cache: dict[str, DiscoveryInfo] = {}
        self.pending_replies: list[HiQnetMessage] = []
        self.pending_condition = threading.Condition()
        self.packet_events: list[PacketEvent] = []
        self.packet_events_lock = threading.Lock()

    def log(self, message: str) -> None:
        self.logger(message)

    def configure_debug(self, verbose_debug: bool | None = None, include_hex_dump: bool | None = None) -> None:
        if verbose_debug is not None:
            self.verbose_debug = verbose_debug
        if include_hex_dump is not None:
            self.include_hex_dump = include_hex_dump
        self.log(
            f"Debug settings updated verbose={self.verbose_debug} hex_dump={self.include_hex_dump}"
        )

    @property
    def source_address(self) -> HiQnetAddress:
        return HiQnetAddress(self.source_device, 0, 0, 0, 0)

    def set_source_device(self, device_id: int) -> None:
        self.source_device = device_id & 0xFFFF

    def next_sequence(self) -> int:
        value = self.sequence_number
        self.sequence_number = (self.sequence_number + 1) & 0xFFFF
        if self.sequence_number == 0:
            self.sequence_number = 1
        return value

    def discover(
        self,
        requested_device: int = 0xFFFF,
        timeout: float = 3.0,
        attempts: int = 1,
    ) -> list[DiscoveryInfo]:
        results: dict[str, DiscoveryInfo] = {}
        local_ip = determine_local_ip()
        network_info = get_local_network_info(local_ip)
        serial = bytes.fromhex(network_info.mac_address.replace(":", ""))
        payload = build_disco_info_payload(
            requested_device=requested_device,
            serial_number=serial,
            max_message_size=8192,
            keep_alive_ms=10000,
            network_info=network_info,
        )

        message = HiQnetMessage(
            source=self.source_address,
            destination=HiQnetAddress.broadcast(),
            message_id=MessageID.DISCO_INFO,
            flags=0,
            hop_count=0x05,
            sequence_number=self.next_sequence(),
            payload=payload,
        )
        encoded = message.encode()

        for attempt in range(1, attempts + 1):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(timeout)
            try:
                sock.bind(("", 0))
                self.log(f"Broadcasting DiscoInfo(Q) attempt {attempt} to UDP/{HIQNET_PORT}")
                self._record_wire_event("TX", "UDP", "255.255.255.255", message, encoded)
                sock.sendto(encoded, ("255.255.255.255", HIQNET_PORT))
                end_time = time.time() + timeout
                while time.time() < end_time:
                    try:
                        packet, addr = sock.recvfrom(65535)
                    except socket.timeout:
                        break
                    try:
                        response = HiQnetMessage.decode(packet)
                    except Exception as exc:
                        self.log(f"Ignoring undecodable UDP packet from {addr[0]}: {exc}")
                        continue
                    if response.message_id != MessageID.DISCO_INFO:
                        continue
                    self._record_wire_event("RX", "UDP", addr[0], response, packet)
                    info = parse_disco_info(response, sender_ip=addr[0])
                    key = f"{addr[0]}:{info.source_address.short_label()}"
                    results[key] = info
                    self.discovery_cache[addr[0]] = info
                    self.log(
                        "Discovered HiQnet device "
                        f"{info.source_address.short_label()} at {addr[0]} serial={info.serial_hex}"
                    )
            finally:
                sock.close()
        return list(results.values())

    def probe_target(self, target_ip: str, timeout: float = 2.0) -> TargetProbeResult:
        local_ip = determine_local_ip(target_ip)
        network_info = get_local_network_info(local_ip)
        serial = bytes.fromhex(network_info.mac_address.replace(":", ""))
        payload = build_disco_info_payload(
            requested_device=0xFFFF,
            serial_number=serial,
            max_message_size=8192,
            keep_alive_ms=10000,
            network_info=network_info,
        )
        discovery = HiQnetMessage(
            source=self.source_address,
            destination=HiQnetAddress.broadcast(),
            message_id=MessageID.DISCO_INFO,
            flags=0,
            hop_count=0x05,
            sequence_number=self.next_sequence(),
            payload=payload,
        )
        encoded = discovery.encode()
        udp_reply_received = False
        udp_reply_summary = None
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.settimeout(timeout)
        try:
            udp_sock.bind(("", 0))
            self._record_wire_event("TX", "UDP", target_ip, discovery, encoded)
            udp_sock.sendto(encoded, (target_ip, HIQNET_PORT))
            try:
                packet, addr = udp_sock.recvfrom(65535)
                response = HiQnetMessage.decode(packet)
                self._record_wire_event("RX", "UDP", addr[0], response, packet)
                udp_reply_received = True
                udp_reply_summary = summarize_payload(response)
            except socket.timeout:
                udp_reply_summary = None
        finally:
            udp_sock.close()

        tcp_3804_open = False
        tcp_error = None
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.setblocking(False)
        try:
            code = tcp_sock.connect_ex((target_ip, HIQNET_PORT))
            if code == 0:
                tcp_3804_open = True
            else:
                _, writable, _ = select.select([], [tcp_sock], [], timeout)
                if not writable:
                    tcp_error = "connect timed out"
                else:
                    socket_error = tcp_sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                    if socket_error == 0:
                        tcp_3804_open = True
                    elif socket_error in {errno.ECONNREFUSED, 10061}:
                        tcp_error = "connection refused (RST)"
                    elif socket_error in {errno.ETIMEDOUT, 10060}:
                        tcp_error = "connect timed out"
                    else:
                        tcp_error = f"socket error={socket_error}"
        finally:
            tcp_sock.close()

        result = TargetProbeResult(
            target_ip=target_ip,
            local_ip=local_ip,
            udp_discovery_sent=True,
            udp_reply_received=udp_reply_received,
            udp_reply_summary=udp_reply_summary,
            tcp_3804_open=tcp_3804_open,
            tcp_error=tcp_error,
        )
        for line in result.lines():
            self.log(line)
        return result

    def connect(self, target_ip: str, target_address: HiQnetAddress, keep_alive_ms: int = 10000) -> None:
        self.disconnect()
        sock = socket.create_connection((target_ip, HIQNET_PORT), timeout=5.0)
        sock.settimeout(1.0)
        self.sock = sock
        self.stop_event.clear()
        self.connected = ConnectionState(
            target_ip=target_ip,
            target_address=target_address,
            tcp_connected=True,
            keep_alive_ms=max(250, keep_alive_ms),
            last_activity=time.time(),
        )

        self.connected.local_session = random.randint(1, 0xFFFF)
        hello = HiQnetMessage(
            source=self.source_address,
            destination=target_address,
            message_id=MessageID.HELLO,
            flags=FLAG_GUARANTEED,
            sequence_number=self.next_sequence(),
            payload=build_hello_payload(self.connected.local_session),
        )
        self.log(f"Opening TCP session to {target_ip}:{HIQNET_PORT}")
        self._send_tcp_message(hello)
        self.log("Waiting for Hello(I) reply to correlate session negotiation")

        response = self._wait_for_reply(MessageID.HELLO, timeout=5.0)
        if response is not None:
            self.connected.remote_session, remote_flags = parse_hello_payload(response.payload)
            self.log(
                "Hello(I) received "
                f"remote_session={self.connected.remote_session} supported_flags=0x{remote_flags:04X}"
            )
        else:
            self.log("Hello(I) not received; continuing without remote session header support")

        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()
        self.keepalive_thread = threading.Thread(target=self._keepalive_loop, daemon=True)
        self.keepalive_thread.start()

    def disconnect(self) -> None:
        self.stop_event.set()
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None
        self.connected = ConnectionState("", HiQnetAddress(0))

    def get_params(self, address: HiQnetAddress, param_ids: list[int]) -> list[ParamValue]:
        message = HiQnetMessage(
            source=self.source_address,
            destination=address,
            message_id=MessageID.MULTI_PARAM_GET,
            flags=FLAG_GUARANTEED | self._session_flag(),
            sequence_number=self.next_sequence(),
            payload=build_multi_param_get_payload(param_ids),
            session_number=self.connected.remote_session if self._session_flag() else None,
        )
        self._send_tcp_message(message)
        response = self._wait_for_reply(MessageID.MULTI_PARAM_GET, timeout=5.0)
        if response is None:
            raise TimeoutError("Timed out waiting for MultiParamGet(I)")
        self.log(f"Received MultiParamGet(I) for {len(param_ids)} parameter(s)")
        return parse_multi_param_get_payload(response.payload)

    def set_params(self, address: HiQnetAddress, values: list[ParamValue]) -> None:
        message = HiQnetMessage(
            source=self.source_address,
            destination=address,
            message_id=MessageID.MULTI_PARAM_SET,
            flags=FLAG_GUARANTEED | self._session_flag(),
            sequence_number=self.next_sequence(),
            payload=build_multi_param_set_payload(values),
            session_number=self.connected.remote_session if self._session_flag() else None,
        )
        self._send_tcp_message(message)
        self.log(f"Sent MultiParamSet for {len(values)} parameter(s)")

    def set_percent(self, address: HiQnetAddress, pairs: list[tuple[int, float]]) -> None:
        message = HiQnetMessage(
            source=self.source_address,
            destination=address,
            message_id=MessageID.PARAM_SET_PERCENT,
            flags=FLAG_GUARANTEED | self._session_flag(),
            sequence_number=self.next_sequence(),
            payload=build_param_set_percent_payload(pairs),
            session_number=self.connected.remote_session if self._session_flag() else None,
        )
        self._send_tcp_message(message)
        self.log(f"Sent ParamSetPercent for {len(pairs)} parameter(s)")

    def subscribe(self, address: HiQnetAddress, param_ids: list[int]) -> None:
        payload = bytearray()
        payload.extend(len(param_ids).to_bytes(2, "big"))
        for param_id in param_ids:
            payload.extend(param_id.to_bytes(2, "big"))
            payload.extend(b"\x00")
            payload.extend(self.source_address.to_bytes())
            payload.extend(param_id.to_bytes(2, "big"))
            payload.extend(b"\x00\x00\x00")
            payload.extend((1000).to_bytes(2, "big"))
        message = HiQnetMessage(
            source=self.source_address,
            destination=address,
            message_id=MessageID.MULTI_PARAM_SUBSCRIBE,
            flags=FLAG_GUARANTEED | self._session_flag(),
            sequence_number=self.next_sequence(),
            payload=bytes(payload),
            session_number=self.connected.remote_session if self._session_flag() else None,
        )
        self._send_tcp_message(message)
        self.log(f"Sent MultiParamSubscribe for {len(param_ids)} parameter(s)")

    def _session_flag(self) -> int:
        return FLAG_SESSION if self.connected.remote_session else 0

    def _send_tcp_message(self, message: HiQnetMessage) -> None:
        if self.sock is None:
            raise RuntimeError("Not connected")
        encoded = message.encode()
        self.sock.sendall(encoded)
        self.connected.last_activity = time.time()
        self._record_wire_event("TX", "TCP", self.connected.target_ip, message, encoded)

    def _wait_for_reply(self, message_id: int, timeout: float) -> HiQnetMessage | None:
        end_time = time.time() + timeout
        expected_name = message_id_name(message_id)
        if self.verbose_debug:
            self.log(f"Waiting up to {timeout:.1f}s for {expected_name} reply")
        while time.time() < end_time:
            if self.sock is None:
                return None
            ready, _, _ = select.select([self.sock], [], [], 0.25)
            if ready:
                incoming = self._read_one_message()
                if incoming is None:
                    continue
                if incoming.flags & FLAG_INFO and incoming.message_id == message_id:
                    if self.verbose_debug:
                        self.log(
                            f"Matched direct reply {expected_name} seq={incoming.sequence_number} "
                            f"session={format_session(incoming.session_number)}"
                        )
                    return incoming
                with self.pending_condition:
                    self.pending_replies.append(incoming)
                    if self.verbose_debug:
                        self.log(
                            f"Queued unmatched message {message_id_name(incoming.message_id)} "
                            f"pending={len(self.pending_replies)}"
                        )
                    self.pending_condition.notify_all()
        with self.pending_condition:
            for item in self.pending_replies:
                if item.flags & FLAG_INFO and item.message_id == message_id:
                    self.pending_replies.remove(item)
                    if self.verbose_debug:
                        self.log(
                            f"Matched queued reply {expected_name} seq={item.sequence_number} "
                            f"pending={len(self.pending_replies)}"
                        )
                    return item
        if self.verbose_debug:
            self.log(f"Timed out waiting for {expected_name} reply")
        return None

    def _read_one_message(self) -> HiQnetMessage | None:
        if self.sock is None:
            return None
        try:
            header = self._recv_exact(6)
            if not header:
                return None
            header_length = header[1]
            message_length = int.from_bytes(header[2:6], "big")
            remainder = self._recv_exact(message_length - 6)
            packet = header + remainder
            message = HiQnetMessage.decode(packet)
            self.connected.last_activity = time.time()
            self._record_wire_event("RX", "TCP", self.connected.target_ip, message, packet, header_length=header_length)
            return message
        except socket.timeout:
            return None
        except OSError:
            return None
        except Exception as exc:
            self.log(f"Receive error: {exc}")
            return None

    def _recv_exact(self, length: int) -> bytes:
        data = bytearray()
        while len(data) < length:
            if self.sock is None:
                raise OSError("Socket closed")
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                raise OSError("Connection closed")
            data.extend(chunk)
        return bytes(data)

    def _reader_loop(self) -> None:
        while not self.stop_event.is_set():
            message = self._read_one_message()
            if message is None:
                continue
            with self.pending_condition:
                self.pending_replies.append(message)
                if self.verbose_debug:
                    self.log(
                        f"Reader queued {message_id_name(message.message_id)} "
                        f"seq={message.sequence_number} pending={len(self.pending_replies)}"
                    )
                self.pending_condition.notify_all()

    def _keepalive_loop(self) -> None:
        while not self.stop_event.wait(1.0):
            if self.sock is None or not self.connected.tcp_connected:
                return
            idle_ms = (time.time() - self.connected.last_activity) * 1000.0
            if idle_ms < self.connected.keep_alive_ms:
                continue
            try:
                if self.verbose_debug:
                    self.log(
                        f"Keep-alive due after idle={idle_ms:.0f}ms threshold={self.connected.keep_alive_ms}ms"
                    )
                network_info = get_local_network_info(determine_local_ip(self.connected.target_ip))
                serial = bytes.fromhex(network_info.mac_address.replace(":", ""))
                payload = build_disco_info_payload(
                    requested_device=self.source_device,
                    serial_number=serial,
                    max_message_size=8192,
                    keep_alive_ms=self.connected.keep_alive_ms,
                    network_info=network_info,
                )
                message = HiQnetMessage(
                    source=self.source_address,
                    destination=self.connected.target_address,
                    message_id=MessageID.DISCO_INFO,
                    flags=FLAG_GUARANTEED | FLAG_INFO | self._session_flag(),
                    sequence_number=self.next_sequence(),
                    payload=payload,
                    session_number=self.connected.remote_session if self._session_flag() else None,
                )
                self._send_tcp_message(message)
                self.log("Sent DiscoInfo(I) keep-alive")
            except Exception as exc:
                self.log(f"Keep-alive failed: {exc}")
                return

    def status_snapshot(self) -> dict:
        return {
            "source_device": self.source_device,
            "target_ip": self.connected.target_ip,
            "target_address": self.connected.target_address.short_label(),
            "tcp_connected": self.connected.tcp_connected,
            "local_session": self.connected.local_session,
            "remote_session": self.connected.remote_session,
            "last_activity": self.connected.last_activity,
            "keep_alive_ms": self.connected.keep_alive_ms,
            "verbose_debug": self.verbose_debug,
            "include_hex_dump": self.include_hex_dump,
            "packet_event_count": len(self.packet_events),
        }

    def export_packet_events(self) -> list[dict[str, object]]:
        with self.packet_events_lock:
            return [event.as_dict() for event in self.packet_events]

    def clear_packet_events(self) -> None:
        with self.packet_events_lock:
            self.packet_events.clear()
        self.log("Cleared packet event history")

    def _record_wire_event(
        self,
        direction: str,
        transport: str,
        target_ip: str,
        message: HiQnetMessage,
        packet: bytes,
        *,
        header_length: int | None = None,
    ) -> None:
        payload_summary = summarize_payload(message)
        event = PacketEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            direction=direction,
            transport=transport,
            target_ip=target_ip,
            message_id=message.message_id,
            message_name=message_id_name(message.message_id),
            sequence_number=message.sequence_number,
            flags=message.flags,
            flags_text=format_flags(message.flags),
            source=message.source.short_label(),
            destination=message.destination.short_label(),
            session_number=message.session_number,
            payload_length=len(message.payload),
            payload_summary=payload_summary,
            raw_hex=format_hex(packet) if self.include_hex_dump else None,
        )
        with self.packet_events_lock:
            self.packet_events.append(event)
        parts = [
            direction,
            transport,
            f"id=0x{message.message_id:04X}",
            f"name={event.message_name}",
            f"seq={message.sequence_number}",
            f"flags=0x{message.flags:04X}",
            f"flag_names={event.flags_text}",
            f"session={format_session(message.session_number)}",
            f"src={event.source}",
            f"dst={event.destination}",
            f"payload_bytes={len(message.payload)}",
        ]
        if header_length is not None:
            parts.append(f"header={header_length}")
        parts.append(f"summary={payload_summary}")
        if self.include_hex_dump:
            parts.append(f"hex={format_hex(packet)}")
        if self.verbose_debug:
            self.log(" ".join(parts))


def coerce_param_value(data_type_name: str, raw_value: str) -> ParamValue:
    data_type = DataType[data_type_name.upper()]
    if data_type in {DataType.FLOAT32, DataType.FLOAT64}:
        value: object = float(raw_value)
    elif data_type == DataType.STRING:
        value = raw_value
    else:
        value = int(raw_value, 0)
    return ParamValue(0, data_type, value)


HiQnetClient = LegacyHiQnetClient
