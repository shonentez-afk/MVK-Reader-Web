"""Source-backed Mode1 TACH Byte graphs and read-only saved-file workflow."""
from datetime import datetime, timezone
import hashlib
import json

import numpy as np
import pytest

from ..core.direct_bin_session import DirectBinSession, TACH_PROVENANCE
from ..core.offline_export import spectrum_for_zip
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from ..core.original_file_workbench import source_file_workbench
from ..core.original_mode2_source_files import build_original_tsxml_compatible
from ..core.original_pagefile_recording import (
    OriginalFileNameOptions, OriginalPageFileSelection, export_selected_original_pagefile,
)
from ..core.waveform_hover_idr_candidate import prepare_waveform_hover_window

STAMP = "2026-11-24--13-00-00"
NOW = datetime(2026, 11, 24, 13, 1, tzinfo=timezone.utc)


def make_saved_pair(folder, channel=9, *, count=2048, rate=8192, name=None):
    label = f"TACH{channel-8}" if channel >= 9 else f"ADC{channel}"
    name = name or f"MVK99999-{label}-{STAMP}.bin"
    if channel >= 9:
        raw = np.resize(np.array([0, 25, 130, 255, 239, 100, 30, 7], dtype="u1"), count)
    else:
        raw = np.asarray(np.sin(np.arange(count)/8), dtype="<f4")
    file = folder/name
    file.write_bytes(raw.tobytes())
    content, _ = build_original_tsxml_compatible(
        channel=channel, binary_basename=name, size_bytes=raw.nbytes,
        rate_hz=rate, local_time=NOW, device_label="MVK99999", channel_label=label,
        **({"adc_units": "м/с2", "adc_gain": 2.5} if channel <= 8 else {}))
    xml = folder/(name+".tsxml")
    xml.write_bytes(content)
    return file, xml, raw


def test_mode1_tach_byte_exact_wave_and_full_spectrum_pipelines(tmp_path):
    file, xml, u8 = make_saved_pair(tmp_path, 9)
    session = DirectBinSession.open(xml)
    flow = OfflineMeasurementFlow.bind(session)
    normalized = (u8.astype(np.float64)/255).astype("<f4")
    data, fs, audit, name = flow.samples()
    assert session.available_channels == (9,) and flow.channel == 9 and flow.tach_byte
    assert name == file.name and fs == 8192
    assert data.tobytes() == normalized.tobytes() and not data.flags.writeable
    assert audit["source"] == TACH_PROVENANCE
    assert audit["declared_units_text"] == "Count" and audit["source_tach_byte_normalization_divisor"] == 255
    verify = session.verify()
    assert verify["channels"][0]["samples"] == len(u8)
    assert verify["channels"][0]["real_data_type"] == "Byte"
    assert flow.status_snapshot() is None and not flow.source_record()["dsp_values_available"]
    assert flow.source_record()["source_bin_sha256"] == hashlib.sha256(u8.tobytes()).hexdigest()
    assert dict(source_file_workbench(flow).metadata)["Выбранный канал"] == "TACH1"

    wave = flow.waveform(8/fs, 1024/fs, "ac", points=4096, display_order="getsignal_buffer")
    assert wave["mode"] == "acdc" and wave["unit"] == ""
    assert wave["removed_mean_m_s2"] == 0
    assert np.array_equal(wave["amplitude"], normalized[8:1032][::-1])
    assert wave["input_source_window"]["source_tach_normalized_byte_window"]
    assert wave["peak_m_s2"] == 1
    exact = session.exact_sample(9, 8/fs, 8/fs, 1024/fs, "ac", "getsignal_buffer")
    hover = prepare_waveform_hover_window(session, 9, start_s=8/fs, seconds=1024/fs,
                                          mode="ac", display_order="getsignal_buffer")
    assert exact["index"] == hover.pick(8/fs)["index"] == 1031
    assert exact["value_m_s2"] == hover.pick(8/fs)["value_m_s2"] == normalized[1031]
    assert exact["mode"] == hover.mode == "acdc"

    for mode, unit in enumerate(("дБ", "", "~", "~~")):
        spectrum = flow.spectrum(1024, mode, 8/fs, fs/2, 512)
        # Reference uses explicitly normalized known Byte values and the same
        # original FFT math; not a claim about Win32 x87 equivalence.
        expected = spectrum_for_zip(file, 9, 1024, mode, 8/fs, fs/2, 512,
            f_range=1.0, sample_provider=lambda _: (
                normalized, fs, {"source_tach_byte_window": True}, file.name))
        assert spectrum["unit"] == unit and spectrum["f_range_used"] == 1.0
        assert spectrum["df_hz"] == 8 and spectrum["detrended_before_fft"]
        assert spectrum["input_source_window"] == wave["input_source_window"]
        assert spectrum["amplitude"] == expected["amplitude"]
        if mode==1:
            assert spectrum["spectrum_summary"]["output_peak_frequency_hz"] == pytest.approx(1024., abs=8)
    for run in (lambda: flow.envelope(20, 0., 0.125, None),
                lambda: flow.spectrum_envelope(20, 1024, None),
                lambda: session.narrowband(9, 50),
                lambda: flow.spectrum(1024, f_range=2.5)):
        with pytest.raises(ValueError, match="TACH Byte"):
            run()


def test_primary_reopen_and_pagefile_copies_original_tach_bytes_only(tmp_path):
    adc, _, floats = make_saved_pair(tmp_path, 4)
    tach, sx, original = make_saved_pair(tmp_path, 10, count=1101)
    session = DirectBinSession.open(sx)
    flow = OfflineMeasurementFlow.bind(session)
    assert session.available_channels == (4, 10) and session.primary_channel == 10
    assert session.verify()["channels"][1]["samples"] == 1101  # not floored to words
    assert flow.channel == 10 and flow.tach_byte
    assert not flow.select(channel=4).tach_byte
    assert flow.select(channel=4).samples()[0].tobytes() == floats.tobytes()
    assert DirectBinSession.open(adc).primary_channel == 4

    select = OriginalPageFileSelection.for_flow(flow).set_checked(
        "channels", 3, False, flow=flow)
    assert select.report()["selected_tachs"] == [2]
    report = export_selected_original_pagefile(
        flow, select, OriginalFileNameOptions(use_custom_name=False), tmp_path, when=NOW)
    exported = tmp_path/report["output_folder"]
    assert (exported/tach.name).read_bytes() == original.tobytes()
    assert (exported/sx.name).read_bytes() == sx.read_bytes()
    assert not (exported/adc.name).exists()
    copied = json.loads((exported/"PAGEFILE_SELECTION.json").read_text(encoding="utf-8"))
    assert copied["selected_native_tach_channels"] == []
    assert copied["selected_direct_tach_channels"] == [2]
    assert copied["saved_tach_copied_as_original_bytes"]
    assert not copied["device_io_executed"]
    assert DirectBinSession.open(exported/sx.name).primary_channel == 10


def test_short_tach_can_reopen_wave_but_fft_requires_real_samples(tmp_path):
    file, _, data = make_saved_pair(tmp_path, 9, count=97)
    flow = OfflineMeasurementFlow.bind(DirectBinSession.open(file))
    assert flow.waveform(0, .1)["window_samples"] == len(data)
    with pytest.raises(ValueError, match="Не хватает"):
        flow.spectrum(1024)


@pytest.mark.parametrize(("before", "after"), [
    (b"<ChannelNumber>9", b"<ChannelNumber>1"),
    (b"<Units>Count", b"<Units>count"),
    (b"<InternalChannelGain>1", b"<InternalChannelGain>2"),
    (b"<DataOffset>0", b"<DataOffset>1"),
    (b"<DataLength>2048", b"<DataLength>2047"),
    (b".bin</DataFileName>", b".other.bin</DataFileName>"),
])
def test_rejects_mismatched_byte_annexe(tmp_path, before, after):
    file, xml, _ = make_saved_pair(tmp_path, 9)
    data = xml.read_bytes()
    assert before in data
    xml.write_bytes(data.replace(before, after, 1))
    with pytest.raises(ValueError):
        DirectBinSession.open(file)


def test_legacy_byte_gain_fallback_is_one_only_and_dtd_forbidden(tmp_path):
    file, xml, _ = make_saved_pair(tmp_path, 10)
    content = xml.read_text(encoding="cp1251")
    stripped = "\n".join(x for x in content.splitlines()
                         if "<InternalChannelGain>" not in x)
    xml.write_text(stripped, encoding="cp1251")
    assert DirectBinSession.open(file).spectrum(10, 1024)["f_range_used"] == 1.
    malicious = stripped.replace("windows-1251", "utf-16").replace(
        "<MainRoot>", '<!DOCTYPE MainRoot [<!ENTITY bad "rejected">]><MainRoot>')
    xml.write_bytes(malicious.encode("utf-16"))
    with pytest.raises(ValueError, match="разбора XML"):
        DirectBinSession.open(file)


def test_tach_binary_and_sidecar_each_revalidated_after_open(tmp_path):
    file, xml, data = make_saved_pair(tmp_path, 9)
    session = DirectBinSession.open(file)
    content = xml.read_bytes()
    xml.write_bytes(content.replace(b"<Units>Count", b"<Units>count"))
    with pytest.raises(ValueError, match="изменён"):
        session.samples(9)
    xml.write_bytes(content)
    modified = data.copy()
    modified[7] ^= 1
    file.write_bytes(modified.tobytes())
    with pytest.raises(ValueError, match="изменён"):
        session.waveform(9, 0., .125)
