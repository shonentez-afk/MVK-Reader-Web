"""Stage111Z.18 — uncalibrated local CSV never masquerades as DSP."""
from __future__ import annotations

from pathlib import Path

import pytest

from mvk_compatible.core.spectrum_summary_export_candidate import (
    RESEARCH_HEADER,RESEARCH_UNCALIBRATED_HEADER,
    append_research_summary_csv,
)

GOLDEN_FAKE={
    "source":"APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE",
    "output_mean":6.892500877380371,
    "output_peak_frequency_hz":3800.036376953125,
    "output_peak_y":0.7786021828651428,
}


def test_uncalibrated_export_explicit_header_no_implicit_original_claim(tmp_path):
    path=tmp_path/"direct.csv"
    result=append_research_summary_csv(path,GOLDEN_FAKE,uncalibrated=True)
    lines=path.read_text(encoding="utf-8").splitlines()
    assert lines[0]=="sep=|"
    assert lines[1]==RESEARCH_UNCALIBRATED_HEADER
    assert "НЕ КАЛИБРОВАНО" in lines[1]
    assert lines[-1]=="6,89|3800|0,7786"
    assert result["uncalibrated_source_declared"] is True
    assert result["physical_units_verified"] is False
    assert result["original_delphi_export_format_verified"] is False
    append_research_summary_csv(path,GOLDEN_FAKE,uncalibrated=True)
    assert path.read_text(encoding="utf-8").splitlines().count(lines[-1])==2


def test_uncalibrated_and_ordinary_candidate_cannot_mix_in_existing_csv(tmp_path):
    uncalibrated=tmp_path/"u.csv"
    standard=tmp_path/"s.csv"
    append_research_summary_csv(uncalibrated,GOLDEN_FAKE,uncalibrated=True)
    append_research_summary_csv(standard,GOLDEN_FAKE)
    assert RESEARCH_HEADER in standard.read_text(encoding="utf-8")
    assert RESEARCH_UNCALIBRATED_HEADER not in standard.read_text(encoding="utf-8")
    with pytest.raises(ValueError,match="Refuse to append"):
        append_research_summary_csv(uncalibrated,GOLDEN_FAKE)
    with pytest.raises(ValueError,match="Refuse to append"):
        append_research_summary_csv(standard,GOLDEN_FAKE,uncalibrated=True)


@pytest.mark.parametrize("invalid",[None,0,1,"yes",[],{}])
def test_uncalibrated_flag_must_be_explicit_bool(tmp_path,invalid):
    with pytest.raises(ValueError,match="explicit boolean"):
        append_research_summary_csv(tmp_path/"invalid.csv",GOLDEN_FAKE,uncalibrated=invalid)
