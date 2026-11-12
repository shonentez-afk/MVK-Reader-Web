"""Stage111Z31BU: original PageStatus four-grid controller + verified export.

Operator-owned _Unit128.pas:
  0084761A -> tabStatus                    (mode 0)
  008476B7 -> tabAlarmResult               (mode 1)
  0084779C -> tabAllResult                 (modes 2,3,4)
  008479FD -> tabResult + SpecSeries       (modes 5..12)
  00847D58 -> tabResult, TACH              (modes 13,14)
The original Delphi tcStatus was 2 tabs at DESIGN time, extended to
15 runtime modes. chResult (4,42,400,720) / splResult (404,42,8,720).
Original chResultMouseMove (0084AA20) maps x to band index 0..42 and
displays the nominal Float32 frequency together with an actual bar value.

This module does not fabricate sensor status, TACH RPM or device writes.
It only renders independently source-verified Native R6.1 VALUES/AUX or
explicit unavailable entries for uncalibrated Direct BIN/TSXML.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from hashlib import sha256
import math
from pathlib import Path

from .offline_measurement_flow import OfflineMeasurementFlow
from .original_pagestatus_source import StatusTable,MODE_NAMES,source_pagestatus_table
from .original_config_idp_tables import source_octave_frequencies_float32

SOURCE="ORIGINAL_IDR_PAGESTATUS_FOUR_TABLES_SOURCE_FUNCTIONAL_STAGE111Z31BU"
ORIGINAL_STATUS_TABS_DESIGN_TIME=2
ORIGINAL_STATUS_TABS_RUNTIME=len(MODE_NAMES)
ORIGINAL_STATUS_CHART_RECT=(4,42,400,720)
ORIGINAL_STATUS_SPLITTER_RECT=(404,42,8,720)
ORIGINAL_STATUS_GRIDS=("tabStatus","tabAlarmResult","tabAllResult","tabResult")
SOURCE_FREQUENCIES=source_octave_frequencies_float32()
MAX_CSV_BYTES=1_000_000
MAX_CSV_ROWS=128
MODE_GRID=(
    ("tabStatus","tabAlarmResult")
    +("tabAllResult",)*3
    +("tabResult",)*10
)


@dataclass(frozen=True)
class OriginalStatusProjection:
    """Single verified source tick/mode driving FOUR physical Qt grids."""
    model:StatusTable
    table_name:str
    chart_visible:bool
    source_digest:str|None
    tick_index:int|None
    session_serial:str|None
    provenance:str=SOURCE

    def __post_init__(self):
        i=self.model.index
        if type(i) is not int or not 0<=i<ORIGINAL_STATUS_TABS_RUNTIME:
            raise ValueError("Original PageStatus requires mode 0..14")
        if self.table_name!=MODE_GRID[i]:
            raise ValueError("Original status mode mapped to wrong Delphi grid")
        if self.chart_visible and (i<5 or i>12 or
                                   self.model.bands_for_plot is None or
                                   len(self.model.bands_for_plot)!=43):
            raise ValueError("Unverified original 43-band chart")
        if self.source_digest is not None and (
                len(self.source_digest)!=64 or any(
                c not in "0123456789abcdef" for c in self.source_digest)):
            raise ValueError("Invalid source fingerprint")
        if len(self.model.rows)>MAX_CSV_ROWS:
            raise ValueError("Original status table unusually large")

    @property
    def mode(self):
        return self.model.index

    def cursor(self,position:int):
        """Original chResultMouseMove nearest index + original 43 Float32 Hz."""
        if type(position) is not int or not 0<=position<43:
            raise ValueError("Original chart bin index outside 0..42")
        if not self.chart_visible or self.model.bands_for_plot is None:
            raise ValueError("Original chart not active for this source mode")
        y=self.model.bands_for_plot[position]
        if not isinstance(y,(float,int)) or isinstance(y,bool) or not math.isfinite(y):
            raise ValueError("Unverified chart band amplitude")
        return {
            "source":SOURCE,
            "adc":self.mode-4,
            "band_index":position,
            "nominal_hz_float32":SOURCE_FREQUENCIES[position],
            "verified_source_band_value":float(y),
            "source_tick_index":self.tick_index,
            "original_canvas_mouse_pixel_parity_verified":False,
        }

    def receipt(self):
        return {
            "source":SOURCE,
            "mode":self.mode,
            "original_grid_name":self.table_name,
            "verified_bins":43 if self.chart_visible else 0,
            "rows":len(self.model.rows),
            "columns":len(self.model.headers),
            "source_digest":self.source_digest,
            "source_tick_index":self.tick_index,
            "direct_bin_has_values":False,
            "device_io_performed":False,
            "original_delphi_pixel_parity_verified":False,
        }


def source_status_projection(mode:int,flow:OfflineMeasurementFlow|None):
    if type(mode) is not int or not 0<=mode<15:
        raise ValueError("Original tcStatus has exactly 15 runtime modes")
    if flow is None:
        model=source_pagestatus_table(mode,None)
        return OriginalStatusProjection(
            model,MODE_GRID[mode],False,None,None,None)
    if not isinstance(flow,OfflineMeasurementFlow):
        raise ValueError("Verified original Core flow is required")
    record=flow.source_record()  # revalidate local BIN, TSXML, ZIP SHA
    model=source_pagestatus_table(mode,flow.status_snapshot())
    visible=bool(5<=mode<=12 and model.bands_for_plot is not None)
    return OriginalStatusProjection(
        model,MODE_GRID[mode],visible,
        record["source_bin_sha256"],
        None if flow.direct_bin else flow.tick_index,
        flow.session.serial,
    )


def _excel_safe(value):
    s=str(value)
    if len(s)>512 or any(c in s for c in ("\x00","\r","\n")):
        raise ValueError("Original PageStatus contains unsafe output text")
    if s.lstrip().startswith(("=","+","-","@")):
        return "'"+s
    return s


def export_verified_status_csv(flow:OfflineMeasurementFlow,mode:int,destination):
    """Real local Save As, independent readback, never an original device write.

    Original Status page has NO bStatusSave; this is an explicitly
    compatible EXTRA action, not a falsely restored Delphi control.
    """
    if flow.direct_bin:
        raise ValueError("No verified Native R6.1 VALUES/AUX in direct BIN source")
    proj=source_status_projection(mode,flow)
    path=Path(destination).absolute()
    if (path.suffix.lower()!=".csv" or path.is_symlink()
            or path.exists() or not path.parent.is_dir()
            or path.parent.is_symlink()):
        raise ValueError("Choose NEW local CSV, without overwriting source")
    if path==getattr(flow.session,"path",None):
        raise ValueError("Cannot export over original recording")
    rows=(tuple(_excel_safe(x) for x in proj.model.headers),)+tuple(
        tuple(_excel_safe(v) for v in row) for row in proj.model.rows)
    if len(rows)>MAX_CSV_ROWS+1:
        raise ValueError("Source table too large")
    created=False
    try:
        with path.open("x",encoding="utf-8-sig",newline="") as f:
            created=True
            writer=csv.writer(f,delimiter=";")
            writer.writerows(rows)
        if path.stat().st_size>MAX_CSV_BYTES:
            raise ValueError("PageStatus source CSV exceeds safe size")
        with path.open(encoding="utf-8-sig",newline="") as f:
            again=tuple(tuple(row) for row in csv.reader(f,delimiter=";"))
        if rows!=again:
            raise ValueError("PageStatus export roundtrip mismatch")
        check=source_status_projection(mode,flow)
        if (proj.source_digest!=check.source_digest or
                proj.tick_index!=check.tick_index or
                proj.model.rows!=check.model.rows or
                proj.model.headers!=check.model.headers):
            raise ValueError("PageStatus source changed during export")
        return {
            **proj.receipt(),
            "saved_rows":len(rows)-1,
            "saved_columns":len(rows[0]),
            "sha256":sha256(path.read_bytes()).hexdigest(),
            "all_written_rows_reopened_and_verified":True,
            "device_io_performed":False,
            "source_files_modified":False,
            "original_win32_csv_format_claimed":False,
        }
    except Exception:
        if created:path.unlink(missing_ok=True)
        raise


assert len(MODE_GRID)==15
assert ORIGINAL_STATUS_TABS_RUNTIME==15
assert len(SOURCE_FREQUENCIES)==43
