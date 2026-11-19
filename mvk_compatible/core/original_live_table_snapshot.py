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
    """Original _Unit128:0084E020 has TWO independent sections.

    1. ADC header (checked of 8), 24 ResultAdcCells + 43
       ResultAdcBandCells; each data row ends in source GetUnits.
    2. EMPTY line; separate TACH header (checked of 2), then exactly 6
       ResultTachCellList rows; also with a final source GetUnits.
    Original TLanguage labels, units and GetValueText remain unverified;
    we do NOT mix ADC and TACH columns into a fabricated 10-wide grid.
    """
    if not live_table_snapshot_ready(status):
        raise ValueError("Source TABLE: no fresh, source-validated PARAM bank")
    bank=status["source_live_page_status_banks"]
    selected_indices=_check_channels(selected)
    adcs=tuple(i for i in selected_indices if i<8)
    tachs=tuple(i-8 for i in selected_indices if i>=8)
    if len(bank["adc"])!=8 or len(bank["tach"])!=2:
        raise ValueError("Source TABLE: wrong register bank counts")
    # A trailing empty cell for xParamName|xChannelN| mirrors the source
    # WriteLn header (which has no unit label). On data rows the final
    # cell is original GetUnits, left unknown without original metadata.
    adc_header=("Параметр (RAW)",)+tuple(
        f"АЦП {i+1}" for i in adcs)+("",)
    rows=[adc_header]
    for n in range(24):
        rows.append((
            f"ResultAdcCells {n+1} · RMS +0x{0x60+2*n:03X}",
            *(_cell(bank["adc"][i]["rms_24_raw_f32_le"][n],"Float32")
              for i in adcs),
            UNAVAILABLE,  # GetUnits from the original TMvkCellList
        ))
    for n in range(43):
        rows.append((
            f"ResultAdcBandCells {n+1} · 43-band +0x{2+2*n:03X}",
            *(_cell(bank["adc"][i]["bands_43_raw_f32_le"][n],"Float32")
              for i in adcs),
            UNAVAILABLE,
        ))
    rows.append(())  # original 0084E478..0084E48A writes a blank line
    tach_header=("Параметр (RAW)",)+tuple(
        f"Тахометр {i+1}" for i in tachs)+("",)
    rows.append(tach_header)
    for n,offset in enumerate((0,2,4,6,8,0xFE)):
        rows.append((
            f"ResultTachCellList {n+1} · +0x{offset:02X}",
            *(_cell(
                bank["tach"][i]["source_field_0_2_4_6_8_fe_raw_le"][n],
                "Float32" if n<2 else "UInt32") for i in tachs),
            UNAVAILABLE,
        ))
    if len(rows)!=MAX_TABLE_ROWS+3:
        raise ValueError("Source TABLE original 2-section count mismatch")
    if any(len(row)!=(2+len(adcs)) for row in rows[:68]):
        raise ValueError("Source TABLE original ADC row column count mismatch")
    if rows[68]!=() or any(
            len(row)!=(2+len(tachs)) for row in rows[69:]):
        raise ValueError("Source TABLE original TACH row column count mismatch")
    actual_data=tuple(rows[1:68])+tuple(rows[70:])
    if not any(
        v!=UNAVAILABLE for row in actual_data for v in row[1:-1]):
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
    # Two original table sections: checked ADC columns, blank row,
    # checked TACH columns. The final cell on data rows is GetUnits.
    data="sep=|\r\n"+"".join("|".join(row)+"\r\n" for row in rows)
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
        # Both source headers, 67 ADC rows, separator and 6 TACH
        # rows must reopen exactly, not merely pass a SHA comparison.
        assert len(rows)==MAX_TABLE_ROWS+3
        checks=(readback.decode(FORMAT).splitlines())
        if (len(checks)!=len(rows)+1 or checks[0]!="sep=|" or
                tuple(checks[1:])!=tuple("|".join(x) for x in rows)):
            raise ValueError("Source TABLE roundtrip row/column mismatch")
        return {
            "source":TABLE_SOURCE,
            "table_saved":True,
            "original_table_layout_sep_pipe_verified":True,
            "source_table_row_count":MAX_TABLE_ROWS,
            "source_table_section_count":2,
            "source_adc_data_rows":67,
            "source_tach_data_rows":6,
            "source_adcs_in_first_section":[i+1 for i in _check_channels(selected) if i<8],
            "source_tachs_in_second_section":[i-7 for i in _check_channels(selected) if i>=8],
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
