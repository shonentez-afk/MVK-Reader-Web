"""Source-verified RU GetValueText in every live PageStatus mode.

Tests use only synthetic source PARAM DWORDs with original register
addresses. Private PAS/IDP/SQLite/CSV/PCAP are NOT copied here.
The output remains a Delphi Win32 FORMAT CANDIDATE, never original
runtime byte parity.
"""
from __future__ import annotations

import struct
import pytest

from ..core.original_live_result_registers import (
    parse_live_result_registers, source_live_status_projection,
)
from .test_mode2_original_page_status_param_banks import live_state, w, d


def test_all_14_live_mode_ru_projections_from_one_valid_source_bank():
    status=live_state()
    banks=parse_live_result_registers(status)
    assert banks is not None
    for index in range(1,15):
        projection=source_live_status_projection(
            index,banks,source_ru_text=True)
        assert projection.model.index==index
        assert "КАНДИДАТ" in projection.model.note
        assert projection.provenance.endswith("RU_GETVALUETEXT_CANDIDATE")
        assert projection.receipt()["original_delphi_pixel_parity_verified"] is False
        assert projection.source_digest is None
        assert projection.model.rows
    alarm=source_live_status_projection(1,banks,source_ru_text=True)
    assert len(alarm.model.rows)==24
    assert alarm.model.rows[0][1]=="4,5"
    assert alarm.model.rows[1][1]=="Красная зона (квитировано) (Устар. ПО)"
    assert alarm.model.rows[2][1]=="---"
    assert alarm.model.rows[1][2]=="—"  # untouched ADC 2 != healthy
    assert alarm.model.rows[2][2]=="—"  # no fabricated alarm
    rms=source_live_status_projection(2,banks,source_ru_text=True)
    assert rms.model.rows[0][0].startswith("Виброускорение, 10..3000 Гц")
    assert rms.model.rows[0][1]=="1,5"
    assert rms.model.rows[0][2]=="—"
    assert source_live_status_projection(
        3,banks,source_ru_text=True).model.rows[0][1]=="2,5"
    assert source_live_status_projection(
        4,banks,source_ru_text=True).model.rows[0][1]=="3,5"
    spec=source_live_status_projection(5,banks,source_ru_text=True)
    assert spec.chart_visible
    assert spec.model.rows[0][0].startswith("Полоса 0.63 Гц")
    assert spec.model.rows[0][1]=="0,25"
    assert spec.model.bands_for_plot[0]==0.25
    assert spec.model.bands_for_plot[-1]==10.75
    assert all(source_live_status_projection(
        i,banks,source_ru_text=True).model.rows[0][1]=="—"
               for i in range(6,13))
    tach=source_live_status_projection(13,banks,source_ru_text=True)
    assert tach.model.rows[0][0]=="Частота вращения"
    assert tach.model.rows[0][2]=="50,5"
    assert tach.model.rows[1][2]=="0,25"
    assert tach.model.rows[4][2]=="456"
    assert tach.model.rows[5][2]=="—"  # stale +FE never injected
    assert all(row[2]=="—" for row in
        source_live_status_projection(14,banks,source_ru_text=True).model.rows)


def test_alarm_state_and_alert_have_original_independent_bit_windows():
    status=live_state()
    field=status["source_live_page_status_banks"]["adc"][0][
        "control_8_status_raw_u32_le"]
    # _Unit125:00805241 calls State (Bits=8, Start=0), at 00805293
    # calls composite Alert (Bits=8, Start=8) on SAME +0x132 DWORD.
    field[0]=d(0x00000511)  # state id 17, alert ids 1|4
    banks=parse_live_result_registers(status)
    alarm=source_live_status_projection(1,banks,source_ru_text=True)
    assert alarm.model.rows[1][1]=="Зеленая зона"
    assert alarm.model.rows[2][1]==(
        "Ошибка датчика (Устар. ПО); Переход в желтую зону")
    field[0]=d(0x000008FE)  # unmapped state ID FE, Alert id 8
    banks=parse_live_result_registers(status)
    alarm=source_live_status_projection(1,banks,source_ru_text=True)
    assert alarm.model.rows[1][1]=="(0x000000FE)"
    assert alarm.model.rows[2][1]=="Переход в красную зону"
    field[0]=None
    banks=parse_live_result_registers(status)
    alarm=source_live_status_projection(1,banks,source_ru_text=True)
    assert alarm.model.rows[1][1]=="—"
    assert alarm.model.rows[2][1]=="—"


def test_nonfinite_and_incomplete_param_dword_never_show_success():
    status=live_state()
    adc=status["source_live_page_status_banks"]["adc"][0]
    adc["control_8_values_raw_f32_le"][0]=d(0x7FC00000)
    adc["bands_43_raw_f32_le"][0]=d(0x7F800000)
    banks=parse_live_result_registers(status)
    alarm=source_live_status_projection(1,banks,source_ru_text=True)
    assert alarm.model.rows[0][1]=="—"
    third=source_live_status_projection(5,banks,source_ru_text=True)
    assert third.model.rows[0][1]=="—"
    assert not third.chart_visible


def test_ru_presentation_explicit_opt_in_keeps_original_raw_audit_intact():
    banks=parse_live_result_registers(live_state())
    raw=source_live_status_projection(1,banks)
    ru=source_live_status_projection(1,banks,source_ru_text=True)
    assert raw.model.rows[1][1]=="0x00000003 (RAW)"
    assert ru.model.rows[1][1]!="0x00000003 (RAW)"
    assert "НЕ исходный TMvkCellList.GetValueText" in raw.model.note
    assert "КАНДИДАТ" in ru.model.note
    with pytest.raises(ValueError,match="Boolean"):
        source_live_status_projection(1,banks,source_ru_text="ru-ru")
