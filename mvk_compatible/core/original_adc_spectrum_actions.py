"""Stage111Z31BV: original PageAdc cursor + PageSpectrum Copy/Save actions.

Source: operator-owned Projects/_Unit128.pas and mvkform.dfm.

- 0084B4AC pbAdcMouseMove: ADCGrapher.UpdateCursor(pointer X);
- 0084C918 pbSpectrumMouseMove: SpecGrapher.UpdateCursor(pointer X);
- 0084BC28 bSpecCopyValue: 3 tab-separated numbers from the SELECTED
  channel's OutputMean(+0x30), OutputPeakX(+0x34)*Series.XScale,
  OutputPeakY(+0x38), not an arbitrary chart pixel;
- 0084BD7C bSpecSaveValue: append one 3-value pipe-delimited row to
  SPEC-FREQ-yyyy-mm-dd.csv under edLibraryPath; first write starts
  with sep=| and source-localized labels. This exporter targets the
  original Russian Windows ANSI profile. Numeric RTL parity is separate.

The uploaded Delphi sources and user data remain private. This module
never touches a device or the original config. Only files with the same
header, units and numeric format can be appended to.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import math
from pathlib import Path
import re
import struct

import numpy as np

from .offline_measurement_flow import OfflineMeasurementFlow
from .spectrum_summary_export_candidate import spectrum_triplet_text
from .storage_f_range_idr_candidate import DOMAIN_ORIGINAL_STORAGE
from .direct_bin_session import TACH_INPUT_DOMAIN
from .mvk_original_scale_tables_idr_candidate import source_derived_units

SOURCE="ORIGINAL_IDR_ADC_SPEC_ACTIONS_STAGE111Z31BV"
SPECTRUM_COPY_SOURCE="PRIVATE_UNIT128_0084BC28"
SPECTRUM_SAVE_SOURCE="PRIVATE_UNIT128_0084BD7C"
WAVE_CURSOR_SOURCE="PRIVATE_UNIT128_0084B4AC"
SPEC_CSV_ENCODING="cp1251"


def spectrum_source_ru_header(mode:int, source_units:str="м/с2")->str:
    """Russian bSpecSaveValue header for the selected source channel.

    Format is lbSpecMeanX, Units | xFrequency, XName | xParamValue, Units.
    Russian resource keys and XName are from MVKView 1.0.47. In log mode
    this is the original *summary* unit, not the chart's dB Y-axis.
    Native ZIP defaults to acceleration; saved archives use actual FUnits.
    """
    unit=source_derived_units(mode,source_units)
    if unit is None or "|" in unit or any(not c.isprintable() for c in unit):
        raise ValueError("Некорректные единицы оригинального SPEC-FREQ")
    return f"СКЗ спектра, {unit}|Частота, Гц|Значение, {unit}"


SPEC_CSV_HEADER=spectrum_source_ru_header(0)
SPEC_CSV_PREFIX="SPEC-FREQ-"
MAX_SPEC_CSV_BYTES=2_000_000
MAX_ENVELOPE_SAMPLES=2_000_000
_ASCII_DATE=re.compile(r"^SPEC-FREQ-\d{4}-\d{2}-\d{2}\.csv$")


def _finite(name,value):
    if isinstance(value,(bool,str,bytes)):
        raise ValueError(f"{name}: finite numerical source required")
    try:
        result=float(value)
    except (TypeError,ValueError) as exc:
        raise ValueError(f"{name}: finite numerical source required") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name}: finite numerical source required")
    return result


def _source_summary(flow,spectrum):
    if not isinstance(flow,OfflineMeasurementFlow) or not isinstance(spectrum,dict):
        raise ValueError("The current real Core spectrum and session are required")
    source=flow.source_record()  # verifies source archive, ADC and SHA
    adc=flow.channel
    if spectrum.get("channel")!=adc:
        raise ValueError("PageSpectrum ADC does not match current source channel")
    n=spectrum.get("n_fft")
    # The original selected bSpecLines sample count is BEFORE decimation.
    # Tiny post-FIR FFT is allowed only on the explicitly validated source route.
    pre=spectrum.get("source_bspec_lines_before_fir")
    source_fir=(spectrum.get("source_bspec_lines_interpretation")=="ORIGINAL_SELECTED_PRE_FIR"
                and type(pre) is int and 1024<=pre<=262144 and not pre&(pre-1)
                and type(n) is int and n<=pre)
    if type(n) is not int or not (8 if source_fir else 1024)<=n<=262144 or n&(n-1):
        raise ValueError("Original spectrum must have power-of-two FFT size")
    ys=spectrum.get("amplitude")
    xs=spectrum.get("frequency_hz")
    if ys is None or xs is None or len(ys)!=n//2 or len(xs)!=n//2:
        raise ValueError("Current FFT must preserve all N/2 bins")
    mode=spectrum.get("mode")
    summary=spectrum.get("spectrum_summary")
    if (type(mode) is not int or mode not in range(4)
        or not isinstance(summary,dict) or
        summary.get("source")!="APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE"
        or summary.get("spectrum_mode")!=mode or summary.get("n_fft")!=n):
        raise ValueError("No source-derived selected mode GetSpectrum triplet")
    df=_finite("FFT df",spectrum.get("df_hz"))
    if df<=0:
        raise ValueError("No original XScale from current FFT")
    frequency=_finite("peak Hz",summary.get("output_peak_frequency_hz"))
    bin_index=_finite("peak bin",summary.get("output_peak_x_bin"))
    if not (0<=frequency<=df*(n//2) and 0<=bin_index<n//2):
        raise ValueError("Peak lies outside current FFT output")
    # Source [_Unit128:0084BCAD] multiplies OutputPeakX by
    # TQGRSeries.XScale (df). The pure summary already rounded to f32.
    x87_candidate=float(np.float32(np.float32(bin_index)*np.float32(df)))
    if not math.isclose(frequency,x87_candidate,rel_tol=1e-5,abs_tol=2e-5):
        raise ValueError("Exported frequency not linked to displayed NFFT/df")
    peak_y=_finite("peak Y",summary.get("output_peak_y"))
    mean=_finite("mean",summary.get("output_mean"))
    if mode!=0 and (peak_y<0 or mean<0):
        raise ValueError("Negative linear GetSpectrum summary")
    # No fabricated physical calibration; native verified record !=
    # an original Win32 same-session/x87 numerical attestation.
    return source,n,mode,(mean,frequency,peak_y),summary


@dataclass(frozen=True)
class OriginalSpectrumAction:
    source_bin_sha256:str
    adc:int
    n_fft:int
    spectrum_mode:int
    current_dsp_tick_index:int|None
    values:tuple[float,float,float]
    direct_bin_uncalibrated:bool
    source:str=SOURCE
    source_tsxml_sha256:str|None=None
    source_units:str="м/с2"
    original_saved_archive_metadata:bool=False
    window_signature:tuple|None=None

    @classmethod
    def from_view(cls,flow:OfflineMeasurementFlow,spectrum:dict):
        if isinstance(spectrum,dict) and spectrum.get("preview_left_padding_samples"):
            raise ValueError("Дополненный спектр доступен только для просмотра")
        record,n,mode,values,_=_source_summary(flow,spectrum)
        window=spectrum.get("input_source_window")
        signature=(tuple(window.get(k) for k in (
            "first_archive_sample_index","last_archive_sample_exclusive",
            "source_float32_le_sha256","sample_rate_hz"))
            if isinstance(window,dict) else None)
        units="м/с2"
        saved=False
        if flow.direct_bin:
            entry=flow.session.mode1_export_source(flow.channel)
            if entry is not None:
                meta=entry.source_metadata
                indicated=meta.channel_units_text
                channel_units=("" if indicated=="Count" else
                               "м/с2" if indicated=="1" else indicated)
                if (signature is not None and window.get("channel")==flow.channel
                        and window.get("no_zero_padding") is True
                        and type(signature[0]) is int and type(signature[1]) is int
                        and 0<=signature[0]<signature[1]<=record["sample_count"]
                        and window.get("source_sample_count")==signature[1]-signature[0]
                        and isinstance(signature[2],str)
                        and re.fullmatch(r"[a-f0-9]{64}",signature[2])
                        and signature[3]==float(meta.sample_rate_hz)
                        and spectrum.get("f_range_used")==meta.original_f_range_single_candidate
                        and spectrum.get("input_domain")==(
                            TACH_INPUT_DOMAIN if entry.tach_byte else DOMAIN_ORIGINAL_STORAGE)
                        and (not entry.tach_byte or (
                            window.get("source_tach_normalized_byte_window") is True
                            and spectrum.get("source_tach_byte_normalization_divisor")==255))):
                    try:
                        spectrum_source_ru_header(
                            mode,channel_units).encode(SPEC_CSV_ENCODING)
                    except (UnicodeError,ValueError):
                        pass  # remain clearly labelled local research
                    else:
                        units=channel_units
                        saved=True
        return cls(
            source_bin_sha256=record["source_bin_sha256"],
            adc=flow.channel,n_fft=n,spectrum_mode=mode,
            current_dsp_tick_index=None if flow.direct_bin else flow.tick_index,
            values=values,direct_bin_uncalibrated=flow.direct_bin and not saved,
            source_tsxml_sha256=record["source_tsxml_sha256"],source_units=units,
            original_saved_archive_metadata=saved,window_signature=signature)

    def validate_flow(self,flow:OfflineMeasurementFlow,spectrum:dict|None=None):
        if not isinstance(flow,OfflineMeasurementFlow):
            raise ValueError("No verified PageSpectrum session")
        record=flow.source_record()
        if (record["source_bin_sha256"]!=self.source_bin_sha256 or
                flow.channel!=self.adc or
                (None if flow.direct_bin else flow.tick_index)!=self.current_dsp_tick_index
                or record["source_tsxml_sha256"]!=self.source_tsxml_sha256
                or flow.direct_bin!=(self.source_tsxml_sha256 is not None)):
            raise ValueError("Spectrum Copy/Save state is stale or from another ADC/tick")
        if spectrum is not None:
            other=OriginalSpectrumAction.from_view(flow,spectrum)
            if other!=self:
                raise ValueError("Current rendered GetSpectrum was replaced")
        return True

    def clipboard_text(self,*,decimal_separator=","):
        """Original 0084BC28 tab triplet; mark unsupported local BIN sources."""
        if decimal_separator not in (",","."):
            raise ValueError("Numeric locale must be explicitly selected")
        # Reuse one existing source-formatter with original digit positions
        # 3,4,4; FloatToStr RTL byte parity remains open.
        summary={
            "source":"APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE",
            "output_mean":self.values[0],
            "output_peak_frequency_hz":self.values[1],
            "output_peak_y":self.values[2],
        }
        triple=spectrum_triplet_text(
            summary,separator="\t",decimal_separator=decimal_separator)
        if self.direct_bin_uncalibrated:
            return "НЕ КАЛИБРОВАНО · условные единицы · локальные значения FFT, не приборный DSP\n"+triple
        return triple

    def pipe_row(self,*,decimal_separator=","):
        summary={
            "source":"APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE",
            "output_mean":self.values[0],
            "output_peak_frequency_hz":self.values[1],
            "output_peak_y":self.values[2],
        }
        return spectrum_triplet_text(
            summary,separator="|",decimal_separator=decimal_separator)

    def receipt(self):
        return {
            "source":SOURCE,
            "original_selected_spectrum_adc":self.adc,
            "source_bin_sha256":self.source_bin_sha256,
            "selected_n_fft":self.n_fft,
            "selected_spectrum_mode":self.spectrum_mode,
            "source_tick_index":self.current_dsp_tick_index,
            "original_triplet_columns":3,
            "uncalibrated_direct_bin":self.direct_bin_uncalibrated,
            "source_tsxml_sha256":self.source_tsxml_sha256,
            "source_units":self.source_units,
            "original_saved_archive_metadata":self.original_saved_archive_metadata,
            "original_clipboard_handler":SPECTRUM_COPY_SOURCE,
            "original_csv_handler":SPECTRUM_SAVE_SOURCE,
            "actual_source_fft_used":True,
            "original_delphi_float_format_parity_verified":False,
            "physical_calibration_verified":False,
            "hardware_commands_sent":False,
        }


def spectrum_source_daily_path(directory,day:date):
    """Recovered filename prefix/daily append, not original codepage bytes."""
    if not isinstance(day,date):
        raise ValueError("A real calendar date is needed")
    folder=Path(directory).absolute()
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Source edLibraryPath must be an existing folder")
    return folder/(SPEC_CSV_PREFIX+day.strftime("%Y-%m-%d")+".csv")


def append_source_spec_freq_csv(action:OriginalSpectrumAction,
                                flow:OfflineMeasurementFlow,
                                destination,*,spectrum:dict|None=None,
                                decimal_separator=","):
    """Mirror 0084BD7C with Russian ANSI, exact units, and validated append.

    Every write revalidates the source and checks the full output.
    Native ZIP keeps its strict header check. A saved original archive
    with Count metadata can retain its recognizable first daily header.
    Never append a physical unit under a different physical-unit header.
    A foreign header or mixed numeric locale is refused. A failed append is rolled
    back to the original verified byte length.
    """
    if not isinstance(action,OriginalSpectrumAction):
        raise ValueError("No original GetSpectrum selection")
    action.validate_flow(flow,spectrum)
    dest=Path(destination).absolute()
    if (dest.suffix.lower()!=".csv" or not _ASCII_DATE.fullmatch(dest.name)
        or not dest.parent.is_dir() or dest.parent.is_symlink()
        or dest.is_symlink()):
        raise ValueError("Source SPEC-FREQ-YYYY-MM-DD.csv in local folder required")
    if action.direct_bin_uncalibrated:
        # The three numeric values are still real local FFT, but a
        # source-looking SPEC-FREQ file would falsely assert original
        # sensor calibration. Keep the existing clearly labelled
        # research export for BIN-only sources.
        raise ValueError("Direct BIN calibration not verified: original SPEC-FREQ export blocked")
    if decimal_separator not in (",","."):
        raise ValueError("Numeric locale must be explicitly selected")
    row=action.pipe_row(decimal_separator=decimal_separator)
    if len(row.split("|"))!=3 or "\r" in row or "\n" in row:
        raise ValueError("Original source triplet must be exactly three safe numbers")
    header=("sep=|\r\n"+spectrum_source_ru_header(action.spectrum_mode, action.source_units)
            +"\r\n").encode(SPEC_CSV_ENCODING)
    before=b""
    retained_first_header=False
    if dest.exists():
        if (not dest.is_file() or
                dest.stat().st_size>MAX_SPEC_CSV_BYTES):
            raise ValueError("Source SPEC-FREQ file invalid or oversized")
        before=dest.read_bytes()
        old_header=header
        if not before.startswith(header):
            # Count/Byte has no attested physical units. The original writes a
            # daily header once, then only numeric rows
            # even after a change of mode/channel/unit. In saved Mode1 reproduce
            # this for recognizable original headers; never rewrite old bytes.
            fields=before.split(b"\r\n",2)
            if not action.original_saved_archive_metadata or len(fields)!=3 or fields[0]!=b"sep=|":
                raise ValueError("Existing vendor/unverified SPEC-FREQ: different header, encoding or units")
            try:
                old_text=fields[1].decode(SPEC_CSV_ENCODING)
                m=re.fullmatch(r"СКЗ спектра, ([^|]{0,66})\|Частота, Гц\|Значение, \1",old_text)
                if not m or spectrum_source_ru_header(0,m[1])!=old_text:
                    raise ValueError("Unrecognized Russian header")
            except (UnicodeError,ValueError) as exc:
                raise ValueError("Existing vendor/unverified SPEC-FREQ: different header, encoding or units") from exc
            if action.source_units:
                raise ValueError(
                    'Заголовок дневного SPEC-FREQ не совпадает с единицами текущего спектра. '
                    'Выберите отдельную папку для этого режима. Старый файл не изменён.')
            old_header=b"sep=|\r\n"+fields[1]+b"\r\n"
            retained_first_header=True
        tail=before[len(old_header):]
        if tail and not tail.endswith(b"\r\n"):
            raise ValueError("Existing candidate SPEC-FREQ rows malformed")
        number=rb"[+-]?(?:[0-9]+(?:"+re.escape(decimal_separator.encode("ascii"))+rb"[0-9]*)?)(?:[eE][+-]?[0-9]+)?"
        numeric_row=re.compile(rb"\|".join((number,)*3))
        rows=tail[:-2].split(b"\r\n") if tail else []
        if any((b"." if decimal_separator=="," else b",") in old for old in rows):
            raise ValueError("Existing SPEC-FREQ has a different decimal separator")
        if not all(numeric_row.fullmatch(old) for old in rows):
            raise ValueError("Existing candidate SPEC-FREQ rows malformed")
    payload=(row+"\r\n").encode("ascii")
    output=(before or header)+payload
    if len(output)>MAX_SPEC_CSV_BYTES:
        raise ValueError("Source SPEC-FREQ CSV exceeds safe size")
    created=False
    try:
        if before:
            with dest.open("ab") as handle:
                handle.write(payload)
        else:
            with dest.open("xb") as handle:
                created=True
                handle.write(output)
        on_disk=dest.read_bytes()
        if on_disk!=output:
            raise ValueError("Source SPEC-FREQ independent readback failed")
        action.validate_flow(flow,spectrum)
        return {
            **action.receipt(),
            "local_source_grammar":"sep=| + 3-column header + pipe rows + CRLF",
            "current_saved_row":row,
            "appended_existing_candidate":bool(before),
            "retained_first_header_after_unit_change":retained_first_header,
            "full_csv_sha256":sha256(on_disk).hexdigest(),
            "independent_roundtrip_verified":True,
            "source_file_untouched":True,
            "source_csv_encoding":SPEC_CSV_ENCODING,
            "source_csv_ru_header_from_executable":True,
            "original_csv_full_file_numeric_parity_verified":False,
            "hardware_commands_sent":False,
        }
    except Exception:
        if created:
            dest.unlink(missing_ok=True)
        elif before:
            with dest.open("wb") as handle:handle.write(before)
        raise


@dataclass(frozen=True)
class OriginalEnvelopeCursor:
    """Source UI cursor reads complete processed float32 envelope, not plot LOD."""
    channel:int
    source_bin_sha256:str
    output_hz:float
    code:int
    output_order:str
    array_sha256:str
    full_values:np.ndarray
    provenance:str=WAVE_CURSOR_SOURCE
    original_delphi_cursor_pixel_parity_verified:bool=False
    original_absolute_envelope_time_verified:bool=False

    @classmethod
    def from_trace(cls,flow:OfflineMeasurementFlow,trace:dict):
        if not isinstance(flow,OfflineMeasurementFlow) or not isinstance(trace,dict):
            raise ValueError("Verified source envelope trace required")
        record=flow.source_record()
        if trace.get("channel")!=flow.channel or trace.get("code") not in range(1,32):
            raise ValueError("Envelope trace channel/code from a different view")
        hz=_finite("FIR output rate",trace.get("output_sample_rate_hz"))
        if hz<=0 or hz>record["sample_rate_hz"]:
            raise ValueError("Invalid actual FIR output Fs")
        source=trace.get("cursor_full_samples_float32")
        a=np.asarray(source)
        if (a.ndim!=1 or a.dtype!=np.dtype("float32")
            or not 1<=len(a)<=MAX_ENVELOPE_SAMPLES
            or trace.get("output_samples")!=len(a)
            or not np.isfinite(a).all()):
            raise ValueError("Exact full FIR output is unavailable for source cursor")
        ordered=trace.get("display_order")
        if ordered not in ("chronological","getsignal_buffer"):
            raise ValueError("Unknown original GetSignal display buffer order")
        expected=trace.get("cursor_full_samples_sha256")
        digest=sha256(np.asarray(a,dtype="<f4").tobytes()).hexdigest()
        if digest!=expected:
            raise ValueError("FIR cursor source data SHA mismatch")
        span=trace.get("input_source_window")
        if (not isinstance(span,dict) or span.get("channel")!=flow.channel):
            raise ValueError("Envelope input window not linked to selected ADC")
        return cls(
            channel=flow.channel,source_bin_sha256=record["source_bin_sha256"],
            output_hz=hz,code=trace["code"],output_order=ordered,
            array_sha256=digest,full_values=a.copy())

    def pick(self,x_buffer_seconds):
        x=_finite("Envelope relative buffer position",x_buffer_seconds)
        if x<0 or x>(len(self.full_values)-1)/self.output_hz:
            raise ValueError("Envelope cursor outside displayed output buffer")
        index=min(len(self.full_values)-1,max(0,int(math.floor(x*self.output_hz+0.5))))
        value=float(self.full_values[index])
        return {
            "source":WAVE_CURSOR_SOURCE,
            "adc":self.channel,"code":self.code,
            "output_index":index,
            "output_buffer_relative_s":index/self.output_hz,
            "value_from_full_filtered_float32":value,
            "order":self.output_order,
            "input_bin_sha256":self.source_bin_sha256,
            "filtered_output_sha256":self.array_sha256,
            "original_absolute_envelope_time_verified":False,
            "original_pixel_geometry_verified":False,
            "physical_calibration_verified":False,
        }
