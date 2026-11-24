"""LIVE PageStatus operator projection from one accepted PARAM snapshot.

_Unit128:0084779C..008479F8 = RESULT6 + selected BAND24 + TACH6.
008479FD..00847D53 = SpecSeries43 + RESULT6 + three BAND24 columns.
00847D58..00847E4A = TACH6. 008475E8..008475EF = FreezeUpdate.
_Unit125:00804A30/00804DEC/008053B8 define the corresponding lists.
No local FFT, guessed register, device command or Delphi runtime attestation.
The older RAW/diagnostic projection is intentionally kept separate.
"""
from __future__ import annotations

from copy import deepcopy

from .original_connected_status import connected_system_status
from .original_live_result_registers import (
    SCHEMA, _raw_f32, source_live_status_projection,
)
from .original_pagestatus_source import MODE_NAMES, StatusTable, UNAVAILABLE
from .original_status_workbench import MODE_GRID, OriginalStatusProjection
from .original_ru_csv_layout import source_ru_cell_title, source_ru_typed_text
from .original_get_value_text_30 import live_get_units

SOURCE = "SOURCE_LIVE_OPERATOR_PAGESTATUS_LAYOUT_STAGE111Z31EA"
BAND_BANKS = ("rms_24_raw_f32_le", "peak_24_raw_f32_le",
              "peak_peak_24_raw_f32_le")
RESULT_BANK = "result_adc_six_raw_dwords_le"
TACH_BANK = "source_field_0_2_4_6_8_fe_raw_le"


def _text(group, index, word):
    if word is None:
        return UNAVAILABLE
    is_float = (group in ("BAND", "SPEC")
                or group == "RESULT" and index >= 3
                or group == "TACH" and index < 2)
    if is_float and _raw_f32(word) is None:
        return UNAVAILABLE
    value = source_ru_typed_text(group, index, word)
    return UNAVAILABLE if value == "UNKNOWN" else value


def _result_word(adc, index):
    words = adc.get(RESULT_BANK, (None,)*6)
    word = words[index]
    # Original first three Advanced cells read exactly the same complete
    # +0x120 DWORD. The old Go schema exposed this word independently.
    if index < 3 and word is None:
        return adc.get("sensor_status_raw_u32_le")
    return word


def _empty_bank():
    # Presentation-only placeholders. This is not a verified PARAM bank.
    return {
        "schema": SCHEMA,
        "known_complete_dwords": 0,
        "adc": tuple({
            "bands_43_raw_f32_le": (None,)*43,
            **{key: (None,)*24 for key in BAND_BANKS},
            RESULT_BANK: (None,)*6,
            "sensor_status_raw_u32_le": None,
            "control_8_values_raw_f32_le": (None,)*8,
            "control_8_status_raw_u32_le": (None,)*8,
        } for _ in range(8)),
        "tach": tuple({TACH_BANK: (None,)*6} for _ in range(2)),
    }


def source_live_operator_status_projection(mode: int,
                                           banks: dict | None):
    """Four real grids. A 43-band chart is NOT the 30-row ADC table.

    Missing data leave exactly the same operator layout; empty cells in
    inapplicable columns differ from unavailable register values.
    """
    if type(mode) is not int or not 1 <= mode <= 14:
        raise ValueError("LIVE operator PageStatus requires modes 1..14")
    known = banks is not None
    if known and (not isinstance(banks, dict) or banks.get("schema") != SCHEMA
                  or len(banks["adc"]) != 8 or len(banks["tach"]) != 2):
        raise ValueError("LIVE operator PageStatus requires validated 8 ADC + 2 TACH")
    b = banks if known else _empty_bank()
    adcs, tachs = b["adc"], b["tach"]
    chart = None
    if mode == 1:
        raw = source_live_status_projection(1, b, source_ru_text=True)
        headers, rows = raw.model.headers, raw.model.rows
    elif 2 <= mode <= 4:
        headers = ("Наименование параметра", *(f"АЦП {i}" for i in range(1,9)),
                   "Тахометр 1", "Тахометр 2", "Ед. изм.")
        rows = []
        for i in range(6):
            rows.append((source_ru_cell_title("RESULT", i),
                         *(_text("RESULT", i, _result_word(a, i)) for a in adcs),
                         "", "", live_get_units("RESULT", i)))
        bank_key = BAND_BANKS[mode-2]
        for i in range(24):
            rows.append((source_ru_cell_title("BAND", i),
                         *(_text("BAND", i, a[bank_key][i]) for a in adcs),
                         "", "", live_get_units("BAND", i)))
        for i in range(6):
            rows.append((source_ru_cell_title("TACH", i), *("",)*8,
                         *(_text("TACH", i, t[TACH_BANK][i]) for t in tachs),
                         live_get_units("TACH", i)))
    elif 5 <= mode <= 12:
        adc = adcs[mode-5]
        headers = ("Наименование параметра", "СКЗ", "Пик", "Пик-пик", "Ед. изм.")
        rows = []
        for i in range(6):
            rows.append((source_ru_cell_title("RESULT", i),
                         _text("RESULT", i, _result_word(adc, i)),
                         "", "", live_get_units("RESULT", i)))
        for i in range(24):
            rows.append((source_ru_cell_title("BAND", i),
                         *(_text("BAND", i, adc[key][i]) for key in BAND_BANKS),
                         live_get_units("BAND", i)))
        values = tuple(_raw_f32(word) for word in adc["bands_43_raw_f32_le"])
        # Preserve the existing fail-closed all-43 rule; never turn
        # missing PARAM data into zero-valued bars or local FFT.
        if known and all(value is not None for value in values):
            chart = values
    else:
        # Original tabResult is initialized with five columns at
        # 008453C1; the TACH branch writes only col1 and the units col4.
        headers = ("Наименование параметра", "Значение", "", "", "Ед. изм.")
        tach = tachs[mode-13]
        rows = [(source_ru_cell_title("TACH", i),
                 _text("TACH", i, tach[TACH_BANK][i]),
                 "", "", live_get_units("TACH", i)) for i in range(6)]

    note = (
        "LIVE · принятые PARAM-регистры текущего сеанса. "
        "Структура списков RESULT6 / BAND24 / SPEC43 / TACH6 восстановлена; "
        "GetValueText — КАНДИДАТ исходного Delphi/Win32. "
        "Пропуски — «—», локальный FFT не подставляется."
        if known else
        "Ожидание подтверждённых PARAM-регистров текущего измерения. "
        "Структура таблицы сохранена; значения не подставляются.")
    model = StatusTable(mode, MODE_NAMES[mode], tuple(headers), tuple(rows),
                        note, chart, SOURCE)
    return OriginalStatusProjection(
        model, MODE_GRID[mode], chart is not None, None, None, None,
        provenance=(SOURCE if known else "SOURCE_LIVE_OPERATOR_UNAVAILABLE"))


class LivePageStatusBinding:
    """One current source snapshot for the whole original tcStatus.

    Accepted snapshots are copied once, not on each 20 ms paint dispatch.
    Freeze holds the last accepted snapshot even on a mode change. Fault,
    Stop or a different socket/session always invalidate held data.
    This adapter never decides whether Go actually sent a device command.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.identity = None
        self.snapshot = None
        self._observed = None
        self._accepted_param_frames = None
        self.paused = False

    def select(self, status, *, active, stop_requested, source_fault,
               freeze_requested, expected_session_id=None):
        if not active:
            self.reset()
            return None
        if status is None or not isinstance(status, dict):
            self.snapshot = self._observed = None
            self.paused = False
            return None
        identity = (status.get("session_id"),
                    status.get("source_tcp_connection_count", 0))
        if self.identity != identity:
            self.reset()
            self.identity = identity
        try:
            health = connected_system_status(status)
        except (ValueError, TypeError, KeyError):
            health = None
        if (stop_requested or source_fault
                or expected_session_id is not None
                and identity[0] != expected_session_id
                or health is None or not health.connection_verified
                or health.data_integrity_alert
                or status.get("source_tcp_multi_socket") is True):
            self.snapshot = self._observed = None
            self.paused = False
            return None
        gate = (status.get("source_original_receive_gate")
                if status.get("source_original_receive_gate_verified") is True
                else None)
        self.paused = bool(freeze_requested or
                           isinstance(gate, dict) and gate.get("freeze_update") is True)
        if self.paused:
            return self.snapshot
        banks = (status.get("source_live_page_status_banks")
                 if status.get("source_live_page_status_banks_verified") is True
                 else None)
        if banks is not None:
            frames = banks.get("accepted_param_frames")
            if (not isinstance(identity[0], str) or not identity[0]
                    or banks.get("schema") != SCHEMA
                    or banks.get("tcp_connection_count") != identity[1]
                    or type(frames) is not int or frames < 0
                    or self._accepted_param_frames is not None
                    and frames < self._accepted_param_frames):
                self.snapshot = self._observed = None
                return None
            self._accepted_param_frames = frames
        if status is not self._observed:
            self.snapshot = deepcopy(status)
            self._observed = status
        return self.snapshot

    @property
    def banks(self):
        s = self.snapshot
        if (s is None or s.get("capture_only") is True
                or s.get("source_live_page_status_banks_verified") is not True):
            return None
        return s.get("source_live_page_status_banks")

    def receipt(self):
        b = self.banks
        if b is None or self.identity is None:
            return None
        return {
            "source_session_id": self.identity[0],
            "source_tcp_connection_count": self.identity[1],
            "accepted_param_frames": b["accepted_param_frames"],
            "known_complete_dwords": b["known_complete_dwords"],
            "display_frozen": self.paused,
            "source_original_operator_layout": True,
            "original_delphi_runtime_verified": False,
        }
