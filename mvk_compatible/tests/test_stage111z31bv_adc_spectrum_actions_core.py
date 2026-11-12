"""BV: source PageAdc full FIR cursor and PageSpectrum 3-field Copy/Save.

Pure Core, synthetic Native ZIP and private-free FIR coefficients only.
Preserves Source Unit128 handler addresses, ADC/FFT/source provenance
and original daily SPEC-FREQ pipe-append structure without device I/O.
"""
from __future__ import annotations
from dataclasses import replace
from datetime import date
from hashlib import sha256
import math
from pathlib import Path

import numpy as np
import pytest

from .test_offline_core import fixture_zip
from .test_stage111z16_direct_bin_tsxml import _make_pair
from .test_envelope_idr_candidate import fake_profile
from ..core.offline_export import OfflineSession
from ..core.direct_bin_session import DirectBinSession
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from ..core.original_adc_spectrum_actions import (
    OriginalSpectrumAction,OriginalEnvelopeCursor,
    spectrum_source_daily_path,append_source_spec_freq_csv,
    SPEC_CSV_HEADER,SPEC_CSV_PREFIX,SPECTRUM_COPY_SOURCE,
    SPECTRUM_SAVE_SOURCE,WAVE_CURSOR_SOURCE,
)


def _native(tmp_path,adc=1):
    source=fixture_zip(tmp_path,sample_count=4096)
    session=OfflineSession.open(source)
    flow=OfflineMeasurementFlow.bind(session,channel=adc,tick_index=0)
    d=flow.spectrum(
        1024,1,0.,max_hz=1e9,max_points=512,backend="numpy")
    return source,flow,d


def test_real_source_three_value_spectrum_from_selected_adc_nfft_and_mode(tmp_path):
    source,flow,spectrum=_native(tmp_path)
    act=OriginalSpectrumAction.from_view(flow,spectrum)
    assert act.adc==1 and act.n_fft==1024
    assert act.spectrum_mode==1
    assert act.current_dsp_tick_index==0
    assert act.source_bin_sha256==flow.source_record()["source_bin_sha256"]
    assert not act.direct_bin_uncalibrated
    assert act.values==tuple(spectrum["spectrum_summary"][x] for x in (
        "output_mean","output_peak_frequency_hz","output_peak_y"))
    three=act.clipboard_text(decimal_separator=",").split("\t")
    assert len(three)==3
    assert all(part.strip() for part in three)
    assert "\r" not in "".join(three) and "\n" not in "".join(three)
    assert len(act.pipe_row().split("|"))==3
    assert act.receipt()["original_clipboard_handler"]==SPECTRUM_COPY_SOURCE
    assert act.receipt()["original_csv_handler"]==SPECTRUM_SAVE_SOURCE
    assert not act.receipt()["original_delphi_float_format_parity_verified"]
    assert not act.receipt()["hardware_commands_sent"]
    assert sha256(source.read_bytes()).hexdigest()


def test_spec_freq_original_daily_pipe_header_first_write_append_roundtrip(tmp_path):
    source,flow,spectrum=_native(tmp_path)
    oldsha=sha256(source.read_bytes()).hexdigest()
    action=OriginalSpectrumAction.from_view(flow,spectrum)
    daily=spectrum_source_daily_path(tmp_path,date(2026,11,12))
    assert daily.name=="SPEC-FREQ-2026-11-12.csv"
    assert SPEC_CSV_PREFIX=="SPEC-FREQ-"
    first=append_source_spec_freq_csv(action,flow,daily,spectrum=spectrum)
    raw=daily.read_bytes()
    assert raw.startswith(("sep=|\r\n"+SPEC_CSV_HEADER+"\r\n").encode("utf-8"))
    assert raw.count(b"sep=|")==1
    assert len(raw.splitlines())==3
    assert raw.splitlines()[2].decode("utf-8")==action.pipe_row()
    assert len(raw.splitlines()[2].split(b"|"))==3
    assert first["independent_roundtrip_verified"]
    assert first["current_saved_row"]==action.pipe_row()
    assert first["appended_existing_candidate"] is False
    assert first["full_csv_sha256"]==sha256(raw).hexdigest()
    assert not first["original_csv_codepage_and_header_parity_verified"]

    second=append_source_spec_freq_csv(action,flow,daily,spectrum=spectrum)
    assert second["appended_existing_candidate"] is True
    assert len(daily.read_bytes().splitlines())==4
    assert daily.read_bytes().count(b"sep=|")==1
    assert daily.read_bytes().endswith((action.pipe_row()+"\r\n").encode("utf-8"))
    assert sha256(source.read_bytes()).hexdigest()==oldsha
    assert not first["hardware_commands_sent"]


def test_spectrum_copy_save_rejects_mismatched_adc_tick_n_and_vendor_file(tmp_path):
    source,flow,spectrum=_native(tmp_path)
    action=OriginalSpectrumAction.from_view(flow,spectrum)
    with pytest.raises(ValueError,match="stale"):
        action.validate_flow(flow.select(channel=2))
    if flow.session.updates>1:
        with pytest.raises(ValueError,match="stale"):
            action.validate_flow(flow.select(tick_index=1))
    other=dict(spectrum)
    other["channel"]=2
    with pytest.raises(ValueError,match="channel"):
        OriginalSpectrumAction.from_view(flow,other)
    other=dict(spectrum)
    other["spectrum_summary"]={**spectrum["spectrum_summary"],
                               "output_peak_frequency_hz":1e8}
    with pytest.raises(ValueError):
        OriginalSpectrumAction.from_view(flow,other)

    vendor=tmp_path/"SPEC-FREQ-2026-11-12.csv"
    vendor.write_bytes(b"sep=|\r\nREAL ORIGINAL VENDOR 1|2|3\r\n1|2|3\r\n")
    original=vendor.read_bytes()
    with pytest.raises(ValueError,match="vendor"):
        append_source_spec_freq_csv(action,flow,vendor,spectrum=spectrum)
    assert vendor.read_bytes()==original
    for path in ("wrong.csv","SPEC-FREQ-2026-13-45.txt"):
        with pytest.raises(ValueError):
            append_source_spec_freq_csv(
                action,flow,tmp_path/path,spectrum=spectrum)
    assert sha256(source.read_bytes()).hexdigest()


def test_source_spec_freq_direct_bin_requires_distinct_unsafe_units_notice(tmp_path):
    source,_,_=_make_pair(tmp_path,adc=4,n=8192)
    flow=OfflineMeasurementFlow.bind(DirectBinSession.open(source),channel=4)
    spec=flow.spectrum(1024,1,0,max_hz=1e9,max_points=512,backend="numpy")
    action=OriginalSpectrumAction.from_view(flow,spec)
    assert action.direct_bin_uncalibrated
    assert action.clipboard_text().startswith("НЕ КАЛИБРОВАНО")
    path=tmp_path/"SPEC-FREQ-2026-11-12.csv"
    with pytest.raises(ValueError,match="calibration"):
        append_source_spec_freq_csv(action,flow,path,spectrum=spec)
    assert not path.exists()


def test_source_full_fir_cursor_uses_raw_filtered_array_not_decimated_plot(tmp_path):
    source=fixture_zip(tmp_path,sample_count=4096)
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(source),channel=1)
    original_hash=sha256(source.read_bytes()).hexdigest()
    wave=flow.envelope(
        20,start_s=2099/65536,seconds=1997/65536,
        profile=fake_profile(i=1.,q=.4),
        display_order="chronological",points=32)
    full=wave["cursor_full_samples_float32"]
    assert len(full)==wave["output_samples"]==1024
    assert len(wave["amplitude"])<len(full)
    assert full.dtype==np.dtype("float32")
    assert not full.flags.writeable
    assert wave["cursor_full_samples_sha256"]==sha256(
        np.asarray(full,dtype="<f4").tobytes()).hexdigest()
    cursor=OriginalEnvelopeCursor.from_trace(flow,wave)
    assert cursor.provenance==WAVE_CURSOR_SOURCE
    assert cursor.channel==1 and cursor.code==20
    index=101
    chosen=cursor.pick(index/cursor.output_hz)
    assert chosen["output_index"]==index
    assert chosen["value_from_full_filtered_float32"]==float(full[index])
    assert not chosen["original_absolute_envelope_time_verified"]
    assert not chosen["original_pixel_geometry_verified"]
    assert not chosen["physical_calibration_verified"]
    assert chosen["input_bin_sha256"]==flow.source_record()["source_bin_sha256"]
    with pytest.raises(ValueError):
        cursor.pick(-.001)
    with pytest.raises(ValueError):
        cursor.pick(1024/cursor.output_hz)
    assert sha256(source.read_bytes()).hexdigest()==original_hash


def test_source_fir_cursor_rejects_tampered_trace_or_wrong_selected_adc(tmp_path):
    file=fixture_zip(tmp_path,sample_count=4096)
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(file),channel=1)
    d=flow.envelope(
        20,start_s=2099/65536,seconds=1997/65536,
        profile=fake_profile(),display_order="getsignal_buffer",points=70)
    reversed_cursor=OriginalEnvelopeCursor.from_trace(flow,d)
    assert reversed_cursor.output_order=="getsignal_buffer"
    with pytest.raises(ValueError,match="channel"):
        OriginalEnvelopeCursor.from_trace(flow.select(channel=2),d)
    bad=dict(d)
    bad["cursor_full_samples_sha256"]="0"*64
    with pytest.raises(ValueError,match="SHA mismatch"):
        OriginalEnvelopeCursor.from_trace(flow,bad)
    bad=dict(d)
    bad["cursor_full_samples_float32"]=np.asarray([np.nan],dtype=np.float32)
    with pytest.raises(ValueError,match="Exact full"):
        OriginalEnvelopeCursor.from_trace(flow,bad)
