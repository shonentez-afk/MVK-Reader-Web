"""Independent source WriteValues 0x3100 RAW-order acceptance.

Verifies each Go tick against BOTH exported files:
SOURCE_Wxx_VALUES_3100_RECEIVED.jsonl (original source packet)
SOURCE_Wxx_VALUES_3100_RAW_LAYOUT.csv (source-ordered local RAW row).

This is an evidence validator, not vendor GetValueText/ANSI/parity.
No network, no device IO, no original PAS/IDP/SQLite/PCAP/FIR.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re

from .original_values_3100_timeline import RegisterPrefixSnapshot

SCHEMA="MVK_SOURCE_VALUES_3100_ORDERED_RAW_TICK_V1"
HEX4=re.compile(r"[0-9a-f]{8}\Z")
HEX64=re.compile(r"[0-9a-f]{64}\Z")
LOCAL_TIME=re.compile(r"\d\d:\d\d:\d\d\.\d{3}\Z")
MAX_EVENT_LINE=300_000
MAX_OUTPUT_BYTES=500_000_000
MAX_ROWS=100_000
MAX_CELLS=8*(43+6+24)+2*6
TACH_OFFSETS=(0,2,4,6,8,0xFE)
GROUPS=("SPEC","RESULT","BAND","TACH")


def _safe_regular(path):
    p=Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size>MAX_OUTPUT_BYTES:
        raise ValueError("Source WriteValues evidence file unavailable, symlink or over limit")
    return p


def _expected_address(channel,group,index):
    if type(channel) is not int or not 1<=channel<=10:
        raise ValueError("Invalid original channel")
    if type(index) is not int or index<0:
        raise ValueError("Invalid source selected original cell index")
    if channel<=8:
        if group=="SPEC" and index<43:
            return 0x2000+(channel-1)*0x200+2+2*index,"F32_CANDIDATE"
        if group=="RESULT" and index<6:
            addr=(0x120,0x120,0x120,0,0x5E,0x5C)[index]
            return (0x2000+(channel-1)*0x200+addr,
                    "U32_ADVANCED_UNFORMATTED" if index<3 else "F32_CANDIDATE")
        if group=="BAND" and index<24:
            return 0x2000+(channel-1)*0x200+0x60+2*index,"F32_CANDIDATE"
    elif group=="TACH" and index<6:
        return (0x3000+(channel-9)*0x100+TACH_OFFSETS[index],
                "F32_CANDIDATE" if index<2 else "U32_CANDIDATE")
    raise ValueError("Selected GetValueText cell does not belong to its list")


def parse_source_values_3100_event(event:dict)->dict:
    if not isinstance(event,dict):
        raise ValueError("Source WriteValues requires event object")
    if event.get("param_address")!="0x3100":
        raise ValueError("Source WriteValues is not a real PARAM 0x3100 event")
    for field in ("frame_index","source_values_tick_index","register_words"):
        if type(event.get(field)) is not int or not 0<=event[field]<1<<64:
            raise ValueError("Source WriteValues invalid frame/tick/word count")
    raw=event.get("param_payload_le_hex")
    if (not isinstance(raw,str) or
            len(raw)!=event["register_words"]*4 or
            any(c not in "0123456789abcdef" for c in raw)):
        raise ValueError("Source WriteValues invalid exact original payload")
    digest=event.get("param_payload_sha256")
    if not isinstance(digest,str) or digest!=sha256(bytes.fromhex(raw)).hexdigest():
        raise ValueError("Source WriteValues original PARAM payload SHA mismatch")
    proof=event.get("source_ordered_raw_tick")
    if not isinstance(proof,dict) or proof.get("schema")!=SCHEMA:
        raise ValueError("Source WriteValues raw tick schema missing")
    for flag in ("original_get_value_text_parity_verified",
                 "original_delphi_local_time_parity_verified",
                 "original_delphi_values_csv_byte_parity_verified"):
        if proof.get(flag) is not False:
            raise ValueError("Source WriteValues falsely claimed original Delphi parity")
    local=proof.get("local_source_capture_hh_nn_ss_zzz")
    if not isinstance(local,str) or not LOCAL_TIME.fullmatch(local):
        raise ValueError("Source WriteValues malformed original time candidate")
    try:
        datetime.strptime(local,"%H:%M:%S.%f")
    except ValueError as exc:
        raise ValueError("Source WriteValues invalid local capture clock") from exc
    cells=proof.get("original_selected_cell_order")
    if not isinstance(cells,list) or not 1<=len(cells)<=MAX_CELLS:
        raise ValueError("Source WriteValues invalid selected original cell count")
    row=local
    known=0
    unknown=0
    last_key=None
    for cell in cells:
        if not isinstance(cell,dict):
            raise ValueError("Source WriteValues invalid raw cell")
        ch=cell.get("channel")
        group=cell.get("source_list_group")
        index=cell.get("source_cell_index")
        address,kind=_expected_address(ch,group,index)
        if cell.get("type_candidate")!=kind:
            raise ValueError("Source WriteValues invented source register type")
        if (address is None and "source_word_address" in cell or
                address is not None and cell.get("source_word_address")!=address):
            raise ValueError("Source WriteValues original register address mismatch")
        key=(ch,GROUPS.index(group),index)
        if last_key is not None and key<=last_key:
            raise ValueError("Source WriteValues wrong original channel/list/cell order")
        last_key=key
        v=cell.get("raw_dword_le_hex")
        if v is None:
            if cell.get("source_two_words_valid") is not False:
                raise ValueError("Source WriteValues missing source word marked valid")
            unknown+=1
            row+="|UNKNOWN"
        else:
            if (address is None or not isinstance(v,str) or not HEX4.fullmatch(v) or
                    cell.get("source_two_words_valid") is not True):
                raise ValueError("Source WriteValues unsupported or partial original DWORD")
            known+=1
            row+="|RAW_"+kind+":"+v
    if (type(proof.get("source_known_full_register_dwords")) is not int or
            proof["source_known_full_register_dwords"]!=known or
            type(proof.get("unknown_or_unmapped_selected_cells")) is not int or
            proof["unknown_or_unmapped_selected_cells"]!=unknown):
        raise ValueError("Source WriteValues selected source valid-word counts mismatch")
    rawrow=(row+"\r\n").encode("ascii")
    # The old compatibility editor has 73 VALUES boxes; original
    # bWriteValuesClick copies only 6+24+6=36. Do not silently
    # interpret legacy index 36..72 as a vendor list field.
    legacy=proof.get("non_original_legacy_73_flag_bits_ignored",0)
    if type(legacy) is not int or not 0<=legacy<=37:
        raise ValueError("Source WriteValues invalid legacy flag count")
    if not isinstance(proof.get("source_raw_layout_line_sha256"),str) or (
            proof["source_raw_layout_line_sha256"]!=sha256(rawrow).hexdigest()):
        raise ValueError("Source WriteValues row bytes/SHA mismatch")
    return {
        "tick_index":event["source_values_tick_index"],
        "frame_index":event["frame_index"],
        "source_ordered_cells":len(cells),
        "source_valid_raw_dwords":known,
        "unmapped_or_missing_cells":unknown,
        "raw_line_bytes":rawrow,
        "row_sha256":proof["source_raw_layout_line_sha256"],
        "original_get_value_text_parity_verified":False,
        "original_win32_time_parity_verified":False,
    }


def verify_source_values_prefix_event(event, *, prefix, channels, spec, values)->dict:
    """Check actual native selected cells against independently replayed RAW.

    Layout/SHA alone cannot detect a later descriptor's value leaking into
    an earlier row. Old trigger-only evidence never obtains this proof.
    """
    if not isinstance(prefix, RegisterPrefixSnapshot):
        raise ValueError("Source WriteValues missing independent trigger-prefix replay")
    parsed = parse_source_values_3100_event(event)
    cells = event["source_ordered_raw_tick"]["original_selected_cell_order"]
    selected = []
    for channel in range(1, 9):
        if not channels[channel - 1]:
            continue
        selected.extend((channel, "SPEC", i) for i in range(43) if spec[i])
        selected.extend((channel, "RESULT", i) for i in range(6) if values[i])
        selected.extend((channel, "BAND", i) for i in range(24) if values[i + 6])
    for channel in (9, 10):
        if channels[channel - 1]:
            selected.extend((channel, "TACH", i) for i in range(6) if values[i + 30])
    if [(c["channel"], c["source_list_group"], c["source_cell_index"])
            for c in cells] != selected:
        raise ValueError("Source WriteValues selected trigger-prefix mask mismatch")
    if event["source_ordered_raw_tick"].get(
            "non_original_legacy_73_flag_bits_ignored", 0) != sum(values[36:]):
        raise ValueError("Source WriteValues legacy mask count mismatch")
    for cell, (channel, group, index) in zip(cells, selected):
        address, kind = _expected_address(channel, group, index)
        raw = prefix.dword_hex(address, current=group == "TACH" and index == 5)
        if cell.get("raw_dword_le_hex") != raw:
            raise ValueError("Source WriteValues selected value differs from RAW trigger prefix")
        cell_type = (10 if kind == "U32_ADVANCED_UNFORMATTED"
                     else 2 if kind == "U32_CANDIDATE" else 0)
        if type(cell.get("source_cell_type")) is not int or cell["source_cell_type"] != cell_type:
            raise ValueError("Source WriteValues source cell type mismatch")
        advanced = None
        if cell_type == 10 and raw is not None:
            word = int.from_bytes(bytes.fromhex(raw), "little")
            start, width = ((0, 1), (4, 3), (10, 2))[index]
            advanced = (word >> start) & ((1 << width) - 1)
        if advanced is not None:
            if type(cell.get("source_advanced_selected_id")) is not int or cell["source_advanced_selected_id"] != advanced:
                raise ValueError("Source WriteValues Advanced selector differs from RAW trigger prefix")
        elif "source_advanced_selected_id" in cell:
            raise ValueError("Source WriteValues unexpected Advanced selector")
    return parsed


def verify_source_values_tick_files(events_jsonl,raw_layout_csv)->dict:
    """Read two actual local files; SHA-check each tick without RAM blowup."""
    events=_safe_regular(events_jsonl)
    layout=_safe_regular(raw_layout_csv)
    if not events.stat().st_size:
        raise ValueError("No original PARAM 0x3100 event was written")
    count=known=unknown=0
    hd=sha256()
    last_frame=last_tick=-1
    with events.open("rb") as f,layout.open("rb") as raw:
        for record in f:
            if len(record)>MAX_EVENT_LINE:
                raise ValueError("Original selected WriteValues JSONL row too long")
            count+=1
            if count>MAX_ROWS:
                raise ValueError("Too many original WriteValues rows")
            try:
                entry=json.loads(record)
            except (UnicodeError,json.JSONDecodeError) as exc:
                raise ValueError("Original WriteValues event JSONL corrupt") from exc
            r=parse_source_values_3100_event(entry)
            if r["frame_index"]<=last_frame or r["tick_index"]<=last_tick:
                raise ValueError("Original WriteValues tick/frame cursor reordered")
            last_frame,last_tick=r["frame_index"],r["tick_index"]
            expect=r.pop("raw_line_bytes")
            actual=raw.read(len(expect))
            if actual!=expect:
                raise ValueError("Original source tick CSV differs from SHA-bound JSON event")
            hd.update(actual)
            known+=r["source_valid_raw_dwords"]
            unknown+=r["unmapped_or_missing_cells"]
        if raw.read(1):
            raise ValueError("Unclaimed trailing original source tick CSV bytes")
    return {
        "schema":"MVK_SOURCE_VALUES_3100_ORDERED_RAW_ACCEPTANCE_V1",
        "accepted_actual_param_3100_ticks":count,
        "source_valid_raw_dwords":known,
        "unmapped_or_missing_cells":unknown,
        "paired_csv_sha256":hd.hexdigest(),
        "original_delphi_get_value_text_parity_verified":False,
        "original_delphi_csv_byte_parity_verified":False,
        "physical_mvk01_e2e_verified":False,
        "no_device_commands":True,
        "no_paths_or_original_payloads_in_report":True,
    }
