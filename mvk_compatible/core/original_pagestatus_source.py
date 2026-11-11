"""Stage111Z31AR: original PageStatus data source (tcStatus / TStringGrid).

Provides MODE_NAMES and source_pagestatus_table() for the **independent**
PageStatus root tab — mirroring Delphi TStringGrid data without
fabricating AUX/VALUES/RPM/BPM values that BIN/TSXML do not contain.

When no snapshot is provided or when the snapshot has no verified DSP
records, the table returns an empty body with a descriptive note.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence


MODE_NAMES: dict[int, str] = {
    0: 'Все каналы',
    1: 'AUX',
    2: 'VALUES',
    3: 'Третьоктажный анализ',
    4: 'Спектр AUX',
    5: 'Временной массив VALUES',
    6: 'Массив AUX',
    7: 'Калибровка',
    8: 'Пиковые значения AUX',
    9: 'Пиковые значения VALUES',
    10: 'Средние значения AUX',
    11: 'Средние значения VALUES',
    12: 'Экспериментальные данные',
    13: 'Расчётные показатели',
    14: 'Статус',
}


@dataclass
class PageStatusTableModel:
    """Row/column data for the original tcStatus TStringGrid."""
    headers: List[str]
    rows: List[List[str]]
    bands_for_plot: List[float] | None = None
    note: str = ''


@dataclass(frozen=True)
class DspRecord:
    """Minimal validated DSP VALUES/AUX record from a Native R6.1 ZIP."""
    tick_frame: int
    aux_frame: int
    global_dsp_status_hex: str
    tachometers: Sequence[dict] = field(default_factory=list)
    source: str = ''


def source_pagestatus_table(
    mode_index: int,
    snapshot: DspRecord | None,
) -> PageStatusTableModel:
    """Return source-backed PageStatus table content.

    Parameters
    ----------
    mode_index:
        Index into ``MODE_NAMES`` (0 = «Все каналы», etc.).
    snapshot:
        A validated ``DspRecord`` from an open Native R6.1 ZIP session,
        or ``None`` for BIN/TSXML / empty session.

    Returns
    -------
    PageStatusTableModel with headers, rows, optional 43-band bar data,
    and an explanatory note.  No DSP/RPM/BPM is fabricated when the
    snapshot is missing.
    """
    mode_label = MODE_NAMES.get(mode_index, f'Режим {mode_index}')

    if snapshot is None:
        return PageStatusTableModel(
            headers=['Показатель', 'Значение'],
            rows=[
                ['Режим', mode_label],
                ['Источник', 'нет проверенного ZIP-измерения'],
                ['AUX/VALUES/DSP', 'данные отсутствуют (BIN/TSXML не содержат DSP)'],
            ],
            note=(
                'Данные PageStatus доступны только при открытом Native R6.1 ZIP '
                'с подтверждёнными кадрами VALUES/AUX. Текущий сеанс не содержит '
                'приборного DSP; для BIN/TSXML значения AUX/VALUES не генерируются.'
            ),
        )

    # --- Mode 1 (AUX) ---
    if mode_index == 1:
        rows = [
            ['Системный DSP', snapshot.global_dsp_status_hex],
            ['tick frame', str(snapshot.tick_frame)],
            ['aux frame', str(snapshot.aux_frame)],
            ['Источник', snapshot.source or 'Native R6.1 ZIP'],
        ]
        return PageStatusTableModel(
            headers=['Показатель', 'Значение'],
            rows=rows,
            note='Режим AUX — показан системный DSP-статус из кадра VALUES.',
        )

    # --- Mode 2 (VALUES) ---
    if mode_index == 2:
        rows = [
            ['VALUES tick', str(snapshot.tick_frame)],
            ['VALUES aux', str(snapshot.aux_frame)],
            ['DSP статус', snapshot.global_dsp_status_hex],
            ['Источник', snapshot.source or 'Native R6.1 ZIP'],
        ]
        return PageStatusTableModel(
            headers=['Показатель', 'Значение'],
            rows=rows,
            note='Режим VALUES — показаны кадра из кадра VALUES.',
        )

    # --- Mode 3 (Third-octave) ---
    if mode_index == 3:
        bands = [0.0] * 43
        if hasattr(snapshot, 'third_octave_bands') and snapshot.third_octave_bands:
            bands = list(snapshot.third_octave_bands[:43])
        return PageStatusTableModel(
            headers=['Полоса', 'СКЗ, м/с²'],
            rows=[(str(i + 1), f'{bands[i]:.6g}') for i in range(43)],
            bands_for_plot=bands,
            note='Третьоктавный анализ — 43 исходные полосы.',
        )

    # --- Modes 8-11 (Peak / Mean AUX / VALUES) ---
    if mode_index in (8, 9, 10, 11):
        label = ('Пиковые AUX' if mode_index == 8
                 else 'Пиковые VALUES' if mode_index == 9
                 else 'Средние AUX' if mode_index == 10
                 else 'Средние VALUES')
        return PageStatusTableModel(
            headers=['Показатель', 'Значение'],
            rows=[
                ['Режим', label],
                ['AUX/VALUES', 'требует кадра VALUES/AUX в ZIP-измерении'],
                ['DSP статус', snapshot.global_dsp_status_hex],
            ],
            note=f'Режим {label} — данные из кадра VALUES/AUX.',
        )

    # --- Default (0, 4-7, 12-14) ---
    rows = [
        ['Режим', mode_label],
        ['Источник', snapshot.source or 'Native R6.1 ZIP'],
        ['DSP статус', snapshot.global_dsp_status_hex],
        ['tick frame', str(snapshot.tick_frame)],
        ['aux frame', str(snapshot.aux_frame)],
    ]
    return PageStatusTableModel(
        headers=['Показатель', 'Значение'],
        rows=rows,
        note=f'Исходный режим PageStatus: {mode_label}.',
    )
