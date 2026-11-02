"""Stage111Z29A: local-only preview first-index continuity across GetSignal/FFT.

No live socket, no original device data. Preview remains provisional.
"""
from __future__ import annotations

from datetime import datetime,timezone
import hashlib

import numpy as np

from mvk_compatible.core.native_r6_live_preview import (
    LivePreview,PreviewADC,provisional_waveform,provisional_spectrum
)


def _preview(n=8192,first=2**20+19):
    data=np.asarray(
        .13*np.sin(2*np.pi*300*np.arange(n,dtype=np.float64)/65536),
        dtype="<f4")
    ch=PreviewADC(
        number=3,rate_hz=65536,first_index=first,next_index=first+n,
        samples=data,sha256=hashlib.sha256(data.tobytes()).hexdigest())
    preview=LivePreview(
        session_id="SYNTHETIC_NOT_REAL",
        updated_utc=datetime(2026,11,2,tzinfo=timezone.utc),
        raw_bytes=8192,frames_decoded=400,channels={3:ch})
    return preview,ch


def test_getsignal_and_fft_are_same_absolute_real_samples_when_preview_full():
    preview,ch=_preview()
    wave=provisional_waveform(preview,3,ac=True)
    spec=provisional_spectrum(preview,3,mode=0)
    a=wave["input_source_window"]
    b=spec["input_source_window"]
    assert a["live_first_adc_sample_index"]==b["live_first_adc_sample_index"]==ch.first_index
    assert a["live_last_adc_sample_exclusive"]==b["live_last_adc_sample_exclusive"]==ch.next_index
    assert a["source_float32_le_sha256"]==b["source_float32_le_sha256"]==ch.sha256
    assert a["preview_source_calibrated_sha256"]==b["preview_source_calibrated_sha256"]
    assert a["original_live_rxpos_parity_verified"] is False
    assert not a["source_is_native_r6_sha_audited_export"]
    assert a["provisional_not_audited"] and b["provisional_not_audited"]
    assert spec["df_hz"]==8
    assert wave["time_s"][0]>=ch.first_index/ch.rate_hz
    assert wave["time_s"][0]<ch.next_index/ch.rate_hz


def test_partial_preview_fft_is_last_full_power_of_two_not_wave_window():
    preview,ch=_preview(n=6000,first=123400)
    wave=provisional_waveform(preview,3)
    spec=provisional_spectrum(preview,3,mode=1)
    a=wave["input_source_window"]
    b=spec["input_source_window"]
    assert a["live_first_adc_sample_index"]==123400
    assert a["live_last_adc_sample_exclusive"]==129400
    assert b["live_first_adc_sample_index"]==129400-4096
    assert b["live_last_adc_sample_exclusive"]==129400
    assert a["source_float32_le_sha256"]!=b["source_float32_le_sha256"]
    assert spec["n_fft"]==4096
    assert not b["original_runtime_getsignal_fft_window_parity_verified"]
