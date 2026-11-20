"""Independent 3-file PARAM 0x3100 GetValueText source-candidate acceptance.

This never asserts original Delphi/Win32 ANSI parity. It checks the
actual JSONL PARAM/source selection, the immutable RAW layout, and
reconstructs a third candidate CSV from typed source addresses using a
separate Python decoder, then verifies exact bytes and SHA per tick.
"""
from __future__ import annotations

from hashlib import sha256
import json

from .original_get_value_text_30 import (
    SCHEMA as FORMATTER_SCHEMA,
    get_value_text_30, source_advanced_id,
)
from .original_source_values_tick_acceptance import (
    MAX_EVENT_LINE, MAX_OUTPUT_BYTES, MAX_ROWS, _safe_regular,
    parse_source_values_3100_event, verify_source_values_tick_files,
)

SOURCE_TEXT_FORMATTER_VERSION="MVK_SOURCE_WRITEVALUES_SOURCE_TEXT_CANDIDATE_V2"
TEXT_ACCEPTANCE_SCHEMA="MVK_SOURCE_VALUES_3100_TEXT_CANDIDATE_ACCEPTANCE_V1"
ADVANCED_KINDS=("result_overload","result_buffers","result_sensor_state")


def expected_source_text_candidate_row(event:dict) -> bytes:
    # Must validate the source PARAM, all selected addresses, read flags,
    # payload SHA, original masks/order and independent RAW-line digest.
    parse_source_values_3100_event(event)
    proof=event["source_ordered_raw_tick"]
    if proof.get("source_text_candidate_formatter_version")!=SOURCE_TEXT_FORMATTER_VERSION:
        raise ValueError("GetValueText candidate source formatter version mismatch")
    row=proof["local_source_capture_hh_nn_ss_zzz"]
    for cell in proof["original_selected_cell_order"]:
        valid=cell["source_two_words_valid"]
        raw=cell["raw_dword_le_hex"]
        group=cell["source_list_group"]
        index=cell["source_cell_index"]
        typ=cell.get("source_cell_type")
        if group=="RESULT" and index<3:
            expected_type=10
            kind=ADVANCED_KINDS[index]
        elif cell["type_candidate"]=="F32_CANDIDATE":
            expected_type=0
            kind=None
        elif cell["type_candidate"]=="U32_CANDIDATE":
            expected_type=2
            kind=None
        else:
            raise ValueError("Unsupported original source GetValueText type mapping")
        if type(typ) is not int or typ!=expected_type:
            raise ValueError("Original source cell type differs from formatter")
        if kind is not None:
            if valid:
                expected_id=source_advanced_id(
                    int.from_bytes(bytes.fromhex(raw),"little"),kind)
                if cell.get("source_advanced_selected_id")!=expected_id or (
                        type(cell.get("source_advanced_selected_id")) is not int):
                    raise ValueError("Advanced original source ID extraction mismatch")
            elif "source_advanced_selected_id" in cell:
                raise ValueError("Unreceived Advanced cell cannot have extracted source ID")
        elif "source_advanced_selected_id" in cell:
            raise ValueError("Non-Advanced cell unexpectedly contains source Advanced ID")
        if not valid:
            rendered="UNKNOWN"
        else:
            rendered=get_value_text_30(
                expected_type,bytes.fromhex(raw),advanced_kind=kind).text
        row+="|"+rendered
    data=(row+"\r\n").encode("ascii")
    digest=proof.get("source_text_candidate_line_sha256")
    if not isinstance(digest,str) or digest!=sha256(data).hexdigest():
        raise ValueError("Source text GetValueText candidate row SHA mismatch")
    return data


def verify_source_values_text_candidate_files(events_jsonl,raw_layout_csv,text_candidate_csv)->dict:
    """Verify all three REAL Go stream artifacts with exact tick linkage."""
    rawreceipt=verify_source_values_tick_files(events_jsonl,raw_layout_csv)
    efile=_safe_regular(events_jsonl)
    tfile=_safe_regular(text_candidate_csv)
    count=0
    total=0
    hasher=sha256()
    with efile.open("rb") as events,tfile.open("rb") as typed:
        for record in events:
            if len(record)>MAX_EVENT_LINE:
                raise ValueError("Source GetValueText candidate event too large")
            count+=1
            if count>MAX_ROWS:
                raise ValueError("Source GetValueText candidate has too many rows")
            try:
                event=json.loads(record)
            except (UnicodeError,json.JSONDecodeError) as exc:
                raise ValueError("Source GetValueText candidate malformed event JSON") from exc
            expected=expected_source_text_candidate_row(event)
            actual=typed.read(len(expected))
            if actual!=expected:
                raise ValueError("Source GetValueText candidate CSV differs from independently decoded text")
            total+=len(actual)
            hasher.update(actual)
        if typed.read(1):
            raise ValueError("Unclaimed trailing GetValueText candidate CSV bytes")
    if count!=rawreceipt["accepted_actual_param_3100_ticks"]:
        raise ValueError("Source RAW/GetValueText text companion tick mismatch")
    return {
        "schema":TEXT_ACCEPTANCE_SCHEMA,
        "formatter_schema":FORMATTER_SCHEMA,
        "actual_param_3100_ticks":count,
        "independently_verified_candidate_bytes":total,
        "candidate_csv_sha256":hasher.hexdigest(),
        "original_delphi_text_parity_verified":False,
        "original_tlanguage_parity_verified":False,
        "original_win32_ansi_csv_byte_parity_verified":False,
        "physical_mvk01_e2e_verified":False,
        "source_three_files_verified":True,
        "instrument_commands_sent":False,
        "privacy_sensitive_original_bytes_embedded":False,
    }
