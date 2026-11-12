"""Stage111Z31BL: one source-backed spectrum FRange + X viewport contract.

This module binds the already verified Single BIN source, source-authored
TSXML gain (if supplied) and SAME full GetSpectrum result to the original
10-entry Hz menu.  It does NOT write hardware, change the FFT, infer sensor
physical calibration or claim same-call Delphi Win32/x87 pixel parity.

Evidence:
  _Unit128 0084C3AC..C4BB: TScrollBar/H page / native integer position;
  _Unit128 0084B5D3..B882: FRange -> GraphDefaultVScale candidate;
  _Unit128 0084655B..5E: TSXML gain -> channel FRange assignment;
  Original _Unit115: source TQGRSeries uses 1/1.28 of N/2 bins.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .direct_bin_session import DirectBinSession
from .offline_measurement_flow import OfflineMeasurementFlow
from .mvk_original_scale_tables_idr_candidate import (
    HORIZONTAL_HZ,validate_source_h_scale,
)
from .spectrum_graph_default_vscale_idr_candidate import (
    spectrum_graph_default_vscale,
)
from .tqgrapher_spectrum_scroll_idr_candidate import NativeScrollContract
from .tqgrapher_display_idr_candidate import spectrum_display_contract

SOURCE = "MVK_ORIGINAL_LINKED_SPECTRUM_VIEW_STAGE111Z31BL"
SOURCE_GAIN = "TSXML_CHANNEL_GAIN_STATIC_LOADER_CANDIDATE"
SOURCE_MISSING = "NO_VERIFIED_CHANNEL_FRANGE"
ORIGINAL_FULL_HZ = HORIZONTAL_HZ[0]


@dataclass(frozen=True)
class SourceSpectrumGain:
    channel: int
    source_bin_sha256: str
    frange_single: float | None
    origin: str
    graph_default_vscale_candidate: float | None
    original_loader_branch: str | None
    spectrum_mode: int
    source_bin_physical_calibration_verified: bool = False
    original_runtime_frange_verified: bool = False
    delphi_x87_scale_parity_verified: bool = False

    @property
    def label(self) -> str:
        if self.frange_single is None:
            return "FRange: не установлен для текущего АЦП"
        return (f"FRange TSXML {self.frange_single:.8g}"
                " · кандидат загрузчика, не калибровка")

    def provenance(self) -> dict:
        return {
            "source": SOURCE,
            "adc": self.channel,
            "source_bin_sha256": self.source_bin_sha256,
            "original_frange_source": self.origin,
            "frange_single": self.frange_single,
            "original_loader_branch": self.original_loader_branch,
            "graph_default_vscale_candidate": self.graph_default_vscale_candidate,
            "original_runtime_frange_verified": False,
            "delphi_x87_scale_parity_verified": False,
            "physical_calibration_verified": False,
            "fft_scaled_by_this_view": False,
        }


@dataclass(frozen=True)
class SourceSpectrumHView:
    channel: int
    source_bin_sha256: str
    n_fft: int
    fft_bins: int
    source_series_bins: int
    source_axis_end_hz: float
    original_full_hz: int
    selected_page_hz: int
    native_position_hz: int
    native_qt_maximum: int
    fft_values_changed: bool = False
    original_runtime_canvas_verified: bool = False

    @property
    def x_bounds(self) -> tuple[float,float]:
        p = self.native_position_hz
        return float(p),float(p+self.selected_page_hz)

    def provenance(self) -> dict:
        return {
            "source": SOURCE,
            "adc": self.channel,
            "source_bin_sha256": self.source_bin_sha256,
            "selected_hz": self.selected_page_hz,
            "native_position_hz": self.native_position_hz,
            "original_full_hz": self.original_full_hz,
            "qt_scroll_maximum": self.native_qt_maximum,
            "original_runtime_canvas_verified": False,
            "fft_values_changed": False,
        }


def _checked_spectrum(flow: OfflineMeasurementFlow,spectrum: dict) -> tuple[dict,int,float,dict]:
    if not isinstance(flow,OfflineMeasurementFlow):
        raise ValueError("One verified offline measurement is required")
    record=flow.source_record()  # rechecks source ADC, SHA and real bytes
    if not isinstance(spectrum,dict) or spectrum.get("channel")!=flow.channel:
        raise ValueError("Spectrum ADC does not match current source")
    n=spectrum.get("n_fft")
    if type(n) is not int or n<1024 or n>262144 or n & (n-1):
        raise ValueError("Original NFFT must be a bounded power of two")
    ys=spectrum.get("amplitude")
    xs=spectrum.get("frequency_hz")
    if (ys is None or xs is None or len(ys)!=n//2 or len(xs)!=n//2):
        raise ValueError("Source spectrum must preserve ALL N/2 FFT bins")
    df=float(spectrum.get("df_hz",float("nan")))
    fs=float(record["sample_rate_hz"])
    if not (math.isfinite(df) and df>0 and
            math.isclose(df,fs/n,rel_tol=2e-6,abs_tol=1e-8)):
        raise ValueError("FFT resolution differs from checked source Fs")
    contract=spectrum_display_contract(n,fs)
    if contract["grapher_series_bins"] > n//2:
        raise ValueError("TQGRSeries exceeds full FFT")
    return record,n,fs,contract


def source_spectrum_gain(
        flow:OfflineMeasurementFlow,spectrum:dict,*,mode:int) -> SourceSpectrumGain:
    """TSXML static gain belongs to THIS selected BIN ADC, never to ZIP/other ADC.

    Missing/zero/negative declared gain is NOT replaced by manual FRange=1;
    DefaultConfig.txt fallback is unknown. A positive TSXML value is valid
    source metadata yet original runtime FRange and unit calibration remain
    unknown. Even known source metadata never multiplies BIN or FFT here.
    """
    record,_,_,_=_checked_spectrum(flow,spectrum)
    if type(mode) is not int or mode not in range(4):
        raise ValueError("Original spectrum mode 0..3 required")
    if spectrum.get("mode")!=mode:
        raise ValueError("Spectrum mode does not match the selected graph")
    gain=None
    branch=None
    origin=SOURCE_MISSING
    if type(flow.session) is DirectBinSession:
        matches=[ch for ch in flow.session.channel_files
                 if ch.adc==flow.channel]
        if len(matches)!=1 or matches[0].bin_sha256!=record["source_bin_sha256"]:
            raise ValueError("TSXML gain from a different BIN/ADC")
        metadata=matches[0].source_metadata
        branch=metadata.gain_loader_branch
        raw=metadata.original_f_range_single_candidate
        if raw is not None:
            gain=float(raw)
            if not (math.isfinite(gain) and gain>0):
                raise ValueError("Nonpositive source TSXML FRange")
            if branch!="DECLARED_POSITIVE_NO_APPLY_RANGE_SOURCE_BRANCH":
                raise ValueError("Conflicting TSXML loader FRange branch")
            origin=SOURCE_GAIN
    graph=(None if gain is None else
           spectrum_graph_default_vscale(
               gain,mode)["candidate_graph_default_vscale_single"])
    return SourceSpectrumGain(
        channel=flow.channel,source_bin_sha256=record["source_bin_sha256"],
        frange_single=gain,origin=origin,
        graph_default_vscale_candidate=graph,
        original_loader_branch=branch,spectrum_mode=mode)


def source_spectrum_h_view(
        flow:OfflineMeasurementFlow,spectrum:dict,*,
        selected_hz:int,position_hz:int=0) -> SourceSpectrumHView:
    """Same full FFT + source-verified original 10-item integer H page.

    The source's 25600 Hz full range and preset come from recovered DWORDs.
    For a recording with lower Fs, the original menu may show an empty region;
    never fabricate bins past the actual grapher axis end.
    """
    record,n,_,contract=_checked_spectrum(flow,spectrum)
    hz=validate_source_h_scale(selected_hz)
    native=NativeScrollContract(
        "horizontal",ORIGINAL_FULL_HZ,hz,position_hz,
        source_menu_preset_verified=True)
    return SourceSpectrumHView(
        channel=flow.channel,
        source_bin_sha256=record["source_bin_sha256"],
        n_fft=n,fft_bins=n//2,
        source_series_bins=contract["grapher_series_bins"],
        source_axis_end_hz=contract["grapher_axis_end_frequency_hz"],
        original_full_hz=ORIGINAL_FULL_HZ,
        selected_page_hz=hz,
        native_position_hz=native.position,
        native_qt_maximum=native.view()["qt_maximum"],
    )
