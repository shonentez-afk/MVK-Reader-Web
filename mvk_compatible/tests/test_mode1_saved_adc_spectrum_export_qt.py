"""Synthetic regression for saved BIN/TSXML Copy/Save, not hardware attestation."""
from datetime import date, datetime, timezone
from math import floor, log10

import numpy as np
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from .test_desktop_qt import qt_app
from .test_stage111z16_direct_bin_tsxml import _make_pair
from .test_stage111z31en_saved_tach_qt import _write_bin
from ..core.direct_bin_session import DirectBinSession
from ..core.original_mode2_source_files import build_original_tsxml_compatible
from ..desktop.main_window import MainWindow


def _adc(tmp_path, channel, unit, gain, *, fs=8192, n=4096):
    label = f"ADC{channel}"
    name = f"MVK00000043-{label}-2026-11-24--10-00-00.bin"
    path = tmp_path / name
    t = np.arange(n, dtype=float) / fs
    samples = ((.71 + t) * np.sin(2 * np.pi * (64.5 + channel) * t)).astype("<f4")
    path.write_bytes(samples.tobytes())
    xml, _ = build_original_tsxml_compatible(
        channel=channel, binary_basename=name, size_bytes=samples.nbytes,
        rate_hz=fs, local_time=datetime(2026, 11, 24, 10, 0, 1, tzinfo=timezone.utc),
        device_label="MVK00000043", channel_label=label, adc_units=unit, adc_gain=gain)
    sidecar = path.with_name(name + ".tsxml")
    sidecar.write_bytes(xml)
    return path, sidecar


@pytest.mark.parametrize(("locale_name", "separator"), [("ru_RU", ","), ("en_US", ".")])
def test_mode1_saved_adc_exports_real_selected_channel_units(
        tmp_path, qt_app, monkeypatch, locale_name, separator):
    source = tmp_path / "source"
    source.mkdir()
    gains = (12.25, 6., 1., 7., 3.5, 5., 6.25, 2.5)
    acceleration = ("м/с2", "м/с2", "мм/с", "мкм")
    non_acceleration = ("g", "g", "~g", "~~g")
    channels = tuple(
        (channel, gain, acceleration if channel % 2 else non_acceleration)
        for channel, gain in enumerate(gains, 1)
    )
    inputs = [_adc(source, channel, units[0], gain) for channel, gain, units in channels]
    first, selected_sidecar = inputs[0][0], inputs[-1][1]

    def unexpected(*args):
        pytest.fail(str(args[-1]))

    for method in ("critical", "warning", "question"):
        monkeypatch.setattr(QMessageBox, method, unexpected)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", unexpected)
    previous_locale = QLocale()
    window = MainWindow()
    try:
        QLocale.setDefault(QLocale(locale_name))
        window.open_archive(first)
        window.original_root_tabs.setCurrentIndex(4)
        qt_app.processEvents()
        assert window.session.available_channels == tuple(range(1, 9))
        for channel, gain, units in channels:
            window.adc.setCurrentIndex(channel - 1)
            qt_app.processEvents()
            assert window._ch() == channel
            for mode, unit in enumerate(units):
                window.spec_mode.setCurrentIndex(mode)
                qt_app.processEvents()
                assert window.spec_copy_button.isEnabled()
                assert window.spec_save_button.isEnabled()
                spectrum = window._full_spectrum
                assert spectrum["input_domain"] == "original_float_storage"
                assert spectrum["f_range_used"] == gain
                assert spectrum["df_hz"] == pytest.approx(8192 / spectrum["n_fft"])
                assert spectrum["physical_units_verified"] is False
                _, action = window._current_original_spectrum_action()
                assert action.adc == channel
                assert action.spectrum_mode == mode
                assert not action.direct_bin_uncalibrated
                assert action.receipt()["physical_calibration_verified"] is False

                QApplication.clipboard().setText("before")
                window.spec_copy_button.click()
                copied = QApplication.clipboard().text()
                assert "\n" not in copied and len(copied.split("\t")) == 3
                assert separator in copied and ({",", "."} - {separator}).isdisjoint(copied)
                assert copied == action.clipboard_text(decimal_separator=separator)
                assert action.values[1] == pytest.approx(64.5 + channel, abs=spectrum["df_hz"])
                formatted = zip(copied.split("\t"), action.values, (3, 4, 4))
                for field, value, significant_digits in formatted:
                    parsed = float(field.replace(",", "."))
                    if value == 0:
                        assert parsed == 0
                    else:
                        exponent = floor(log10(abs(value))) - significant_digits + 1
                        assert parsed == pytest.approx(value, rel=0, abs=.51 * 10 ** exponent)

                library = tmp_path / f"export-{channel}-{mode}"
                library.mkdir()
                window.original_start_controller.set_library(library)
                daily = library / f"SPEC-FREQ-{date.today():%Y-%m-%d}.csv"
                window.spec_save_button.click()
                row = copied.replace("\t", "|") + "\r\n"
                expected = (f"sep=|\r\nСКЗ спектра, {unit}|Частота, Гц|"
                            f"Значение, {unit}\r\n" + row).encode("cp1251")
                assert daily.read_bytes() == expected
                window.spec_save_button.click()
                assert daily.read_bytes() == expected + row.encode("ascii")

        # Selecting the matching TSXML itself uses the same validated channel.
        window.open_archive(selected_sidecar)
        assert window._ch() == 8
        _, action = window._current_original_spectrum_action()
        assert not action.direct_bin_uncalibrated
    finally:
        QLocale.setDefault(previous_locale)
        window.close()
        qt_app.processEvents()


@pytest.mark.parametrize("source_kind", ["minimal", "TACH1", "TACH2"])
def test_mode1_unverified_sources_keep_marked_exports(
        tmp_path, qt_app, monkeypatch, source_kind):
    if source_kind == "minimal":
        source, _, _ = _make_pair(tmp_path)
    else:
        source, sidecar = _write_bin(tmp_path, source_kind, 8 + int(source_kind[-1]),
                               bytes((0, 255, 63, 127)) * 1024)
        sidecar.write_bytes(sidecar.read_bytes().replace(
            b"<FrequencyPerChannel>8192</FrequencyPerChannel>", b""))
    requests = []
    errors = []

    def accept(*args):
        requests.append(args[2])
        return QMessageBox.Yes

    monkeypatch.setattr(QMessageBox, "question", accept)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: pytest.fail(str(args[-1])))
    window = MainWindow()
    try:
        monkeypatch.setattr(window.original_window_man, "spawn_error", errors.append)
        window.open_archive(source)
        window.original_root_tabs.setCurrentIndex(4)
        qt_app.processEvents()
        _, action = window._current_original_spectrum_action()
        assert action.direct_bin_uncalibrated
        window.spec_copy_button.click()
        clipboard = QApplication.clipboard().text()
        assert "НЕ КАЛИБРОВАНО" in clipboard
        assert len(clipboard.splitlines()[-1].split("\t")) == 3

        blocked = tmp_path / f"SPEC-FREQ-{date.today():%Y-%m-%d}.csv"
        monkeypatch.setattr(QFileDialog, "getSaveFileName",
                            lambda *args: (str(blocked), "CSV"))
        window.spec_save_button.click()
        assert not blocked.exists()
        assert errors and "SPEC-FREQ" in errors[-1]

        marked = tmp_path / "research.csv"
        monkeypatch.setattr(QFileDialog, "getSaveFileName",
                            lambda *args: (str(marked), "CSV"))
        window.spec_save_button.click()
        assert "НЕ КАЛИБРОВАНО" in marked.read_text(encoding="utf-8")
        assert len(requests) == 3
    finally:
        window.close()
        qt_app.processEvents()


@pytest.mark.parametrize("invalid_sidecar", ["absent", "broken_xml", "wrong_size"])
def test_mode1_rejects_unusable_pairs_before_export(tmp_path, invalid_sidecar):
    source, sidecar = _adc(tmp_path, 1, "м/с2", 12.25)
    if invalid_sidecar == "absent":
        sidecar.unlink()
    elif invalid_sidecar == "broken_xml":
        sidecar.write_bytes(b"<broken>")
    else:
        source.write_bytes(source.read_bytes()[:-4])
    with pytest.raises(ValueError, match="TSXML"):
        DirectBinSession.open(source)


def test_mode1_export_tracks_time_and_applied_filter(tmp_path, qt_app, monkeypatch):
    from .test_envelope_idr_candidate import fake_profile

    source, _ = _adc(tmp_path, 4, "м/с2", 12.25, fs=65536, n=134000)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: pytest.fail(str(args[-1])))
    monkeypatch.setattr(QMessageBox, "question", lambda *args: pytest.fail(str(args[-1])))
    window = MainWindow()
    try:
        window.open_archive(source)
        window.original_root_tabs.setCurrentIndex(4)
        window.spec_n.setCurrentText("8192")
        window.spec_mode.setCurrentIndex(1)
        qt_app.processEvents()
        flow, at_end = window._current_original_spectrum_action()
        assert not at_end.direct_bin_uncalibrated
        end_window = window._full_spectrum["input_source_window"]
        bar = window.original_shell.view_slider
        bar.setValue(int(.75 * bar.maximum()))
        qt_app.processEvents()
        flow, shifted = window._current_original_spectrum_action()
        assert not shifted.direct_bin_uncalibrated
        assert window._full_spectrum["input_source_window"]["last_archive_sample_exclusive"] < (
            end_window["last_archive_sample_exclusive"])
        assert shifted.values[0] != at_end.values[0]
        with pytest.raises(ValueError, match="rendered GetSpectrum"):
            at_end.validate_flow(flow, window._full_spectrum)

        window.set_envelope_profile(fake_profile(i=.8, q=.3))
        window.spec_envelope_code.setCurrentIndex(window.spec_envelope_code.findData(31))
        window.spec_envelope_button.setChecked(True)
        qt_app.processEvents()
        flow, filtered = window._current_original_spectrum_action()
        assert not filtered.direct_bin_uncalibrated
        assert filtered.n_fft < 1024
        assert filtered.values != shifted.values
        with pytest.raises(ValueError, match="rendered GetSpectrum"):
            shifted.validate_flow(flow, window._full_spectrum)

        decimal_separator = window._source_csv_decimal()
        window.spec_copy_button.click()
        assert QApplication.clipboard().text() == filtered.clipboard_text(
            decimal_separator=decimal_separator)
        window.original_start_controller.set_library(tmp_path)
        window.spec_save_button.click()
        daily = tmp_path / f"SPEC-FREQ-{date.today():%Y-%m-%d}.csv"
        assert daily.read_bytes().split(b"\r\n")[2] == filtered.pipe_row(
            decimal_separator=decimal_separator).encode("ascii")

        bar.setValue(0)
        assert not window.spec_copy_button.isEnabled()
        assert not window.spec_save_button.isEnabled()
    finally:
        window.close()
        qt_app.processEvents()


@pytest.mark.parametrize("channel", [9,10])
def test_full_saved_tach_writes_three_count_values_and_keeps_first_daily_header(
        tmp_path,qt_app,monkeypatch,channel):
    from numpy import arange, sin, pi
    source,_=_write_bin(tmp_path,f"TACH{channel-8}",channel,
                          (127+90*sin(arange(8192)*2*pi/251)).astype("u1").tobytes())
    monkeypatch.setattr(QMessageBox,"question",lambda *_: pytest.fail("Fixed Byte metadata is verified"))
    previous=QLocale()
    w=MainWindow()
    try:
        QLocale.setDefault(QLocale("ru_RU"))
        w.open_archive(source)
        w.original_start_controller.set_library(tmp_path)
        leaf=tmp_path/f"SPEC-FREQ-{date.today():%Y-%m-%d}.csv"
        expected_header="sep=|\r\nСКЗ спектра, |Частота, Гц|Значение, \r\n".encode("cp1251")
        rows=b""
        for mode in range(4):
            w.spec_mode.setCurrentIndex(mode)
            _,action=w._current_original_spectrum_action()
            assert action.original_saved_archive_metadata
            assert action.source_units==""
            assert not action.receipt()["physical_calibration_verified"]
            w._copy_spec_summary()
            text=QApplication.clipboard().text()
            assert len(text.split("\t"))==3
            result=w._save_spec_summary()
            rows+=(text.replace("\t","|")+"\r\n").encode("ascii")
            assert leaf.read_bytes()==expected_header+rows
            assert result["retained_first_header_after_unit_change"]==(mode>=2)
    finally:
        QLocale.setDefault(previous)
        w.close()
        qt_app.processEvents()
