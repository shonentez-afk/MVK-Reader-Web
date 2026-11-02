"""Stage111Z28B1: source-derived PageStatus groups and fail-closed data gates.

The source code mapping is based on user-provided original IDR/DFM.
All measurements in these tests are synthetic, not field parity.
"""
from __future__ import annotations

import pytest

from mvk_compatible.core.offline_export import OfflineSession
from mvk_compatible.core.original_pagestatus_source import (
    MODE_NAMES, TACH_FIELDS, ALARM_FIELDS, UNAVAILABLE,
    original_alarm_rows, original_tach_fields, source_pagestatus_table,
)
from .test_stage111z28_dsp_tach_ticks import _fixture
from .test_offline_core import fixture_zip


def test_original_presentation_exact_idr_15_mode_dispatch(tmp_path):
    d=OfflineSession.open(_fixture(tmp_path)).calculations(0)
    assert len(MODE_NAMES)==15
    assert MODE_NAMES[0].startswith("0")
    assert MODE_NAMES[1].startswith("1")
    assert MODE_NAMES[2].startswith("2")
    assert MODE_NAMES[4].startswith("4")
    assert MODE_NAMES[5].startswith("5")
    assert MODE_NAMES[12].startswith("12")
    assert MODE_NAMES[13].startswith("13")
    assert MODE_NAMES[14].startswith("14")
    for mode in range(15):
        result=source_pagestatus_table(mode,d)
        assert result.index==mode
        assert result.title==MODE_NAMES[mode]
        assert len(result.rows)>0
    assert len(source_pagestatus_table(0,d).rows)==10  # DSP+8 ADC+time
    assert source_pagestatus_table(0,d).rows[0][1]=="0x00000104"


def test_original_alarm_eight_slots_three_cells_each_no_false_alarms(tmp_path):
    d=OfflineSession.open(_fixture(tmp_path)).calculations(0)
    t=source_pagestatus_table(1,d)
    assert len(ALARM_FIELDS)==3
    assert len(t.rows)==24
    assert len(t.headers)==9
    assert len(t.rows[0])==9
    assert t.rows[0][0].endswith("0x130)")
    assert t.rows[1][0].endswith("0x132)")
    assert t.rows[2][0].endswith("0x132)")
    assert t.rows[23][0].endswith("0x16A)")
    assert all(cell==UNAVAILABLE for r in t.rows for cell in r[1:])
    assert "не содержит" in t.note.lower()
    assert t.bands_for_plot is None
    # Even absent data must preserve IDR structural row titles.
    assert original_alarm_rows()==source_pagestatus_table(1,None)


def test_original_all_adc_three_modes_read_only_verified_aux(tmp_path):
    d=OfflineSession.open(_fixture(tmp_path)).calculations(0)
    for mode,key in ((2,"parameters_24"),(3,"parameters_peak_24"),
                     (4,"parameters_peak_peak_24")):
        t=source_pagestatus_table(mode,d)
        assert len(t.rows)==24
        assert len(t.headers)==9
        assert t.rows[0][0]==d["channels"][0]["parameters_24"][0]["name"]
        for ch in range(8):
            val=d["channels"][ch][key][0]["value"]
            assert t.rows[0][ch+1]==f"{val:.8g}"
        assert t.bands_for_plot is None
        assert "пик" in t.note.lower()
    d["channels"][3]["parameters_peak_24"]=None
    peak=source_pagestatus_table(3,d)
    assert all(row[4]=="—" for row in peak.rows)
    # No substitution from RMS into missing peaks!
    assert peak.rows[0][4]!=source_pagestatus_table(2,d).rows[0][4]


def test_single_adc_43_bands_source_plot_not_invented_peak(tmp_path):
    d=OfflineSession.open(_fixture(tmp_path)).calculations(0)
    for i in range(8):
        t=source_pagestatus_table(i+5,d)
        assert len(t.rows)==43
        assert t.bands_for_plot is not None
        assert len(t.bands_for_plot)==43
        assert t.rows[42][0]==d["channels"][i]["third_octave"][42]["name"]
    d["channels"][0]["third_octave"][1]["rms_m_s2"]=None
    t=source_pagestatus_table(5,d)
    assert t.bands_for_plot is None
    assert t.rows[1][1]=="—"


def test_tach_source_labels_units_vs_no_runtime_rpm(tmp_path):
    d=OfflineSession.open(_fixture(tmp_path)).calculations(0)
    fields={item[0]:item for item in TACH_FIELDS}
    assert len(TACH_FIELDS)==6
    assert fields["ResultTacho"][:4]==("ResultTacho",0x00,"Float32","Гц")
    assert fields["ResultTachoDelta"][:4]==("ResultTachoDelta",0x02,"Float32","Гц")
    assert fields["ResultTachoImpulse"][1]==0xFE
    assert fields["ResultTachoImpulse"][4] is False
    tach1=source_pagestatus_table(13,d)
    tach2=source_pagestatus_table(14,d)
    assert len(tach1.rows)==6 and len(tach2.rows)==6
    assert tach1.rows[0]==("ResultTacho","0x3000","13.25","Float32","Гц")
    assert tach1.rows[1]==("ResultTachoDelta","0x3002","22.5","Float32","Гц")
    assert tach1.rows[2][2]=="0xDEADBEEF"
    assert tach1.rows[5]==("ResultTachoImpulse","0x30FE","—","UInt32","—")
    assert tach2.rows[0]==("ResultTacho","0x3100","9.75","Float32","Гц")
    assert tach2.rows[5][1]=="0x31FE"
    assert "НЕ вычисляются" in tach1.note


def test_old_native_does_not_infer_tach_values(tmp_path):
    d=OfflineSession.open(fixture_zip(tmp_path)).calculations(0)
    t=source_pagestatus_table(13,d)
    assert len(t.rows)==6
    assert all(r[2]=="—" for r in t.rows)
    assert source_pagestatus_table(0,d).rows[0][1]=="—"


def test_unknown_value_or_selection_never_becomes_accepted_measurement(tmp_path):
    d=OfflineSession.open(_fixture(tmp_path)).calculations(0)
    for index in (-1,15,1.0,True):
        with pytest.raises(ValueError):
            source_pagestatus_table(index,d)
    with pytest.raises(ValueError):
        original_tach_fields(d["dsp_tach"],0)
    d["channels"][0]["parameters_24"][0]["value"]=True
    with pytest.raises(ValueError,match="Boolean"):
        source_pagestatus_table(2,d)
