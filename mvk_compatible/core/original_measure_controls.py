"""Stage111Z31BS — original global pnMeasure semantic contract + real local table.

Private source _Unit128.pas:
  0084DEA4 bFreezeUpdateClick toggles TMVKThread.FreezeUpdate [+0x400CD]
  0084DEC4 mRate1Click sets SelectedSampleRate and TMVKThread.SetRate
  0084E020 bWriteTableClick writes TABLE-yyyy-mm-dd--hh-nn-ss.csv
  0084E914 bWriteAdcClick toggles TMVKThread.WriteData [+0x400CE]
  0084E988 bWriteValuesClick toggles TMVKThread.WriteValues [+0x400CF]
  00845800 constructs FIVE sample-rate items from private pointer gvar_008D2F7C.

This autonomous module NEVER pretends to own original TMVKThread, send a
sample-rate command, or toggle Native R6.1 recorder file flags. Freeze is
explicitly a presentation-only freeze of PROVISIONAL Native live windows;
the read-only recorder continues and invalid windows are always cleared.

Local table export uses real, immutable, SHA-validated Native R6.1 VALUES
for eight ADCs, not recomputed FFT or fabricated TACH/Alarm readings.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from hashlib import sha256
import math
from pathlib import Path

from .offline_measurement_flow import OfflineMeasurementFlow
from .native_r6_live_preview import LivePreview
from .original_pagefile_recording import (
    OriginalPageFileSelection,ADC_VALUE_COUNT,BAND_VALUE_COUNT,SPEC_COUNT,
)

SOURCE="ORIGINAL_PNMEASURECONTROLS_FUNCTIONAL_STAGE111Z31BS"
DFM_PANEL=(6,6,843,41)
DFM_BUTTONS=(
    ("bFreezeUpdate",6,0,160,41,0,0),
    ("bSampleRate",172,0,160,41,0,1),
    ("bWriteTable",338,0,160,41,0,2),
    ("bWriteAdc",504,0,160,41,3,3),
    ("bWriteValues",670,0,160,41,8,4),
)
DFM_MEASURE_HEIGHT=53
DFM_VISIBLE_AT_DESIGN=False
ORIGINAL_RATE_RADIO_ITEMS=5
TABLE_PREFIX="TABLE-"
MAX_CSV_ROWS=8*(ADC_VALUE_COUNT+2*BAND_VALUE_COUNT)
MAX_CSV_BYTES=2_000_000


@dataclass(frozen=True)
class OriginalMeasureState:
    """Independent UI state; NEVER a hardware command handle.

    Original source flags are distinct, and Native R6.1 has its own
    authorized operator-only start/stop. This model cannot change those.
    """
    mode:str="idle"
    frozen:bool=False
    preview_session_id:str|None=None
    observed_sample_rate_hz:int|None=None
    observed_rates_per_adc:tuple[tuple[int,int],...]=()

    def __post_init__(self):
        if self.mode not in ("idle","offline","live"):
            raise ValueError("Unknown original measure view mode")
        if type(self.frozen) is not bool:
            raise ValueError("Freeze flag must be Boolean")
        if self.frozen and self.mode!="live":
            raise ValueError("Only provisional live preview can be frozen")
        if self.observed_sample_rate_hz is not None and (
                type(self.observed_sample_rate_hz) is not int or
                not 1<=self.observed_sample_rate_hz<=1_000_000):
            raise ValueError("Observed sample rate must be a real Hz integer")

    def open_offline(self,flow:OfflineMeasurementFlow):
        if self.mode=="live":
            raise ValueError("Cannot attach an offline file while recorder active")
        record=flow.source_record()
        rate=record["sample_rate_hz"]
        if not isinstance(rate,(float,int)) or not math.isfinite(rate) or rate<=0:
            raise ValueError("No verified sample frequency")
        display=int(rate) if int(rate)==rate else None
        return OriginalMeasureState(mode="offline",
                                    observed_sample_rate_hz=display)

    def begin_live(self):
        if self.mode=="live":
            raise ValueError("Native recorder already active")
        return OriginalMeasureState(mode="live")

    def accept_preview(self,preview:LivePreview):
        if self.mode!="live" or not isinstance(preview,LivePreview):
            raise ValueError("No trustworthy Native live preview")
        if (self.preview_session_id is not None and
                preview.session_id!=self.preview_session_id):
            raise ValueError("Native preview belongs to another capture session")
        rates=[]
        for adc,ch in sorted(preview.channels.items()):
            if (type(adc) is not int or not 1<=adc<=8 or
                    type(ch.rate_hz) is not int or
                    not 1<=ch.rate_hz<=1_000_000 or
                    ch.number!=adc):
                raise ValueError("Unverified source channel sample rate")
            rates.append((adc,ch.rate_hz))
        observed=rates[0][1] if rates and len({x[1] for x in rates})==1 else None
        return replace(self,preview_session_id=preview.session_id,
                       observed_sample_rate_hz=observed,
                       observed_rates_per_adc=tuple(rates))

    def toggle_freeze(self):
        if self.mode!="live":
            raise ValueError("Original FreezeUpdate requires an active capture")
        return replace(self,frozen=not self.frozen)

    def invalidate_preview(self):
        if self.mode!="live":
            return self
        return replace(self,observed_sample_rate_hz=None,
                       observed_rates_per_adc=())

    def finish(self):
        return OriginalMeasureState()

    def report(self):
        return {
            "source":SOURCE,
            "mode":self.mode,
            "presentation_frozen":self.frozen,
            "observed_sample_rate_hz":self.observed_sample_rate_hz,
            "observed_rates_per_adc":list(self.observed_rates_per_adc),
            "original_sample_rate_menu_entries":ORIGINAL_RATE_RADIO_ITEMS,
            "original_sample_rate_menu_values_verified":False,
            "original_thread_freeze_flag_set":False,
            "original_thread_write_adc_flag_set":False,
            "original_thread_write_values_flag_set":False,
            "native_recorder_filter_or_sample_rate_changed":False,
            "device_commands_sent":False,
            "physical_calibration_verified":False,
        }


def _verified_value(raw):
    if (type(raw) not in (float,int) or
            not math.isfinite(raw)):
        raise ValueError("Original table contains absent/non-finite measurement")
    return f"{raw:.9g}"


def _safe_label(label):
    if not isinstance(label,str) or not label:
        raise ValueError("Missing source field label")
    # Prevent Excel/LibreOffice formula execution in an otherwise valid CSV.
    return "'"+label if label[0] in "=+-@\t\r\n" else label


def table_rows(flow:OfflineMeasurementFlow,
               selection:OriginalPageFileSelection|None=None):
    """Source-authenticated current tick; no FFT or device source invention.

    Without selection, original Table action exports 24+43 per ADC.
    With PageFile selection, explicit measured VALUE / BAND / SPEC flags
    apply to actual proven numbers; TACH is never emitted without evidence.
    """
    if not isinstance(flow,OfflineMeasurementFlow) or flow.direct_bin:
        raise ValueError("A verified Native R6.1 ZIP with VALUES is required")
    flow.source_record()
    data=flow.status_snapshot()
    if data is None or data.get("source")!="MVK_DSP":
        raise ValueError("No verified original DSP VALUES snapshot")
    if selection is not None:
        selection.validate(flow)
        selected=[i+1 for i in selection.checked("channels") if i<8]
    else:
        selected=list(range(1,9))
    if not selected:
        raise ValueError("No checked ADC channel with valid measurements")
    rows=[]
    for adc in selected:
        # SHA revalidate actual source BIN in each chosen ADC.
        flow.select(channel=adc).source_record()
        bank=data["channels"][adc-1]
        if bank.get("channel")!=adc:
            raise ValueError("The original ADC DSP bank differs from selection")
        params=bank.get("parameters_24")
        bands=bank.get("third_octave")
        if (not isinstance(params,list) or len(params)!=ADC_VALUE_COUNT
                or not isinstance(bands,list) or len(bands)!=BAND_VALUE_COUNT):
            raise ValueError("Original VALUES/SPEC bank count mismatch")
        for i,record in enumerate(params):
            if selection is None or selection.values[i]:
                rows.append((adc,"VALUE",i+1,_safe_label(record["name"]),
                             _verified_value(record["value"]),
                             _safe_label(record.get("unit") or "—")))
        for i,record in enumerate(bands):
            if selection is None or selection.values[ADC_VALUE_COUNT+i]:
                rows.append((adc,"BAND",i+1,_safe_label(record["name"]),
                             _verified_value(record["rms_m_s2"]),"м/с²"))
            if selection is not None and selection.spec[i]:
                rows.append((adc,"SPEC",i+1,_safe_label(record["name"]),
                             _verified_value(record["rms_m_s2"]),"м/с²"))
    if not rows or len(rows)>MAX_CSV_ROWS:
        raise ValueError("Original selected table is empty or oversized")
    return tuple(rows)


def export_verified_table_csv(flow:OfflineMeasurementFlow,filename:str|Path,
                              *,selection:OriginalPageFileSelection|None=None):
    """Real local TABLE CSV; no original vendor thread, no overwrite.

    Not original Win32 bytes/locale; our CSV uses UTF-8-SIG and semicolon,
    and the original TABLE- date filename is only a suggested name.
    """
    records=table_rows(flow,selection)
    target=Path(filename).absolute()
    if (target.suffix.lower()!=".csv" or
            target.is_symlink() or target.exists() or
            not target.parent.is_dir() or target.parent.is_symlink()):
        raise ValueError("Choose a NEW regular local CSV file, not a source path")
    if (flow.direct_bin or
            target==getattr(flow.session,"path",None)):
        raise ValueError("Original source cannot be overwritten")
    created=False
    header=("ADC","Группа","Исходный индекс","Показатель","Значение","Ед.")
    try:
        with target.open("x",newline="",encoding="utf-8-sig") as stream:
            created=True
            writer=csv.writer(stream,delimiter=";")
            writer.writerow(header)
            writer.writerows(records)
        if target.stat().st_size>MAX_CSV_BYTES:
            raise ValueError("Original TABLE export exceeds file size limit")
        with target.open(newline="",encoding="utf-8-sig") as stream:
            readback=list(csv.reader(stream,delimiter=";"))
        if readback[0]!=list(header) or tuple(map(tuple,readback[1:]))!=tuple(
                tuple(str(x) for x in row) for row in records):
            raise ValueError("TABLE CSV failed independent file readback")
        # Fail-closed if input source was modified after the export.
        for adc in sorted({int(x[0]) for x in records}):
            flow.select(channel=adc).source_record()
        return {
            "source":SOURCE,
            "source_kind":"CHECKED_NATIVE_R6_OFFLINE_DSP",
            "table_saved":True,
            "rows":len(records),
            "channels":sorted({int(x[0]) for x in records}),
            "selected_result_flags_used":selection is not None,
            "checksum_sha256":sha256(target.read_bytes()).hexdigest(),
            "all_written_rows_reopened_and_verified":True,
            "original_delphi_table_binary_parity_verified":False,
            "original_tmkvthread_write_table_executed":False,
            "device_io_executed":False,
            "original_capture_or_source_modified":False,
            "user_file_path_in_report":False,
        }
    except Exception:
        if created:
            target.unlink(missing_ok=True)
        raise
