"""Stage111Z31BJ: one source-backed File/Signal/Spectrum/Status workbench.

This is the view model shared by the visible original PageFile and
existing signal, spectrum and results pages. It consumes ONLY the
validated OfflineMeasurementFlow and, optionally, a fresh MVK_DSP
snapshot for this exact session/channel/tick. It never synthesizes
instrument SPEC/AUX/VALUES from standalone BIN/TSXML or changes DSP.

No Qt, filesystem writes, device commands, clock assumptions or
private original assets.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .offline_measurement_flow import OfflineMeasurementFlow

SOURCE = "MVK_ORIGINAL_FILE_WORKBENCH_STAGE111Z31BJ"
UNAVAILABLE = "—"


@dataclass(frozen=True)
class FileWorkbench:
    source_kind: str
    selected_channel: int
    available_channels: tuple[int, ...]
    source_basename: str
    sample_count: int
    sample_rate_hz: float
    bin_sha256: str
    metadata: tuple[tuple[str, str], ...]
    spectrum_rows: tuple[str, ...]
    value_rows: tuple[str, ...]
    source_note: str
    dsp_verified_for_selection: bool
    original_runtime_parity_verified: bool = False
    device_action_allowed: bool = False

    def report(self):
        return {
            "source": SOURCE,
            "measurement_kind": self.source_kind,
            "channel": self.selected_channel,
            "channels": list(self.available_channels),
            "samples": self.sample_count,
            "sample_rate_hz": self.sample_rate_hz,
            "spectrum_rows": len(self.spectrum_rows),
            "values_rows": len(self.value_rows),
            "dsp_verified_for_selection": self.dsp_verified_for_selection,
            "original_runtime_parity_verified": False,
            "device_action_allowed": False,
        }


def _number(value) -> str:
    if value is None:
        return UNAVAILABLE
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("DSP numerical field must be numeric or absent")
    if not math.isfinite(float(value)):
        raise ValueError("Non-finite DSP field cannot appear in source UI")
    return f"{value:.8g}"


def source_file_workbench(
    flow: OfflineMeasurementFlow, *,
    verified_status: dict | None = None,
) -> FileWorkbench:
    if not isinstance(flow, OfflineMeasurementFlow):
        raise ValueError("Expected one bound offline measurement flow")
    source = flow.source_record()  # checks source bytes/hash and ADC
    selected = source["selected_channel"]
    channels = tuple(source["available_channels"])
    if selected != flow.channel or selected not in channels:
        raise ValueError("File UI channel differs from authoritative Core")
    direct = flow.direct_bin
    if direct and verified_status is not None:
        raise ValueError("A standalone BIN never has authenticated DSP/AUX")
    if verified_status is not None:
        if (not isinstance(verified_status, dict)
                or verified_status.get("source") != "MVK_DSP"
                or verified_status.get("serial") != flow.session.serial
                or verified_status.get("tick") != flow.tick_index):
            raise ValueError("DSP snapshot is not from the selected session/tick")
        banks = verified_status.get("channels")
        if (not isinstance(banks, list) or len(banks) != 8
                or any(not isinstance(bank, dict) or
                       bank.get("channel") != i
                       for i, bank in enumerate(banks, 1))):
            raise ValueError("Source DSP channel banks are incomplete")
        active = banks[selected - 1]
        measures = active.get("parameters_24")
        bands = active.get("third_octave")
        if (not isinstance(measures, list) or len(measures) != 24
                or not isinstance(bands, list) or len(bands) != 43):
            raise ValueError("Original 24-value/43-band banks are not present")
        peaks = active.get("parameters_peak_24")
        pp = active.get("parameters_peak_peak_24")
        if peaks is not None and (not isinstance(peaks, list) or len(peaks) != 24):
            raise ValueError("Incomplete peak bank")
        if pp is not None and (not isinstance(pp, list) or len(pp) != 24):
            raise ValueError("Incomplete peak-to-peak bank")
        value_rows = []
        for i, item in enumerate(measures):
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise ValueError("Invalid original DSP measurement label")
            unit = item.get("unit", "")
            if not isinstance(unit, str):
                raise ValueError("Original DSP unit must be text")
            rms = _number(item.get("value"))
            peak = _number(peaks[i].get("value")) if peaks is not None else UNAVAILABLE
            peak_peak = _number(pp[i].get("value")) if pp is not None else UNAVAILABLE
            value_rows.append(
                f"{i+1:02d} · {item['name']} · СКЗ {rms}"
                f" · ПИК {peak} · ПИК-ПИК {peak_peak} {unit}".rstrip()
            )
        spectrum_rows = []
        for i, band in enumerate(bands):
            if not isinstance(band, dict) or not isinstance(band.get("name"), str):
                raise ValueError("Invalid original DSP octave label")
            spectrum_rows.append(
                f"{i+1:02d} · {band['name']} · "
                f"{_number(band.get('rms_m_s2'))} м/с²"
            )
        note = ("Проверенный Native R6.1 VALUES/AUX, "
                f"АЦП{selected}, обновление {flow.tick_index+1}/"
                f"{flow.session.updates}; не доказательство 1:1 MVKView")
    else:
        value_rows = ["Нет подтверждённых приборных VALUES/AUX для этого выбора"]
        spectrum_rows = [
            "Приборный SPEC не подтверждён; расчётный FFT доступен на странице «Спектр»"
        ]
        note = (
            "BIN/TSXML: только реальные Single; нет аппаратных VALUES/AUX, "
            "DSP, третьоктав и физически подтверждённой калибровки"
            if direct else
            "Native ZIP: текущие VALUES/AUX пока не приняты; "
            "старые результаты не показываются"
        )
    samples = source["sample_count"]
    rate = source["sample_rate_hz"]
    if (type(samples) is not int or samples <= 0
            or not isinstance(rate, (int, float)) or not math.isfinite(rate)
            or rate <= 0):
        raise ValueError("Unverified signal length/rate")
    meta = (
        ("Имя исходного файла", source["data_file_label"]),
        ("Источник", "BIN/TSXML Single" if direct else "Native R6.1 ZIP"),
        ("Прибор", source["serial"]),
        ("Выбранный канал", f"АЦП{selected}"),
        ("Число отсчётов Single", str(samples)),
        ("Частота дискретизации", f"{rate:g} Гц"),
        ("Длительность сигнала", f"{samples/rate:.6g} с"),
        ("SHA256 источника BIN", source["source_bin_sha256"]),
        ("DSP VALUES/AUX", "проверены для этого тика" if verified_status else "нет"),
        ("Тик VALUES", UNAVAILABLE if direct else
         f"{flow.tick_index+1}/{flow.session.updates}"),
        ("Оригинальный расчёт/графика 1:1", "НЕ подтверждены"),
    )
    return FileWorkbench(
        source_kind=source["measurement_kind"], selected_channel=selected,
        available_channels=channels,
        source_basename=source["data_file_label"],
        sample_count=samples, sample_rate_hz=float(rate),
        bin_sha256=source["source_bin_sha256"], metadata=meta,
        spectrum_rows=tuple(spectrum_rows), value_rows=tuple(value_rows),
        source_note=note, dsp_verified_for_selection=verified_status is not None,
    )
