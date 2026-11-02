"""Stage111Z28B1: IDR source mapping for original PageStatus display.

SOURCE-VERIFIED construction and dispatch, not original runtime/pixel parity:
_Unit128:0x008475F5 switches tcStatus: 0=system, 1=alarm,
2..4=all ADC values by three result banks, 5..12=one ADC+43 band chart,
13..14=one TACH. _Unit125:0x008053B8 builds each TACH field.
_Unit125:0x00805178 constructs 8 slots * (value/state/alert) per ADC.

Only independently audited AUX/VALUES and Stage28A source TACH registers
may appear numerically. Incomplete control-slot blocks do NOT appear in
AUX4700 (0x122 words), so alarms must remain UNKNOWN. No RPM conversion.
No network, original binary, or firmware code is embedded in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TACH_FIELDS = (
    # label (source localization key), relative register word, field type,
    # unit originally supplied to TMvkCellList.Add, available in VALUES tick
    ("ResultTacho", 0x00, "Float32", "Гц", True),
    ("ResultTachoDelta", 0x02, "Float32", "Гц", True),
    ("ResultTachoError", 0x04, "UInt32", "", True),
    ("ResultTachoTimestamp", 0x06, "UInt32", "", True),
    ("ResultTachoCurrent", 0x08, "UInt32", "", True),
    ("ResultTachoImpulse", 0xFE, "UInt32", "", False),
)
ALARM_FIELDS = (
    ("AlarmValue", 0x00, "Float32"),
    ("AlarmState", 0x02, "UInt32"),
    ("AlarmAlert", 0x02, "UInt32"),
)
MODE_NAMES = (
    "0 · Система",
    "1 · Контрольные зоны, 8 АЦП",
    "2 · Все АЦП · СКЗ",
    "3 · Все АЦП · ПИК",
    "4 · Все АЦП · ПИК-ПИК",
    *(f"{5+i} · АЦП {i+1} · 43 полосы" for i in range(8)),
    "13 · Тахоканал 1",
    "14 · Тахоканал 2",
)
UNAVAILABLE = "—"


@dataclass(frozen=True)
class StatusTable:
    index: int
    title: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    note: str
    bands_for_plot: tuple[float, ...] | None = None
    provenance: str = "SOURCE_DISPATCH_WITH_AUDITED_NATIVE_VALUES_NOT_RUNTIME_PARITY"


def original_tach_fields(record: dict, tach: int) -> StatusTable:
    if tach not in (1, 2):
        raise ValueError("Original source has exactly two TACH result lists")
    mode = 12+tach
    available = bool(record.get("available"))
    entries = record.get("tachometers", []) if available else []
    if available and (len(entries)!=2 or entries[tach-1].get("tach")!=tach):
        raise ValueError("TACH results are not mapped to the declared source bank")
    observed = entries[tach-1] if available else None
    values = (
        [*observed["raw_float32_words_0_2"],
         *observed["raw_uint32_words_4_6_8"]] if observed else []
    )
    rows = []
    for n,(key,offset,kind,unit,fresh_tick) in enumerate(TACH_FIELDS):
        # Original 0xFE "impulse" is absent in short 76B tick updates and
        # must never be taken from a stale initial full register snapshot.
        value = values[n] if observed and fresh_tick else None
        displayed = (
            format(value,".9g") if kind=="Float32" else f"0x{value:08X}"
        ) if value is not None else UNAVAILABLE
        rows.append((key, f"0x{0x3000+(tach-1)*0x100+offset:04X}",
                     displayed, kind, unit or UNAVAILABLE))
    return StatusTable(
        mode, MODE_NAMES[mode],
        ("Оригинальный ключ","Регистр","RAW значение","Формат","Ед. по IDR"),
        tuple(rows),
        "TACH: подписи ResultTacho и ResultTachoDelta имеют «Гц» в "
        "исходном конструкторе _Unit125:008053B8. Это лишь статическое "
        "подтверждение ЕДИНИЦЫ И ПОДПИСИ, не аппаратное совпадение частоты; "
        "об/мин НЕ вычисляются. +0xFE импульсы отсутствуют в 76B VALUES тике.",
    )


def original_alarm_rows() -> StatusTable:
    rows = []
    for j in range(8):
        for key,offset,_kind in ALARM_FIELDS:
            # Stage65: per-channel source base 0x2000+ADC*0x200,
            # source slot +0x130+8*j. +0x132 is same status WORD
            # rendered two ways (zone and event) by original advanced cells.
            relative = 0x130+8*j+offset
            rows.append((f"Контроль {j+1} · {key} (отн. 0x{relative:03X})",
                         *(UNAVAILABLE for _ in range(8))))
    return StatusTable(
        1, MODE_NAMES[1], ("Оригинальная ячейка",*(f"АЦП{i}" for i in range(1,9))),
        tuple(rows),
        "Источник _Unit125:00805178 / _Unit128:008476B7: 8 контрольных "
        "слотов × три ячейки на каждый из 8 АЦП. Состояние и событие "
        "читают один DWORD +0x132 с разными интерпретаторами. "
        "ВАЖНО: AUX4700 заканчивается на +0x121 и НЕ содержит контрольные "
        "регистры +0x130; источник номера контролируемого параметра и "
        "порогов находится отдельно в конфигурации. Все значения намеренно "
        "оставлены неизвестными; ложных «Норма/Тревога» нет.",
    )


def _text(x: Any) -> str:
    if x is None:
        return UNAVAILABLE
    if isinstance(x,bool):
        raise ValueError("Boolean is not an original DSP numeric measurement")
    if isinstance(x,float):
        from math import isfinite
        if not isfinite(x):
            raise ValueError("Non-finite original DSP value")
        return f"{x:.8g}"
    return str(x)


def source_pagestatus_table(index: int, calculated: dict | None) -> StatusTable:
    if type(index) is not int or not 0 <= index <= 14:
        raise ValueError("Original tcStatus dispatch index must be 0..14")
    if index==1:
        return original_alarm_rows()
    if calculated is None:
        return StatusTable(
            index,MODE_NAMES[index],("Поле","Значение"),
            (("Источник",UNAVAILABLE),),
            "Нет подтверждённого AUX/VALUES/TIMELINE для данной записи; "
            "нельзя подставлять сигнал, RPM или «исправен».")
    channels=calculated.get("channels")
    if not isinstance(channels,list) or len(channels)!=8:
        raise ValueError("An original PageStatus source snapshot needs 8 ADC")
    system=calculated.get("dsp_tach",{})
    if index==0:
        rows=[("Системный DSP (0x1020)",
               system.get("global_dsp_status_hex") if system.get("available") else UNAVAILABLE)]
        for ch,entry in enumerate(channels,1):
            rows.append((f"АЦП{ch} · состояние датчика",_text(entry.get("sensor_status"))))
        rows.append(("Источник времени",str(calculated.get("time_kind","HOST_CLOCK_VALUES"))))
        return StatusTable(index,MODE_NAMES[index],("Состояние","Исходное значение"),
                           tuple((str(a),str(b)) for a,b in rows),
                           "Source _Unit128:0084761A reads tabStatus/status cell list. "
                           "Статус 0x00000000 означает только нулевые биты, "
                           "не доказательство исправности системы.")
    if 2<=index<=4:
        key=("parameters_24","parameters_peak_24","parameters_peak_peak_24")[index-2]
        rows=[]
        for n in range(24):
            name=channels[0]["parameters_24"][n]["name"]
            vals=[]
            for ch in channels:
                section=ch.get(key)
                if section is not None and len(section)!=24:
                    raise ValueError("Invalid source DSP 24-value result bank")
                vals.append(_text(section[n]["value"]) if section else UNAVAILABLE)
            rows.append((name,*vals))
        return StatusTable(
            index,MODE_NAMES[index],
            ("Измеренная полоса",*(f"АЦП{i}" for i in range(1,9))),
            tuple(rows),
            "Source dispatch _Unit128:0084779C → tabAllResult: 8 АЦП, "
            "3 исходных указателя результата по индексам 2–4. "
            "Здесь показаны уже подтверждённые AUX/VALUES RMS/ПИК/ПИК-ПИК; "
            "точный original text/column order и pixel parity открыты. "
            "Отсутствующий peak не подменяется RMS.",
        )
    if 5<=index<=12:
        ch=channels[index-5]
        bands=ch["third_octave"]
        if len(bands)!=43:
            raise ValueError("Original 43-band record is missing")
        values=tuple(float(b["rms_m_s2"]) for b in bands
                     if b.get("rms_m_s2") is not None)
        plot=values if len(values)==43 else None
        rows=tuple((str(b["name"]),_text(b.get("rms_m_s2")))
                   for b in bands)
        return StatusTable(
            index,MODE_NAMES[index],("Источник 43 полос","СКЗ, м/с²"),
            rows,
            "Source _Unit128:008479FD: original tabResult + chResult "
            "использует 43 последовательные полосы и выбранный АЦП. "
            "Масштаб/цвета/bar geometry оригинала пока не аттестованы.",
            plot,
        )
    return original_tach_fields(system,index-12)
