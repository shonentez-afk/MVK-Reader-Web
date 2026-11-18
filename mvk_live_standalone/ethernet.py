"""Read-only discovery of the ONE physical wired Windows Ethernet IPv4.

No adapter changes, IP address changes, ICMP probes or TCP connections.
The selected IPv4 is later checked/bound again by Native Go via
Get-NetAdapter-equivalent enumeration + IP_UNICAST_IF on Windows.
Wi-Fi, VPN, Hyper-V and logical interfaces must not be picked by name only.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import json
import subprocess
import sys


@dataclass(frozen=True)
class WiredEthernet:
    name: str
    if_index: int
    ipv4: str
    prefix_length: int

    @property
    def description(self) -> str:
        return f"{self.name} · {self.ipv4}/{self.prefix_length} · интерфейс #{self.if_index}"


# Get-NetAdapter -Physical alone ALSO returns real Wi-Fi hardware.
# Filter IF_TYPE_ETHERNET_CSMACD (6) plus physical and UP; do not
# guess by localized Windows adapter name or interface description.
# Output single JSON array even if PowerShell returns 0/1 records.
_WINDOWS_DISCOVERY = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$rows = @()
$ethernetCards = @(Get-NetAdapter -Name '*' -Physical -ErrorAction Stop |
    Where-Object { $_.Status -eq 'Up' -and [int]$_.ifType -eq 6 })
foreach ($nic in $ethernetCards) {
    $ips = @(Get-NetIPAddress -InterfaceIndex $nic.ifIndex -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object { $_.AddressState -eq 'Preferred' -and -not $_.SkipAsSource })
    foreach ($ip in $ips) {
        $rows += [pscustomobject]@{
            Name = [string]$nic.Name
            InterfaceIndex = [int]$nic.ifIndex
            IPv4 = [string]$ip.IPAddress
            PrefixLength = [int]$ip.PrefixLength
        }
    }
}
ConvertTo-Json -InputObject @($rows) -Depth 3 -Compress
""".strip()


def parse_windows_ethernet_json(payload: str) -> WiredEthernet:
    """Strict fail-closed parser: never autoselect any ambiguous adapter/IP."""
    if not isinstance(payload, str) or len(payload)>65536:
        raise ValueError("Слишком большой ответ Windows о сетевых картах")
    try:
        raw=json.loads(payload.lstrip("\ufeff").strip())
    except (ValueError,TypeError) as exc:
        raise ValueError("Windows не вернула список Ethernet IPv4") from exc
    if not isinstance(raw,list):
        raise ValueError("Неверный формат списка Ethernet IPv4")
    if not raw:
        raise ValueError(
            "Нет активного проводного Ethernet с IPv4. Проверьте кабель и настройки IPv4 Windows.")
    if len(raw)!=1:
        raise ValueError(
            "На Ethernet обнаружено несколько IPv4 или несколько сетевых карт. "
            "Адрес автоматически не выбран; укажите IPv4 нужного Ethernet вручную.")
    row=raw[0]
    if not isinstance(row,dict):
        raise ValueError("Некорректная запись Ethernet Windows")
    name=row.get("Name")
    idx=row.get("InterfaceIndex")
    ipv4=row.get("IPv4")
    prefix=row.get("PrefixLength")
    if (not isinstance(name,str) or not name.strip() or len(name)>240 or
        type(idx) is not int or not 1<=idx<2**24 or
        type(prefix) is not int or not 1<=prefix<=32 or
        not isinstance(ipv4,str)):
        raise ValueError("Неверные поля сетевой карты Ethernet")
    try:
        ip=ipaddress.IPv4Address(ipv4)
    except ipaddress.AddressValueError as exc:
        raise ValueError("Неверный IPv4 проводного Ethernet") from exc
    if (str(ip)!=ipv4 or ip.is_loopback or ip.is_link_local or
        ip.is_multicast or ip.is_unspecified or ip.is_reserved or
        ip == ipaddress.IPv4Address("255.255.255.255")):
        raise ValueError("Неподходящий IPv4 Ethernet: требуется назначенный адрес сети прибора")
    return WiredEthernet(name.strip(),idx,ipv4,prefix)


def discover_single_wired_ethernet() -> WiredEthernet:
    """Pure local Windows query. Never changes configuration or dials MVK01."""
    if sys.platform!="win32":
        raise ValueError("Автоопределение физического Ethernet доступно в Windows")
    try:
        result=subprocess.run(
            ["powershell.exe","-NoProfile","-NonInteractive",
             "-Command",_WINDOWS_DISCOVERY],
            capture_output=True,timeout=10,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise ValueError("Не удалось прочитать сетевые карты Windows") from exc
    if result.returncode!=0:
        raise ValueError(
            "Windows не смогла определить Ethernet. "
            "Проверьте адаптер и введите локальный IPv4 вручную.")
    try:
        stdout=result.stdout.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("Неизвестная кодировка ответа Windows") from exc
    return parse_windows_ethernet_json(stdout)
