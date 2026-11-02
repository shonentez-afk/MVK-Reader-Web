"""Stage111Z.28A: validated original register fields at each VALUES tick.

READ ONLY. Source is the existing Native R6.1 exporter TIMELINE.json,
checksum-linked through EXPORT_AUDIT.output_file_sha256, and tied to one
finished Native session. No new device socket, DSP maths, RPM inference,
original clock synchronization or extra gain is performed.

Old completed archives without the Stage111Z28A schema remain readable and
return explicit "unavailable" instead of fabricated TACH or DSP status.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import re
import struct
import zipfile

TIMELINE_FILE = "TIMELINE.json"
SCHEMA = "MVK_NATIVE_R6_DSP_TACH_TICK_V1"
SOURCE = "READ_ONLY_REGISTER_IMAGE_AT_VALUES_76B_TICK"
TIME_KIND = "HOST_RECEIVE_CLOCK_NOT_DSP_SYNCHRONIZED"
MAX_TIMELINE_SIZE = 4_000_000
_HEX = re.compile(r"0x[0-9A-F]{8}\Z")


def _unsigned(value, name, max_value=2**32-1):
    if type(value) is not int or not 0 <= value <= max_value:
        raise ValueError("TIMELINE: invalid " + name)
    return value


def _clock(text):
    if not isinstance(text, str) or len(text) > 90:
        raise ValueError("TIMELINE: invalid tick clock")
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("TIMELINE: tick clock could not be parsed") from exc
    if dt.tzinfo is None:
        raise ValueError("TIMELINE: clock must include UTC zone")
    return dt


def _float32_word(v):
    if type(v) not in (float, int) or not math.isfinite(v):
        raise ValueError("TIMELINE: TACH register float is not finite")
    try:
        exact = struct.unpack("<f", struct.pack("<f", v))[0]
    except (OverflowError, struct.error) as exc:
        raise ValueError("TIMELINE: TACH value outside Float32") from exc
    if exact != v:
        raise ValueError("TIMELINE: TACH word is not an exact source Float32")
    return float(v)


def _no_duplicate_keys(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise ValueError("TIMELINE: duplicate JSON key " + key)
        result[key] = value
    return result


def read_verified_dsp_tach_tick(z: zipfile.ZipFile, audit: dict,
                                tick_index: int, tick_count: int) -> dict:
    """Return strictly source-backed global DSP/TACH data or explicit unknown."""
    no_data = {
        "available": False,
        "reason": "NO_AUTHENTICATED_DSP_TACH_REGISTER_TIMELINE",
        "source": None,
        "global_dsp_status_raw": None,
        "global_dsp_status_hex": None,
        "tachometers": [],
        "tach_frequency_hz_verified": False,
        "rpm_verified": False,
        "tick_received_utc": None,
    }
    if TIMELINE_FILE not in z.namelist():
        return no_data
    file_info = z.getinfo(TIMELINE_FILE)
    if not 0 < file_info.file_size <= MAX_TIMELINE_SIZE:
        raise ValueError("TIMELINE: invalid size")
    raw = z.read(TIMELINE_FILE)
    manifest = audit.get("output_file_sha256")
    if not isinstance(manifest, dict) or manifest.get(TIMELINE_FILE) != hashlib.sha256(raw).hexdigest():
        raise ValueError("TIMELINE: source SHA256 differs from Native EXPORT_AUDIT")
    try:
        ticks = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError("TIMELINE: invalid JSON") from exc
    if not isinstance(ticks, list) or len(ticks) != tick_count or not 0 <= tick_index < len(ticks):
        raise ValueError("TIMELINE: tick count differs from authenticated VALUES")
    audit_ticks = audit.get("values_ticks_3100")
    if audit_ticks is not None and _unsigned(audit_ticks, "VALUES ticks") != tick_count:
        raise ValueError("TIMELINE: Native audit VALUES count differs")
    audit_aux = audit.get("aux4700_updates")
    if audit_aux is not None and _unsigned(audit_aux, "AUX count") != tick_count:
        raise ValueError("TIMELINE: Native audit AUX count differs")
    prev_frame = 0
    prev_clock = None
    for n,row in enumerate(ticks):
        if not isinstance(row, dict) or _unsigned(row.get("update"), "update") != n+1:
            raise ValueError("TIMELINE: non-sequential tick updates")
        aux_frame = _unsigned(row.get("aux_frame"), "aux_frame")
        frame = _unsigned(row.get("tick_frame"), "tick_frame")
        if aux_frame == 0 or not prev_frame < aux_frame < frame:
            raise ValueError("TIMELINE: AUX/VALUES frame ordering invalid")
        clock = _clock(row.get("tick_received_utc"))
        if prev_clock is not None and clock < prev_clock:
            raise ValueError("TIMELINE: host timestamp travelled backwards")
        prev_frame, prev_clock = frame, clock
    row = ticks[tick_index]
    if "dsp_tach_schema" not in row:
        # Pre-Z28 Native timelines have only frame/tick/PC-clock pointers.
        # Never infer TACH results from VALUES CSV (which is 8x73 ADC only).
        return {**no_data, "reason": "OLD_TIMELINE_NO_REGISTER_WORDS",
                "tick_received_utc": row["tick_received_utc"]}
    if (row.get("dsp_tach_schema") != SCHEMA or
            row.get("source") != SOURCE or
            row.get("time_kind") != TIME_KIND or
            row.get("tach_units_and_rpm_verified") is not False or
            row.get("dsp_status_register_word") != "0x1020"):
        raise ValueError("TIMELINE: unknown DSP/TACH schema or unverified units claimed")
    status = _unsigned(row.get("dsp_status_raw"), "DSP word")
    status_hex = row.get("dsp_status_hex")
    if not isinstance(status_hex, str) or not _HEX.fullmatch(status_hex) or status_hex != f"0x{status:08X}":
        raise ValueError("TIMELINE: DSP raw word and hex disagree")
    fields = row.get("tach_channels")
    if not isinstance(fields, list) or len(fields) != 2:
        raise ValueError("TIMELINE: expected exactly two source TACH banks")
    tach = []
    for i,field in enumerate(fields):
        if not isinstance(field, dict):
            raise ValueError("TIMELINE: invalid tach record")
        if (field.get("tach") != i+1 or
                field.get("register_base_word") != f"0x{0x3000+i*0x100:04X}"):
            raise ValueError("TIMELINE: TACH register bank/channel mixed")
        fl = field.get("raw_float32_words_0_2")
        ui = field.get("raw_uint32_words_4_6_8")
        if not isinstance(fl,list) or len(fl)!=2 or not isinstance(ui,list) or len(ui)!=3:
            raise ValueError("TIMELINE: invalid TACH register count")
        floats = [_float32_word(x) for x in fl]
        integers = [_unsigned(x, "TACH uint32") for x in ui]
        tach.append({
            "tach": i+1,
            "register_base_word": field["register_base_word"],
            "raw_float32_words_0_2": floats,
            "raw_uint32_words_4_6_8": integers,
            "frequency_hz": None,  # Do not guess which float is real physical speed!
            "rpm": None,
            "source": SOURCE,
            "time_kind": TIME_KIND,
        })
    return {
        "available": True,
        "reason": None,
        "source": SOURCE,
        "global_dsp_status_raw": status,
        "global_dsp_status_hex": status_hex,
        "global_dsp_all_bits_zero": status==0,
        "tachometers": tach,
        "tach_frequency_hz_verified": False,
        "rpm_verified": False,
        "tick_received_utc": row["tick_received_utc"],
        "host_clock_only": True,
        "aux_frame": row["aux_frame"],
        "tick_frame": row["tick_frame"],
    }


def source_sensor_status(aux: dict | None, source_text: str):
    """Status is a device register, NOT the application FFT result.

    Keep unknown bits. Recognize known mask 0xC00 and not_ready flags but do
    NOT assign physical fault causes without a verified original status map.
    """
    data = {"raw_hex": source_text, "raw_u32": None, "not_ready": None,
            "warning_bits_0xC00": None, "has_nonzero_bits": None,
            "state": "SOURCE_TEXT_ONLY_NOT_VERIFIED"}
    if aux is None:
        return data
    raw = aux.get("status_raw")
    hx = aux.get("status_hex")
    if type(raw) is not int or not 0 <= raw <= 2**32-1 or hx != f"0x{raw:08X}":
        raise ValueError("AUX4700: raw status/hex mismatch")
    if hx.lower() != source_text.strip().lower() and not (
            raw == 0 and source_text.strip().lower() in ("ок", "ok", "0", "0x00000000")):
        raise ValueError("AUX4700: status text and register bits differ")
    flags = aux.get("not_ready")
    if not isinstance(flags,dict) or set(flags)!={"fs16","fs64","fs512"} or any(
            type(x) is not bool for x in flags.values()):
        raise ValueError("AUX4700: missing/not valid not_ready source bits")
    if flags != {"fs16":bool(raw&16),"fs64":bool(raw&32),"fs512":bool(raw&64)}:
        raise ValueError("AUX4700: not_ready flags disagree with status register")
    return {
        "raw_hex":hx, "raw_u32":raw,
        "not_ready":flags,
        "warning_bits_0xC00":f"0x{raw&0xC00:08X}",
        "has_nonzero_bits":raw!=0,
        "state":"RAW_STATUS_ZERO" if raw==0 else "RAW_STATUS_NONZERO_CAUSE_UNVERIFIED",
    }
