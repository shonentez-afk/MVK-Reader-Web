"""One-shot original bWriteTableClick source-layout local snapshot for Mode2.

Private three-source reconstruction:
  _Unit128.pas:0084E020: TABLE-yyyy-mm-dd--hh-nn-ss.csv, sep=|,
  xParamName, checked 8 ADC + 2 TACH, GetValueText and Units per row.
  _Unit115.pas:007CF3A8/007CF4A4/007CE6E4: GetValueText dispatches 30
  original vendor cell types and returns '####' when Data is absent.
  mvkview.idp and mvk_idr(1).sqlite confirm TMvkCellList and call edges.

We preserve the original TABLE shape and time naming, but mark the
values RAW instead of inventing vendor-specific GetValueText/units.
This is deliberately NOT an original Delphi byte-for-byte CSV.

Only an ALREADY VALIDATED same-run Go status, never a second TCP socket.
Never sends a device command, reads files from the instrument, rewrites
incoming.raw, or appends to WriteData/WriteValues event windows.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
import re

from .original_connected_status import connected_system_status
from .original_live_result_registers import (
    SCHEMA, _raw_f32, _raw_u32, _f32_text, _u32_text,
)
from .original_pagestatus_source import UNAVAILABLE

TABLE_SOURCE="MVK_MODE2_SOURCE_LAYOUT_LIVE_RAW_TABLE_V1"
TABLE_PREFIX="TABLE-"
_ALLOWED_BASENAME=re.compile(r"TABLE-\d{4}-\d{2}-\d{2}--\d{2}-\d{2}-\d{2}(?:-[0-9]{1,3})?\.csv\Z")
MAX_TABLE_BYTES=250_000
MAX_TABLE_ROWS=24+43+6
MAX_CAPTURE_BYTES=(1<<64)-1
FORMAT="utf-8-sig"  # not asserted as Win32/TTextRec system ANSI code page


def live_table_snapshot_ready(status:dict|None)->bool:
    if not isinstance(status,dict):
        return False
    banks=status.get("source_live_page_status_banks")
    try:
        health=connected_system_status(status)
    except (TypeError,ValueError,KeyError):
        return False
    return bool(
        status.get("source_live_page_status_banks_verified") is True and
        isinstance(banks,dict) and banks.get("schema")==SCHEMA and
        type(banks.get("accepted_param_frames")) is int and
        banks["accepted_param_frames"]>0 and
        type(banks.get("known_complete_dwords")) is int and
        banks["known_complete_dwords"]>0 and
        status.get("phase")=="RECORDING" and
        status.get("capture_only") is False and
        status.get("source_tcp_multi_socket") is False and
        status.get("source_tcp_connection_count")==1 and
        status.get("source_rate_transition_during_live",False) is False and
        status.get("source_system_error_observed",False) is False and
        health.connection_verified and not health.data_integrity_alert
    )


def _check_channels(selected):
    if (not isinstance(selected,(tuple,list)) or len(selected)!=10 or
            any(type(v) is not bool for v in selected)):
        raise ValueError("Source TABLE requires exactly ten original channel flags")
    if not any(selected):
        raise ValueError("Source TABLE has no selected channels")
    return tuple(i for i,v in enumerate(selected) if v)


def _cell(word,kind):
    if kind=="Float32":
        return _f32_text(word)
    if kind=="UInt32":
        return _u32_text(word)
    raise ValueError("Source TABLE has unsupported original cell type")


def build_live_table_rows(status:dict, selected)->tuple[tuple[str,...],...]:
    """Return source-shaped pipe rows, not the unverified Delphi text bytes."""
    if not live_table_snapshot_ready(status):
        raise ValueError("Source TABLE: no fresh, source-validated PARAM bank")
    bank=status["source_live_page_status_banks"]
    selected_indices=_check_channels(selected)
    if len(bank["adc"])!=8 or len(bank["tach"])!=2:
        raise ValueError("Source TABLE: wrong register bank counts")
    # Source first header is xParamName|xChannelN.., with only checked
    # channels. We explicitly use RAW suffix to avoid claimed TLanguage
    # localization parity.
    header=("Параметр (RAW)",)+tuple(
        f"АЦП {i+1}" if i<8 else f"Тахометр {i-7}"
        for i in selected_indices)
    rows=[header]
    def adc_cell(i,key,n):
        return _cell(bank["adc"][i][key][n],"Float32") if i<8 else UNAVAILABLE
    for n in range(24):
        row=(f"ResultAdcCells {n+1} · RMS +0x{0x60+2*n:03X}",)+tuple(
            adc_cell(i,"rms_24_raw_f32_le",n)
            for i in selected_indices)
        rows.append(row)
    for n in range(43):
        row=(f"ResultAdcBandCells {n+1} · 43-band +0x{2+2*n:03X}",)+tuple(
            adc_cell(i,"bands_43_raw_f32_le",n)
            for i in selected_indices)
        rows.append(row)
    offsets=(0,2,4,6,8,0xFE)
    for n,offset in enumerate(offsets):
        row=(f"ResultTachCellList {n+1} · +0x{offset:02X}",)+tuple(
            (_cell(
                bank["tach"][i-8]["source_field_0_2_4_6_8_fe_raw_le"][n],
                "Float32" if n<2 else "UInt32")
             if i>=8 else UNAVAILABLE)
            for i in selected_indices)
        rows.append(row)
    if len(rows)!=1+MAX_TABLE_ROWS or any(
            len(r)!=1+len(selected_indices) for r in rows):
        raise ValueError("Source TABLE incomplete rows/columns")
    if all(all(v==UNAVAILABLE for v in row[1:]) for row in rows[1:]):
        raise ValueError("Source TABLE selected channels contain no known PARAM values")
    return tuple(rows)


def export_live_table_snapshot(status:dict,selected,filename,
                               *,expected_session_id:str|None=None)->dict:
    """Save one local snapshot, verify every written byte; no source writes.

    Status must be the already-validated sole Native run. Caller compares
    the current bound run again after Qt's file picker closes.
    """
    if expected_session_id is not None and (
            status.get("session_id")!=expected_session_id or
            not isinstance(expected_session_id,str)):
        raise ValueError("Source TABLE selected foreign run")
    rows=build_live_table_rows(status,selected)
    target=Path(filename).absolute()
    if (target.suffix.lower()!=".csv" or target.is_symlink() or
            target.exists() or not target.parent.is_dir() or
            target.parent.is_symlink()):
        raise ValueError("Source TABLE: choose a NEW local CSV in an existing directory")
    if not _ALLOWED_BASENAME.fullmatch(target.name):
        raise ValueError("Source TABLE: filename must use original TABLE-time naming")
    # Go artifacts may not be overwritten, even if a malicious caller
    # selects a misleading .csv name inside a capture run.
    data="sep=|\r\n"+"|".join(rows[0])+"|\r\n"+ "".join(
        "|".join(row)+"|\r\n" for row in rows[1:])
    raw=data.encode(FORMAT)
    if not 0<len(raw)<=MAX_TABLE_BYTES:
        raise ValueError("Source TABLE exceeds safe local snapshot limit")
    created=False
    try:
        with target.open("xb") as f:
            created=True
            f.write(raw)
            f.flush()
        readback=target.read_bytes()
        if readback!=raw:
            raise ValueError("Source TABLE local byte readback differs")
        # All 74 lines, not just the SHA or first row.
        assert len(rows)==74
        checks=(readback.decode(FORMAT).splitlines())
        if (len(checks)!=len(rows)+1 or checks[0]!="sep=|" or
                tuple(checks[1:])!=tuple("|".join(x)+"|" for x in rows)):
            raise ValueError("Source TABLE roundtrip row/column mismatch")
        return {
            "source":TABLE_SOURCE,
            "table_saved":True,
            "original_table_layout_sep_pipe_verified":True,
            "source_table_row_count":len(rows)-1,
            "source_table_selected_channels":[i+1 for i in _check_channels(selected)],
            "source_param_frames":status["source_live_page_status_banks"][
                "accepted_param_frames"],
            "source_tcp_connection_count":status["source_tcp_connection_count"],
            "source_capture_frames":status["frames_decoded"],
            "source_capture_raw_bytes":status["raw_bytes"],
            "csv_sha256":sha256(raw).hexdigest(),
            "readback_all_rows_verified":True,
            "original_delphi_table_byte_parity_verified":False,
            "original_get_value_text_parity_verified":False,
            "source_register_image_was_not_modified":True,
            "instrument_commands_sent":False,
            "original_tmvkthread_write_table_executed":False,
            "contains_operator_file_path":False,
            "csv_encoding_kind":"LOCAL_UTF8_BOM_NOT_DELPHI_ANSI_PARITY",
        }
    except Exception:
        if created:
            target.unlink(missing_ok=True)
        raise
