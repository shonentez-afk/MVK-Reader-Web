"""Offline binding for explicit original MVKView WriteData BIN/TSXML pairs."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET
import re

from .original_mode2_source_files import SOURCE_WRITER_CHANNEL_NAMES

MAX_TSXML_BYTES = 64 * 1024
DECLARATION = '<?xml version="1.0" encoding="windows-1251"?>'
_NAME_TIME = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2}--[0-9]{2}-[0-9]{2}-[0-9]{2})\.bin\Z")
_CLOSE_TIME = re.compile(r"([0-9]{2})/([0-9]{2})/([0-9]{4}) ([0-9]{2}):([0-9]{2}):([0-9]{2}) (AM|PM)\Z")


def write_data_name_time(name: str, channel: int) -> datetime | None:
    """Return a naive local filename clock; do not infer a time zone or UTC."""
    match = _NAME_TIME.search(name)
    label_suffix = "-" + SOURCE_WRITER_CHANNEL_NAMES[channel - 1] + "-"
    if match is None or not name[:match.start()].endswith(label_suffix):
        return None
    if len(name[:match.start()]) <= len(label_suffix):
        return None
    try:
        return datetime.strptime(match[1], "%Y-%m-%d--%H-%M-%S")
    except ValueError:
        return None


def _source_close_time(value: str) -> datetime:
    match = _CLOSE_TIME.fullmatch(value)
    if match is None:
        raise ValueError("invalid local close clock")
    month, day, year, hour, minute, second = map(int, match.groups()[:6])
    if not 1 <= hour <= 12:
        raise ValueError("invalid local close hour")
    return datetime(year, month, day, hour % 12 + (12 if match[7] == "PM" else 0),
                    minute, second)


def _exact_field(node: ET.Element, name: str, *, units: str | None = None) -> str:
    fields = node.findall(name)
    if (len(fields) != 1 or len(fields[0]) or fields[0].text is None
            or (units is not None and fields[0].get("Units") != units)):
        raise ValueError("missing or ambiguous XML field")
    return fields[0].text


def inspect_write_data_sidecar(
        body: bytes, *, binary_basename: str, sidecar_basename: str,
        channel: int, binary_bytes: int) -> tuple[bool, datetime | None]:
    """Bind source Byte/Count or Single metadata to one declared local BIN.

    No path is opened from the XML. Clocks are syntax-checked separately and
    are not treated as provenance for matching recordings or runtime timing.
    """
    try:
        if not 0 < len(body) <= MAX_TSXML_BYTES:
            return False, None
        text = body.decode("cp1251")
        if not text.startswith(DECLARATION) or any(
                token in text.upper() for token in ("<!DOCTYPE", "<!ENTITY")):
            return False, None
        root = ET.fromstring(text[len(DECLARATION):])
        channels = root.findall("./Channels/Channel")
        if root.tag != "MainRoot" or len(channels) != 1:
            return False, None
        node = channels[0]
        rate = int(_exact_field(root, "FrequencyPerChannel"))
        close = _source_close_time(_exact_field(root, "DateTime"))
        expected_type = "Byte" if channel >= 9 else "Single"
        width = 1 if channel >= 9 else 4
        if (
            sidecar_basename != binary_basename + ".tsxml"
            or _exact_field(root, "DataFileName") != ".\\" + binary_basename
            or _exact_field(root, "ChannelsQuantity") != "1"
            or node.get("Index") != "0"
            or int(_exact_field(node, "ChannelNumber")) != channel
            or _exact_field(node, "RealDataType") != expected_type
            or int(_exact_field(node, "DataLength")) != binary_bytes
            or _exact_field(node, "DataOffset") != "0"
            or binary_bytes <= 0
            or binary_bytes % width != 0
            or rate <= 0
            or int(_exact_field(node, "ChannelFrequency")) != rate
        ):
            return False, close
        # Source FormatFloat("0.00") uses byte count / width / Fs in ms.
        # At a half hundredth do not infer the exact x87 rounding direction.
        duration = re.fullmatch(r"([0-9]{1,12})[.]([0-9]{2})",
                                _exact_field(root, "To", units="ms"))
        if _exact_field(root, "From", units="ms") != "0" or duration is None:
            return False, close
        centi_ms = int(duration[1]) * 100 + int(duration[2])
        denom = width * rate
        if abs(centi_ms * denom - binary_bytes * 100000) * 2 > denom:
            return False, close
        if channel >= 9 and (
            _exact_field(node, "Units") != "Count"
            or Decimal(_exact_field(node, "InternalChannelGain")) != 1
        ):
            return False, close
        return True, close
    except (ValueError, ET.ParseError, InvalidOperation, OverflowError):
        return False, None


def write_data_coverage(expected, role_pairs):
    """Produce path-free diagnostics for the one declared WriteData window."""
    expected_set = set(expected or ())
    supplied = set(role_pairs)
    bindings_complete = bool(expected_set) and supplied == expected_set
    ref_names_complete = bindings_complete
    rows = []
    for channel in sorted(expected_set | supplied):
        roles = role_pairs.get(channel, {})
        bin_role = roles.get("bin")
        xml_role = roles.get("tsxml")
        row = {
            "channel": channel,
            "binary_kind_expected": "TACH_BIN_BYTES" if channel >= 9 else "ADC_BIN_F32",
            "selected_by_operator_manifest": channel in expected_set,
            "bin_pair_supplied": bin_role is not None,
            "tsxml_pair_supplied": xml_role is not None,
        }
        bound = []
        name_times = []
        close_times = []
        for side, label in ((0, "reference"), (1, "candidate")):
            name_time = write_data_name_time(bin_role[side][0], channel) if bin_role else None
            sidecar_verified, close = False, None
            if bin_role and xml_role:
                bin_name, bin_bytes = bin_role[side]
                xml_name, xml_bytes = xml_role[side]
                sidecar_verified, close = inspect_write_data_sidecar(
                    xml_bytes, binary_basename=bin_name, sidecar_basename=xml_name,
                    channel=channel, binary_bytes=bin_bytes)
            row[f"{label}_bin_source_name_pattern"] = name_time is not None
            row[f"{label}_tsxml_bound_to_bin"] = sidecar_verified
            row[f"{label}_tsxml_close_clock_format_valid"] = close is not None
            bound.append(sidecar_verified)
            name_times.append(name_time)
            close_times.append(close)
        if name_times[0] is None:
            ref_names_complete = False
        row["local_filename_clock_equal_for_pair"] = (
            name_times[0] == name_times[1] if None not in name_times else None)
        row["local_tsxml_close_clock_equal_for_pair"] = (
            close_times[0] == close_times[1] if None not in close_times else None)
        bindings_complete = bindings_complete and all(bound)
        rows.append(row)
    return {
        "selection_explicit": expected is not None,
        "expected_channels": sorted(expected_set),
        "unexpected_tagged_channels": sorted(supplied - expected_set) if expected is not None else [],
        "all_selected_channel_pairs_structurally_bound": bindings_complete,
        "reference_bin_channel_and_clock_patterns_complete": ref_names_complete,
        "reference_file_runtime_clock_verified": False,
        "windows_timestamp_or_filename_authenticated": False,
        "channels": rows,
    }

