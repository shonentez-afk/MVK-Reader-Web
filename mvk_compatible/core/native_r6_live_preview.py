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
from .offline_export import waveform_for_zip, spectrum_for_zip

NAME = "MVK_NATIVE_LIVE_PREVIEW.zip"
SCHEMA = "MVK_NATIVE_R6_CALIBRATED_PREVIEW_V1"
DOMAIN = "CALIBRATED_NATIVE_R6_BIN_SPOOL_FLOAT32"
MAX_SAMPLES = 8192
MAX_DISK_BYTES = 500_000
MAX_MANIFEST = 16_384
MAX_UNCOMPRESSED_BYTES = MAX_SAMPLES * 4 * 8 + MAX_MANIFEST
_HEX = re.compile(r"[a-f0-9]{64}\Z")
_ENTRY = re.compile(r"ADC([1-8])\.f32\Z")


def _uint(value, name: str) -> int:
    if type(value) is not int or value < 0 or value > 2**32:
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


@dataclass(frozen=True)
class LivePreview:
    session_id: str
    updated_utc: datetime
    raw_bytes: int
    frames_decoded: int
    channels: dict[int, PreviewADC]
    input_domain: str = DOMAIN
    provisional: bool = True

    def samples_for_offline_candidate(self, channel: int):
        ch = self.channels.get(channel)
        if ch is None:
            raise ValueError(f"ADC{channel}: no real samples in provisional window")
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
    raw = _uint(meta.get("raw_bytes"), "raw_bytes")
    frames = _uint(meta.get("frames_decoded"), "frames_decoded")
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
        if (not 0 < count <= MAX_SAMPLES or not 0 < rate <= 1_000_000 or
                end-first != count or end > 2**32 or
                not isinstance(digest, str) or _HEX.fullmatch(digest) is None):
            raise ValueError("Native live preview: invalid calibrated sample metadata")
        reported = status["channels"][number-1]
        if (count > reported["samples"] or
                rate not in reported["sample_rates_hz"] or
                reported["sequence_discontinuities"] or reported["nonfinite_samples"]):
            raise ValueError("Native live preview: channel count/rate/quality mismatch")
        info = archive.getinfo(name)
        if info.file_size != count*4:
            raise ValueError("Native live preview: truncated Float32 channel")
        data = archive.read(name)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Native live preview: ADC SHA256 mismatch")
        values = np.frombuffer(data, dtype="<f4")
        if len(values) != count or not bool(np.isfinite(values).all()):
            raise ValueError("Native live preview: nonfinite or inconsistent ADC")
        channels[number] = PreviewADC(number,rate,first,end,values,digest)
    if actual_names != expected_names:
        raise ValueError("Native live preview: unexpected ZIP members")
    return LivePreview(meta["session_id"],ts,raw,frames,channels)


def load_live_preview(capture_root: str | Path, status: dict, *,
                      now: datetime | None = None) -> LivePreview | None:
    """One local atomic preview per approved GUI capture root; no TCP calls."""
    if status["phase"] != "RECORDING":
        return None
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
    evidence["live_first_adc_sample_index"]=(
        channel.first_index+evidence["first_archive_sample_index"])
    evidence["live_last_adc_sample_exclusive"]=(
        channel.first_index+evidence["last_archive_sample_exclusive"])
    evidence["preview_source_calibrated_sha256"]=channel.sha256
    evidence["original_live_rxpos_parity_verified"]=False
    evidence["provisional_not_audited"]=True
    evidence["time_kind"]="ADC_SAMPLE_INDEX_FROM_NATIVE_R6_PREVIEW_NOT_DSP_UTC"
    result["input_source_window"]=evidence


def provisional_waveform(preview: LivePreview, adc: int, *, ac: bool = False) -> dict:
    channel = preview.channels.get(adc)
    if channel is None:
        raise ValueError("Live ADC window not yet available")
    duration = len(channel.samples)/channel.rate_hz
    out = waveform_for_zip(
        Path("NOT_OPENED"), adc, 0, duration,
        mode="ac" if ac else "acdc", display_order="chronological",
        sample_provider=preview.samples_for_offline_candidate)
    offset = channel.first_index/channel.rate_hz
    out["time_s"] = [offset + float(x) for x in out["time_s"]]
    _mark_absolute_live_source_window(out,channel)
    out["source"] = "LIVE_NATIVE_R6_CALIBRATED_PREVIEW_UNVERIFIED"
    out["provisional_not_audited"] = True
    out["warning"] = ("Предварительный GetSignal-кандидат по уже калиброванным "
                      "битам R6.1. Не результат оригинального MVKView.")
    return out


def provisional_spectrum(preview: LivePreview, adc: int, mode: int = 1) -> dict:
    channel = preview.channels.get(adc)
    if channel is None or len(channel.samples) < 1024:
        raise ValueError("Live ADC has insufficient real FFT history")
    n_fft = 1 << (min(len(channel.samples), MAX_SAMPLES).bit_length()-1)
    out = spectrum_for_zip(
        Path("NOT_OPENED"), adc, n_fft, mode, None,
        max_hz=channel.rate_hz/2, max_points=n_fft//2,
        backend="idr_float32",
        f_range=1.0, input_domain="calibrated_bin",
        sample_provider=preview.samples_for_offline_candidate)
    _mark_absolute_live_source_window(out,channel)
    out["source"] = "LIVE_NATIVE_R6_FFT_IDR_CANDIDATE_UNVERIFIED"
    out["provisional_not_audited"] = True
    out["warning"] = (
        "Live FFT из реальных калиброванных отсчётов R6.1 (FRange=1 после "
        "BIN spool, без второго gain). Оригинальный MVKView parity НЕ доказан.")
    return out
