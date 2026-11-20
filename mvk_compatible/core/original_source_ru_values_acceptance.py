"""Independent real PARAM-3100 Russian VALUES companion four-file verifier.

Never blindly attributes the original 2026-10-28 VALUES to a different
recording. This checks NEW live evidence JSONL/RAW/ASCII/CP1251 from the
same source tick. Distinct from the Delphi/Win32 original-byte oracle.

Only private local input paths; exports a privacy-safe receipt.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from .original_source_values_text_candidate_acceptance import (
    verify_source_values_text_candidate_files,
)
from .original_source_values_tick_acceptance import (
    MAX_EVENT_LINE,MAX_ROWS,_safe_regular,parse_source_values_3100_event,
)
from .original_ru_csv_layout import (
    PROFILE,source_ru_values_header,source_ru_typed_text,
)

SOURCE="MVK_SOURCE_RU_VALUES_3100_FOUR_FILE_ACCEPTANCE_V1"
RU_VERSION="MVK_SOURCE_VALUES_3100_CP1251_RU_LAYOUT_CANDIDATE_V1"
ADVANCED=("result_overload","result_buffers","result_sensor_state")


def original_source_ru_values_row(event:dict)->bytes:
    parse_source_values_3100_event(event)
    proof=event["source_ordered_raw_tick"]
    if proof.get("source_ru_profile_candidate_formatter_version")!=RU_VERSION:
        raise ValueError("Source RU VALUES formatter version mismatch")
    values=[proof["local_source_capture_hh_nn_ss_zzz"]]
    for cell in proof["original_selected_cell_order"]:
        group=cell["source_list_group"]
        index=cell["source_cell_index"]
        raw=cell["raw_dword_le_hex"]
        inferred=10 if group=="RESULT" and index<3 else (
            2 if group=="TACH" and index>=2 else 0)
        if (type(cell.get("source_cell_type")) is not int or
                cell["source_cell_type"]!=inferred):
            raise ValueError("Source RU VALUES cell type differs from original dispatch")
        if inferred==10:
            if raw is not None:
                from .original_get_value_text_30 import source_advanced_id
                selected=source_advanced_id(int.from_bytes(bytes.fromhex(raw),"little"),
                                            ADVANCED[index])
                if (type(cell.get("source_advanced_selected_id")) is not int or
                        cell["source_advanced_selected_id"]!=selected):
                    raise ValueError("Source RU VALUES Advanced selected bit ID mismatch")
            elif "source_advanced_selected_id" in cell:
                raise ValueError("Source RU VALUES missing DWORD cannot have Advanced ID")
        elif "source_advanced_selected_id" in cell:
            raise ValueError("Source RU VALUES non-Advanced with fake ID")
        values.append(source_ru_typed_text(group,index,raw))
    rawline=("|".join(values)+"\r\n").encode("cp1251","strict")
    digest=proof.get("source_ru_profile_candidate_line_sha256")
    if not isinstance(digest,str) or digest!=sha256(rawline).hexdigest():
        raise ValueError("Source RU VALUES row SHA mismatch")
    return rawline


def verify_original_source_ru_values_files(
    events_jsonl,raw_layout_csv,plain_text_csv,ru_profile_csv,
    *,audit_json=None,
)->dict:
    """Check four source-bound files and optional finalized window audit.

    One selected source window per call; the four files must be from the
    same local directory and contain the same number of accepted ticks.
    """
    paths=[_safe_regular(p) for p in (
        events_jsonl,raw_layout_csv,plain_text_csv,ru_profile_csv)]
    if len({p.parent.resolve() for p in paths})!=1:
        raise ValueError("Source RU VALUES proof files belong to different directories")
    old=verify_source_values_text_candidate_files(*paths[:3])
    expected_ticks=old["actual_param_3100_ticks"]
    if expected_ticks<1:
        raise ValueError("Source RU VALUES cannot validate a header with no actual tick")
    digest=sha256()
    count=total=0
    signature=None
    with paths[0].open("rb") as received,paths[3].open("rb") as ru:
        for event_line in received:
            if len(event_line)>MAX_EVENT_LINE:
                raise ValueError("Source RU VALUES JSONL event too long")
            count+=1
            if count>MAX_ROWS:
                raise ValueError("Source RU VALUES too many accepted events")
            try:
                event=json.loads(event_line)
            except (UnicodeError,json.JSONDecodeError) as exc:
                raise ValueError("Source RU VALUES malformed event JSONL") from exc
            cells=event["source_ordered_raw_tick"]["original_selected_cell_order"]
            current=tuple(
                (c["channel"],c["source_list_group"],c["source_cell_index"])
                for c in cells)
            if signature is None:
                signature=current
                header=source_ru_values_header(cells)
                actual=ru.read(len(header))
                if actual!=header:
                    raise ValueError("Source RU VALUES header not the original CP1251 selection")
                total+=len(actual)
                digest.update(actual)
            elif current!=signature:
                raise ValueError("Source RU VALUES original selected cell masks changed mid-stream")
            expected=original_source_ru_values_row(event)
            actual=ru.read(len(expected))
            if actual!=expected:
                raise ValueError("Source RU VALUES CSV row differs from typed DWORDs")
            total+=len(actual)
            digest.update(actual)
        if ru.read(1):
            raise ValueError("Source RU VALUES has trailing unclaimed bytes")
    if count!=expected_ticks:
        raise ValueError("Source RU VALUES accepted 0x3100 tick count differs")
    filename=paths[3].name
    if audit_json is not None:
        auditpath=_safe_regular(audit_json)
        if auditpath.parent.resolve()!=paths[0].parent.resolve():
            raise ValueError("Source RU VALUES audit belongs to another run directory")
        try:
            audit=json.loads(auditpath.read_bytes())
        except (ValueError,UnicodeError) as exc:
            raise ValueError("Source RU VALUES audit malformed JSON") from exc
        if not isinstance(audit,dict) or not isinstance(audit.get("windows"),list):
            raise ValueError("Source RU VALUES audit windows missing")
        matches=[w for w in audit["windows"] if isinstance(w,dict) and
                 w.get("source_ru_profile_candidate_name")==filename]
        if len(matches)!=1:
            raise ValueError("Source RU VALUES audit candidate window ambiguous")
        w=matches[0]
        if (w.get("source_ru_profile_candidate_rows")!=count or
            w.get("source_ru_profile_candidate_bytes")!=total or
            w.get("source_ru_profile_candidate_sha256")!=digest.hexdigest() or
            w.get("original_ru_profile_csv_byte_parity_verified") is not False):
            raise ValueError("Source RU VALUES final audit does not match actual bytes")
    return {
        "schema":SOURCE,
        "profile":PROFILE,
        "actual_param_3100_ticks":count,
        "independently_rebuilt_ru_csv_bytes":total,
        "original_header_and_all_rows_sha256":digest.hexdigest(),
        "original_selected_source_fields":len(signature or ()),
        "all_four_stream_files_same_run_verified":True,
        "original_ru_advanced_source_locale_used":True,
        "source_cp1251_crlf_pipe_verified":True,
        "original_win32_delphi_float_rounding_parity_verified":False,
        "original_delphi_get_value_text_30_byte_parity_verified":False,
        "physical_mvk01_live_1to1_parity_verified":False,
        "instrument_commands_sent":False,
        "operator_measurements_embedded":False,
    }
