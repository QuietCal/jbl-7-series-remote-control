from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import ipaddress
import socket
import subprocess
from typing import Iterable

from lsr7_ws import LSR7WebSocketClient, LSR7ProtocolError


@dataclass(frozen=True)
class NetworkInterface:
    name: str
    ipv4: str
    subnet_mask: str
    prefixlen: int

    @property
    def cidr(self) -> str:
        return f"{self.ipv4}/{self.prefixlen}"

    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.ipv4}/{self.prefixlen})"


@dataclass(frozen=True)
class DiscoveredSpeaker:
    host: str
    class_name: str | None
    instance_name: str | None
    software_version: str | None

    @property
    def display_name(self) -> str:
        class_name = self.class_name or "Unknown"
        return f"{self.host} | {class_name}"


def _mask_to_prefix(mask: str) -> int:
    return ipaddress.IPv4Network(f"0.0.0.0/{mask}").prefixlen


def list_network_interfaces() -> list[NetworkInterface]:
    try:
        output = subprocess.check_output(["ipconfig"], text=True, encoding="utf-8", errors="replace")
    except Exception:
        return []

    interfaces: list[NetworkInterface] = []
    current_name: str | None = None
    ipv4: str | None = None
    subnet_mask: str | None = None

    def commit() -> None:
        nonlocal current_name, ipv4, subnet_mask
        if current_name and ipv4 and subnet_mask:
            interfaces.append(
                NetworkInterface(
                    name=current_name,
                    ipv4=ipv4,
                    subnet_mask=subnet_mask,
                    prefixlen=_mask_to_prefix(subnet_mask),
                )
            )
        current_name = None
        ipv4 = None
        subnet_mask = None

    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if line.endswith(":") and "adapter" in line.lower():
            commit()
            current_name = line[:-1].strip()
            continue
        if current_name is None:
            continue
        if "IPv4 Address" in line or "IPv4-address" in line:
            value = line.split(":", 1)[1].strip().replace("(Preferred)", "").strip()
            ipv4 = value
        elif "Subnet Mask" in line:
            subnet_mask = line.split(":", 1)[1].strip()
    commit()
    return interfaces


def iter_interface_hosts(interface: NetworkInterface, *, max_hosts: int = 512) -> Iterable[str]:
    network = ipaddress.IPv4Network(interface.cidr, strict=False)
    count = 0
    for host in network.hosts():
        yield str(host)
        count += 1
        if count >= max_hosts:
            break


def probe_speaker_host(host: str, *, timeout: float = 0.35) -> DiscoveredSpeaker | None:
    try:
        with LSR7WebSocketClient(host, timeout=timeout) as client:
            identity = client.get_identity()
    except (OSError, LSR7ProtocolError, socket.timeout):
        return None
    class_name = identity.get("class_name")
    if not class_name:
        return None
    return DiscoveredSpeaker(
        host=host,
        class_name=class_name,
        instance_name=identity.get("instance_name"),
        software_version=identity.get("software_version"),
    )


def discover_speakers(interface: NetworkInterface, *, timeout: float = 0.35, max_workers: int = 24, max_hosts: int = 512) -> list[DiscoveredSpeaker]:
    hosts = list(iter_interface_hosts(interface, max_hosts=max_hosts))
    speakers: list[DiscoveredSpeaker] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(probe_speaker_host, host, timeout=timeout): host for host in hosts}
        for future in as_completed(futures):
            speaker = future.result()
            if speaker is not None:
                speakers.append(speaker)
    speakers.sort(key=lambda item: tuple(int(part) for part in item.host.split(".")))
    return speakers
