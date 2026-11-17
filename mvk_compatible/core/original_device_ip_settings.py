"""Original MVKView XML device address import + isolated compatible persistence.

Original _Unit128:0084ED8B -> stXmlStorage.ReadString("Device\\Address",
"192.168.0.30") -> edIpAddr; 0084F270..0084F28C writes the edit
back to XML. Mode2 _Unit128:00846D91..00846DD1 passes the CURRENT edit
text to TMVKThread.Create. No autodiscovery, network probe, or sockets.

Do not overwrite operator's vendor mvkview.exe.xml: compatible edits are
stored in a different user profile file. Original XML is import-only.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

from .original_start_workbench import START_IP_DEFAULT, validate_source_ipv4

SOURCE="ORIGINAL_JV_XML_DEVICE_ADDRESS_0084ED8B_0084F270"
MAX_XML=65536


def read_original_device_address(path:str|Path)->str:
    p=Path(path)
    if p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=MAX_XML:
        raise ValueError("Original source XML missing, oversized, or linked")
    payload=p.read_bytes()
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise ValueError("Device XML DTD/entities are not permitted")
    try:
        root=ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("Invalid source device XML") from exc
    if root.tag!="Configuration":
        raise ValueError("Unexpected source configuration root")
    ip=root.findtext("./Device/Address")
    if ip is None:
        return START_IP_DEFAULT
    return validate_source_ipv4(ip)


def compatible_device_settings_path()->Path|None:
    base=os.environ.get("LOCALAPPDATA")
    if not base:
        return None
    return Path(base)/"MVKViewCompatible"/"device.xml"


def imported_original_device_settings_path()->Path:
    # Keep the original program's conventional executable-adjacent XML
    # separate from our application's writable compatibility file.
    return Path(sys.executable).resolve().parent/"mvkview.exe.xml"


def startup_device_address()->tuple[str,str]:
    """Priority: validated compatible user override > original vendor XML > default."""
    candidates=(
        ("compatible",compatible_device_settings_path()),
        ("original_xml",imported_original_device_settings_path()),
    )
    for name,path in candidates:
        if path is None or not path.exists():
            continue
        try:
            return read_original_device_address(path),name
        except (ValueError,OSError,UnicodeError):
            # An invalid file may not cause a silent or accidental device
            # connection; choose source fallback and require operator consent.
            continue
    return START_IP_DEFAULT,"original_default"


def save_compatible_device_address(ip:str,path:str|Path|None=None)->Path|None:
    """Atomic profile-only save. Never changes original mvkview.exe.xml."""
    normalized=validate_source_ipv4(ip)
    dest=Path(path) if path is not None else compatible_device_settings_path()
    if dest is None:
        return None  # non-Windows host, no implicit user-profile writes
    if dest.is_symlink():
        raise ValueError("Compatible settings path is a symlink")
    folder=dest.parent
    folder.mkdir(parents=True,exist_ok=True)
    if folder.is_symlink():
        raise ValueError("Compatible settings folder is a symlink")
    root=ET.Element("Configuration")
    ET.SubElement(ET.SubElement(root,"Device"),"Address").text=normalized
    xml=ET.tostring(root,encoding="utf-8",xml_declaration=True)
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(prefix=".mvk_device_",suffix=".xml",
                                         dir=folder,delete=False) as stream:
            tmp=Path(stream.name)
            stream.write(xml)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp,dest)
        return dest
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()
