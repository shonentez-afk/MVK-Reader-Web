"""Stage111Z.28B2A: optional original status-slot RAW evidence per VALUES tick.

Native R6 exporter sees whole initial register map but it MUST NOT claim
those values are current alarm states. Only post-initial parameter update
frames containing an entire 8-word control record, observed since the
previous VALUES tick, qualify for raw presentation.

Even those source-backed words DO NOT establish original Delphi state/alert
text, physical alarm severity, control parameter number, or thresholds.
"""
from __future__ import annotations

import math
import re
import struct

SCHEMA = "MVK_NATIVE_R6_CONTROL_TICK_RAW_EVIDENCE_V1"
SOURCE = "POST_INITIAL_FULL_REGISTER_UPDATE_BEFORE_VALUES_TICK"
_HEX = re.compile(r"0x[0-9A-F]{8}\Z")


def _uint(value, name, max_value=2**32-1):
    if type(value) is not int or not 0 <= value <= max_value:
        raise ValueError("CONTROL_STATUS: invalid " + name)
    return value


def _f32(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("CONTROL_STATUS: invalid " + name)
    try:
        f=struct.unpack("<f",struct.pack("<f",value))[0]
    except (OverflowError,struct.error) as exc:
        raise ValueError("CONTROL_STATUS: invalid Float32 "+name) from exc
    if f != value:
        raise ValueError("CONTROL_STATUS: not an exact source Float32 "+name)
    return f


def validated_control_status(row: dict, *, tick_frame: int,
                             previous_tick_frame: int) -> dict:
    """Validate untrusted JSON from already SHA-verified TIMELINE.

    'available' means a REAL dedicated status update frame was present;
    it does NOT mean an accepted alarm interpretation. Missing evidence
    always yields unavailable and never a fabricated normal state.
    """
    absent={
        "available": False,
        "reason": "NO_POST_SNAPSHOT_CONTROL_REGISTER_UPDATE_FOR_THIS_TICK",
        "schema": SCHEMA,
        "source": None,
        "raw_slots": [],
        "zone_and_alert_text_verified": False,
        "config_parameter_selection_verified": False,
        "original_page_status_parity": False,
    }
    record = row.get("control_status")
    if record is None:
        return absent
    if not isinstance(record,dict) or (
        record.get("schema")!=SCHEMA or record.get("source")!=SOURCE or
        record.get("status_frame_fresh_for_tick") is not True or
        record.get("zone_and_alert_text_verified") is not False or
        record.get("config_parameter_selection_verified") is not False or
        record.get("no_initial_snapshot_as_live_status") is not True
    ):
        raise ValueError("CONTROL_STATUS: incompatible provenance or false accepted zone")
    slots=record.get("raw_slots")
    if not isinstance(slots,list) or len(slots)>64:
        raise ValueError("CONTROL_STATUS: raw slot count outside 0..64")
    seen=set()
    cleaned=[]
    for item in slots:
        if not isinstance(item,dict):
            raise ValueError("CONTROL_STATUS: malformed slot")
        adc=_uint(item.get("adc"),"adc")
        slot=_uint(item.get("slot"),"slot")
        if not 1<=adc<=8 or not 1<=slot<=8 or (adc,slot) in seen:
            raise ValueError("CONTROL_STATUS: invalid or duplicate ADC/slot")
        seen.add((adc,slot))
        addr=0x2000+(adc-1)*0x200+0x130+(slot-1)*0x8
        if item.get("status_base_word")!=f"0x{addr:04X}":
            raise ValueError("CONTROL_STATUS: wrong original control register address")
        frame=_uint(item.get("source_frame_index"),"frame",2**64-1)
        if frame <= previous_tick_frame or frame >= tick_frame:
            raise ValueError("CONTROL_STATUS: initial/stale/future source frame")
        state=_uint(item.get("raw_status_u32"),"raw status")
        hx=item.get("raw_status_hex")
        if not isinstance(hx,str) or not _HEX.fullmatch(hx) or hx!=f"0x{state:08X}":
            raise ValueError("CONTROL_STATUS: status word/hex conflict")
        cleaned.append({
            "adc":adc,"slot":slot,"status_base_word":item["status_base_word"],
            "source_frame_index":frame,
            "raw_value_float32":_f32(item.get("raw_value_float32"),"value"),
            "raw_status_u32":state,"raw_status_hex":hx,
            "raw_last_transition_float32":_f32(item.get("raw_last_transition_float32"),"transition"),
            "raw_reserved_u32":_uint(item.get("raw_reserved_u32"),"reserved"),
        })
    return {
        **absent,
        "available":bool(cleaned),
        "reason":None if cleaned else absent["reason"],
        "source":SOURCE,
        "raw_slots":cleaned,
        "observed_slot_count":len(cleaned),
    }
