"""Stage111Z.26B: provisional calibrated live windows from the SOLE Native R6.1.

The Qt side NEVER opens TCP, touches incomplete BIN, rescales FRange, or treats
these windows as a final audited original MVKView export. Accept only a small
atomic ZIP with fixed schema, per-channel SHA256, same session, and fresh status.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zipfile

import numpy as np

from .native_r6_live_status import _utc_stamp
from .original_source_ring_receipt import (SOURCE_LIVE_ADC_DOMAIN, SOURCE_LIVE_ADC_DOMAINS,
    source_live_units_text,TACH_DOMAIN)
from .storage_f_range_idr_candidate import DOMAIN_ORIGINAL_STORAGE
from .offline_export import waveform_for_zip, spectrum_for_zip, reduce_minmax
from .original_getsignal_live_source import (
    source_live_adc_menu_length,source_getsignal_readiness,
)
from .original_sample_cursor32 import (
    u32_preview_bounds,u32_matches_go_status,extended_u32_window,
)

NAME = "MVK_NATIVE_LIVE_PREVIEW.zip"
SCHEMA = "MVK_NATIVE_R6_CALIBRATED_PREVIEW_V1"
DOMAIN = "CALIBRATED_NATIVE_R6_BIN_SPOOL_FLOAT32"
# Source bSpecLines includes up to N=262144; the same sole Native Go
# receiver's calibrated Float32 sidecar is bounded to 8*262144*4=8 MiB.
# This is still PROVISIONAL and smaller than original TMvkChannelStorage.
MAX_SAMPLES = 262144
MAX_DISK_BYTES = 9_000_000
MAX_MANIFEST = 16_384
MAX_UNCOMPRESSED_BYTES = MAX_SAMPLES * 4 * 8 + MAX_MANIFEST
_HEX = re.compile(r"[a-f0-9]{64}\Z")
_ENTRY = re.compile(r"ADC([1-8])\.f32\Z")


def _uint(value, name: str, *, max_value: int = (1 << 32) - 1) -> int:
    if type(value) is not int or value < 0 or value > max_value:
        raise ValueError(f"Native live preview: invalid {name}")
    return value


@dataclass(frozen=True)
class PreviewADC:
    number: int
    rate_hz: int
    first_index: int
    next_index: int
    samples: np.ndarray
    sha256: str
    captured_samples: int | None = None
    source_f_range_single: float = 1.0
    source_range_state: dict | None = None
    source_epoch: dict | None = None


@dataclass(frozen=True)
class LivePreview:
    session_id: str
    updated_utc: datetime
    raw_bytes: int
    frames_decoded: int
    channels: dict[int, PreviewADC]
    input_domain: str = DOMAIN
    provisional: bool = True
    # Only the SHA/RAW/cursor-checked local Go ring IPC sets this flag.
    # Never infer source storage from the length of a Native preview.
    source_ring_provenance_verified: bool = False

    def samples_for_offline_candidate(self, channel: int):
        ch = self.channels.get(channel)
        if ch is None:
            raise ValueError(f"ADC{channel}: no real samples in provisional window")
        if self.input_domain==TACH_DOMAIN:
            if (channel not in (9,10) or not self.source_ring_provenance_verified or
                    ch.samples.dtype!=np.dtype("u1")):
                raise ValueError("TACH requires verified original Byte ring")
            # 007D2317..007D232D fild Byte; fdiv Single(255); fstp Single.
            normalized=(ch.samples.astype(np.float64)/255.0).astype("<f4")
            return normalized,float(ch.rate_hz),{"source_tach_byte_window":True},f"Source TACH{channel-8} Byte/255"
        # The original spool already scaled each float32; the offline
        # candidate MUST NOT multiply channel FRange a second time.
        return ch.samples, float(ch.rate_hz), {}, f"Native R6.1 LIVE ADC{channel}"


def _validate_preview_payload(archive: zipfile.ZipFile, status: dict,
                              now: datetime) -> LivePreview:
    files = archive.namelist()
    if len(files) != len(set(files)) or "MANIFEST.json" not in files or len(files) > 9:
        raise ValueError("Native live preview: invalid or duplicate members")
    meta_info = archive.getinfo("MANIFEST.json")
    if meta_info.file_size > MAX_MANIFEST:
        raise ValueError("Native live preview: oversized manifest")
    total = sum(f.file_size for f in archive.infolist())
    if total > MAX_UNCOMPRESSED_BYTES:
        raise ValueError("Native live preview: uncompressed data exceeds bounded ring")
    try:
        meta = json.loads(archive.read("MANIFEST.json"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Native live preview: invalid manifest JSON") from exc
    if not isinstance(meta, dict) or meta.get("schema") != SCHEMA:
        raise ValueError("Native live preview: unexpected schema")
    if (meta.get("session_id") != status["session_id"] or
            meta.get("phase") != "RECORDING" or
            meta.get("input_domain") != DOMAIN or
            meta.get("calibration_already_applied") is not True or
            meta.get("read_only_no_app_payload_sent") is not True or
            meta.get("provisional_not_audited") is not True):
        raise ValueError("Native live preview: wrong session or calibration domain")
    ts = _utc_stamp(meta.get("updated_utc"), "live preview updated_utc")
    age = (now - ts).total_seconds()
    if age < -4 or age > 5:
        raise ValueError("Native live preview: delayed, stale or future window")
    # The status and preview are replaced atomically but independently.
    # Older preview frames can be shown only if status is not older than them.
    st = _utc_stamp(status["updated_utc"], "live status updated_utc")
    if (ts-st).total_seconds() > 3 or (st-ts).total_seconds() > 5:
        raise ValueError("Native live preview: unrelated status/preview update")
    # Go Summary.RawBytes/TotalFrames are uint64; continuous source
    # recording must not stop preview at the old 4 GiB counter limit.
    raw = _uint(meta.get("raw_bytes"), "raw_bytes",max_value=(1<<64)-1)
    frames = _uint(meta.get("frames_decoded"), "frames_decoded",max_value=(1<<64)-1)
    if raw > status["raw_bytes"] or frames > status["frames_decoded"]:
        raise ValueError("Native live preview: preview newer than trusted status")
    records = meta.get("channels")
    if not isinstance(records, list) or not 0 < len(records) <= 8:
        raise ValueError("Native live preview: empty or oversized ADC list")
    actual_names = {f.filename for f in archive.infolist()}
    expected_names = {"MANIFEST.json"}
    channels: dict[int, PreviewADC] = {}
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("Native live preview: invalid ADC record")
        number = _uint(row.get("adc"), "adc")
        if not 1 <= number <= 8 or number in channels:
            raise ValueError("Native live preview: duplicate or invalid ADC number")
        name = row.get("entry")
        if name != f"ADC{number}.f32" or _ENTRY.fullmatch(name or "") is None:
            raise ValueError("Native live preview: unsafe ADC path")
        expected_names.add(name)
        count = _uint(row.get("samples"), "samples")
        rate = _uint(row.get("sample_rate_hz"), "rate")
        first = _uint(row.get("first_sample_index"), "first_index")
        end = _uint(row.get("next_sample_index"), "next_index")
        digest = row.get("sha256")
        captured=row.get("captured_samples")
        if captured is not None and (
                type(captured) is not int or not 0<=captured<1<<64):
            raise ValueError("Native live preview: invalid uint64 captured count")
        if (not 0 < count <= MAX_SAMPLES or not 0 < rate <= 1_000_000 or
                not u32_preview_bounds(first,end,count) or
                not isinstance(digest,str) or _HEX.fullmatch(digest) is None):
            raise ValueError("Native live preview: invalid calibrated sample metadata")
        reported = status["channels"][number-1]
        if (count>reported["samples"]
                or rate not in reported["sample_rates_hz"]
                or reported["sequence_discontinuities"]
                or reported["nonfinite_samples"]
                or not u32_matches_go_status(
                    end,reported.get("next_sample_index"),
                    status_samples=reported["samples"],window_samples=count,
                    captured_samples=captured)):
            raise ValueError("Native live preview: channel count/rate/absolute index mismatch")
        info = archive.getinfo(name)
        if info.file_size != count*4:
            raise ValueError("Native live preview: truncated Float32 channel")
        data = archive.read(name)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Native live preview: ADC SHA256 mismatch")
        values = np.frombuffer(data, dtype="<f4")
        if len(values) != count or not bool(np.isfinite(values).all()):
            raise ValueError("Native live preview: nonfinite or inconsistent ADC")
        channels[number] = PreviewADC(number,rate,first,end,values,digest,captured)
    if actual_names != expected_names:
        raise ValueError("Native live preview: unexpected ZIP members")
    return LivePreview(meta["session_id"],ts,raw,frames,channels)


def load_live_preview(capture_root: str | Path, status: dict, *,
                      now: datetime | None = None) -> LivePreview | None:
    """One local atomic preview per approved GUI capture root; no TCP calls."""
    if status["phase"] != "RECORDING":
        return None
    if status.get("source_rate_transition_during_live",False):
        raise ValueError("Native live preview: original SetRate changed Fs; old single-rate preview is invalid")
    if (status["capture_only"] or status["invalid_frames"] or
            status["snapshot_stale"] or
            (status["seconds_since_last_packet"] is not None and
             status["seconds_since_last_packet"] > 4)):
        raise ValueError("Native live preview: unsafe or stale incoming stream")
    root = Path(capture_root)
    run = Path(status["run_directory"])
    if (root.is_symlink() or not root.is_dir() or run.is_symlink() or
            not run.is_dir() or run.parent.resolve() != root.resolve() or
            run.name != status["session_id"]):
        raise ValueError("Native live preview: foreign run directory")
    source = run / NAME
    if not source.exists():
        return None
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_DISK_BYTES:
        raise ValueError("Native live preview: unsafe/oversized snapshot")
    try:
        with zipfile.ZipFile(source, "r") as archive:
            return _validate_preview_payload(
                archive, status, now or datetime.now(timezone.utc))
    except (zipfile.BadZipFile, EOFError) as exc:
        raise ValueError("Native live preview: corrupted local ZIP") from exc


def _mark_absolute_live_source_window(result: dict, channel: PreviewADC) -> None:
    # The generic offline candidate operates on a local 0-based preview
    # buffer. Do NOT mistake it for absolute device sample index zero.
    evidence=dict(result["input_source_window"])
    extended_first,_=extended_u32_window(
        channel.first_index,channel.next_index,len(channel.samples),
        channel.captured_samples if channel.captured_samples is not None
        else len(channel.samples))
    evidence["live_first_adc_sample_index"]=(
        extended_first+evidence["first_archive_sample_index"])
    evidence["live_last_adc_sample_exclusive"]=(
        extended_first+evidence["last_archive_sample_exclusive"])
    evidence["source_index_u32_wrapped"]=channel.first_index>channel.next_index
    evidence["capture_local_uint64_cursor_confirmed"]=(
        channel.captured_samples is not None)
    evidence["preview_source_calibrated_sha256"]=channel.sha256
    evidence["original_live_rxpos_parity_verified"]=False
    evidence["provisional_not_audited"]=True
    evidence["time_kind"]="ADC_SAMPLE_INDEX_FROM_NATIVE_R6_PREVIEW_NOT_DSP_UTC"
    if channel.number>=9:
        # Source display is relative to GetSignal; byte FRxPos is local.
        # A 32-bit word header is NOT an absolute 32-bit byte clock.
        first=channel.captured_samples-len(channel.samples)
        evidence["live_first_adc_sample_index"]=first+evidence["first_archive_sample_index"]
        evidence["live_last_adc_sample_exclusive"]=first+evidence["last_archive_sample_exclusive"]
        evidence["live_first_tach_byte_pos"]=evidence["live_first_adc_sample_index"]
        evidence["live_last_tach_byte_exclusive"]=evidence["live_last_adc_sample_exclusive"]
        evidence["source_tach_byte_sha256"]=channel.sha256
        evidence["time_kind"]="TACH_CAPTURE_LOCAL_BYTE_POSITION_NOT_DSP_UTC"
    result["input_source_window"]=evidence


def provisional_waveform(
        preview: LivePreview, adc: int, *, ac: bool = False,
        source_h_tag: int | None = None,
        capture_rxpos: int | None = None,
        last_processed_pos: int = 0,
        source_allow_overlap: bool = True) -> dict:
    """Original source PageAdc H scale, using only SHA-confirmed Float32.

    With source_h_tag the exact source count is Fs*menu_ms//1000.
    No synthetic zero-fill or silent downshift. The separate Source
    CheckDataAvailability runtime distinguishes original readiness
    from the stricter, actually verified preview history.
    Without source_h_tag the legacy research latest-30s window remains.
    """
    channel = preview.channels.get(adc)
    if channel is None:
        raise ValueError("Live ADC window not yet available")
    is_tach=adc>=9 and preview.input_domain==TACH_DOMAIN
    if is_tach: ac=False
    total = len(channel.samples)
    source_receipt=None
    source_ms=None
    if source_h_tag is not None:
        visible,source_ms=source_live_adc_menu_length(
            source_h_tag,channel.rate_hz)
        rx=total if capture_rxpos is None else capture_rxpos
        source_receipt=source_getsignal_readiness(
            rx_pos=rx,valid_pos=0,
            last_processed_pos=last_processed_pos,
            signal_length=visible,contiguous=False,
            allow_overlap=source_allow_overlap,
            preview_samples=total,
        )
        if not source_receipt.verified_preview_window_ready:
            raise ValueError(
                f"GetSignal {source_ms} мс: требуется {visible} реальных "
                f"отсчётов и подтверждение нового окна, "
                f"доступно в preview {total}, новых от последнего "
                f"обновления {max(0,rx-last_processed_pos)}")
    else:
        # Latest-30s research fallback is not an original bAdcHScale
        # selection. Original source menu Tag0 is 20s, not 30s.
        visible = min(total, int(channel.rate_hz) * 30)
    start = total - visible
    duration = visible / channel.rate_hz
    out = waveform_for_zip(
        Path("NOT_OPENED"), adc, start/channel.rate_hz, duration,
        mode="ac" if ac else "acdc", display_order="chronological",
        sample_provider=preview.samples_for_offline_candidate,
        include_full_cursor=source_h_tag is not None)
    extended_first,_=extended_u32_window(
        channel.first_index,channel.next_index,total,
        channel.captured_samples if channel.captured_samples is not None
        else total)
    offset = ((channel.captured_samples-total) if is_tach else extended_first)/channel.rate_hz
    out["time_s"] = [offset + float(x) for x in out["time_s"]]
    _mark_absolute_live_source_window(out,channel)
    if source_h_tag is not None:
        # The original PageAdc plots the returned REVERSED GetSignal
        # buffer with ScrWidth<0. Preserve old absolute-preview time_s
        # only as research metadata; the visible source X uses these
        # full-buffer-relative peaks, never a stale LOD cursor.
        full=out["cursor_full_reversed_getsignal"]
        axis_factor=1. if source_ms>=10000 else 1000.
        x,y=reduce_minmax(full,channel.rate_hz,0,4000)
        out["cursor_plot_x"]=[float(np.float32(v*axis_factor)) for v in x]
        out["cursor_plot_y"]=y
        out["cursor_axis_unit"]="с" if source_ms>=10000 else "мс"
        out["cursor_axis_max"]=(source_ms/1000. if source_ms>=10000
                                else float(source_ms))
        out["cursor_xscale_single"]=float(np.float32(
            axis_factor/channel.rate_hz))
        out["cursor_original_reverse_x_candidate"]=True
        out["cursor_plot_is_peak_preserving_lod"]=True
    is_source=(
        preview.source_ring_provenance_verified and
        preview.input_domain in SOURCE_LIVE_ADC_DOMAINS)
    out["source"] = (("LIVE_SOURCE_TMVK_CHANNEL_FRANGE1_UNVERIFIED" if channel.source_f_range_single==1 else
                      "LIVE_SOURCE_TMVK_CHANNEL_CONFIG_FRANGE_UNVERIFIED")
                     if is_source else
                     "LIVE_NATIVE_R6_CALIBRATED_PREVIEW_UNVERIFIED")
    out["input_domain"]=(
        ("original_live_f_range1" if channel.source_f_range_single==1 else
         "original_live_config_f_range") if is_source else DOMAIN)
    out["source_live_f_range_single"]=channel.source_f_range_single if is_source else None
    out["source_range_state"]=channel.source_range_state if is_source else None
    out["source_live_units"]=source_live_units_text(channel.source_range_state) if is_source else None
    out["provisional_not_audited"] = True
    out["source_waveform_latest_real_samples"] = visible
    out["source_waveform_max_display_seconds"] = 30
    out["source_live_preview_ring_samples"] = total
    if source_receipt is not None:
        out["original_bAdcHScale_tag"] = source_h_tag
        out["original_bAdcHScale_milliseconds"] = source_ms
        out["original_bAdcHScale_requested_samples"] = visible
        out["source_getsignal_readiness"] = source_receipt.receipt()
        out["source_getsignal_exact_selected_count"] = (
            out["window_samples"] == visible)
    if is_tach:
        out.update(source="LIVE_SOURCE_TACH_BYTE_GETSIGNAL_CANDIDATE",
            input_domain=TACH_DOMAIN,source_live_f_range_single=1.0,
            source_range_state=None,source_live_units="",unit="",
            source_sample_width_bytes=1,source_tach_byte_normalization_divisor=255,
            warning="TACH: Byte/255, без NoDC и FIR; Win32 не аттестован.")
        return out
    out["warning"] = (
        f"Исходный живой Float32 FRange={channel.source_f_range_single:g}, SHA-проверенное Go кольцо; "
        "Win32 численный паритет не доказан."
        if is_source else
        "Предварительный GetSignal-кандидат по уже калиброванным "
        "битам R6.1. Не результат оригинального MVKView.")
    return out


def provisional_spectrum(preview: LivePreview, adc: int, mode: int = 1,
                         *, n_fft: int | None = None,
                         full_bins: bool = False) -> dict:
    """Compute only the SELECTED source bSpecLines N, no silent fallback.

    Source _Unit128.pas 0084819A..008481AA assigns gvar_008D3450
    to GetSpectrum Params+4. The prior live preview auto-selected the
    largest available power of two, misrepresenting the visible source
    menu, currently default N=65536. Preserve the no-argument API
    solely for offline/test callers; Qt always supplies its menu N.
    """
    if type(full_bins) is not bool:
        raise ValueError("Live full_bins must be Boolean")
    channel = preview.channels.get(adc)
    if channel is None or len(channel.samples) < 1024:
        raise ValueError("Live ADC has insufficient real FFT history")
    if n_fft is None:
        n_fft = 1 << (min(len(channel.samples), MAX_SAMPLES).bit_length()-1)
    elif (type(n_fft) is not int or n_fft not in
          (1024, 4096, 8192, 16384, 32768, 65536, 131072, 262144)):
        raise ValueError("Invalid original bSpecLines N")
    if len(channel.samples) < n_fft:
        raise ValueError(
            f"FFT N={n_fft}: требуется {n_fft} реальных отсчётов, "
            f"в текущем Live окне {len(channel.samples)}; "
            "уменьшение N или нулевое дополнение запрещено")
    is_tach=adc>=9 and preview.input_domain==TACH_DOMAIN
    is_source=(
        preview.source_ring_provenance_verified and
        preview.input_domain in SOURCE_LIVE_ADC_DOMAINS)
    out = spectrum_for_zip(
        Path("NOT_OPENED"), adc, n_fft, mode, None,
        # Full N/2 power and summary are still computed. Only the
        # on-screen pyqtgraph polyline is reduced to peak-preserving
        # <=5000 bins, avoiding a 131072-point repaint every tick.
        max_hz=channel.rate_hz/2,
        max_points=n_fft//2 if full_bins else 5000,
        backend="idr_float32",
        f_range=channel.source_f_range_single if is_source else 1.0, input_domain=(
            DOMAIN_ORIGINAL_STORAGE if is_source else "calibrated_bin"),
        sample_provider=preview.samples_for_offline_candidate)
    _mark_absolute_live_source_window(out,channel)
    out["source"] = "LIVE_NATIVE_R6_FFT_IDR_CANDIDATE_UNVERIFIED"
    out["provisional_not_audited"] = True
    out["source_selected_fft_n"] = n_fft
    out["source_fft_n_matches_requested_bSpecLines"] = True
    out["original_bSpecLines_source"] = "_Unit128.pas:0084819A-00848200"
    out["source_history_uses_exact_calibrated_float32"] = not is_source
    out["source_history_uses_original_live_f_range1_float32"] = is_source and channel.source_f_range_single==1
    out["source_history_uses_original_live_float32"] = is_source
    out["source_live_f_range_single"]=channel.source_f_range_single if is_source else None
    out["source_range_state"]=channel.source_range_state if is_source else None
    out["source_fft_full_power_bins"] = n_fft//2
    out["source_plot_peak_preserving_max_points"] = 5000
    out["original_delphi_numerical_parity"] = False
    if is_tach:
        out.update(source_history_uses_exact_calibrated_float32=False,
            source_live_f_range_single=1.0,source_range_state=None,
            source_sample_width_bytes=1,source_tach_byte_normalization_divisor=255,
            warning="TACH Byte/255 -> удаление среднего -> Hann/FFT; Win32 не аттестован.")
        return out
    out["warning"] = (
        f"Оригинальное живое кольцо Float32/FRxPos с FRange={channel.source_f_range_single:g}, "
        "без коэффициента экспортёра BIN; x87/Delphi FFT ещё не доказан."
        if is_source else
        "Live FFT из калиброванного BIN-превью R6.1 (FRange=1, "
        "без второго gain). Оригинальный MVKView parity НЕ доказан.")
    return out
