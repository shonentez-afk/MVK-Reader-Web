"""Stage111Z.11 synthetic-only original Copy text comparison QA.

The original user's clipboard has NOT been supplied. All text fixtures here
are fabricated using candidate formatter and are NOT original Delphi golden.
"""
from __future__ import annotations

import json
import struct

import numpy as np
import pytest

from mvk_compatible.core.spectrum_summary_export_candidate import spectrum_triplet_text
from mvk_compatible.private_spectrum_copy_runtime_compare import (
    SOURCE, compare_original_copy_text,
)
from mvk_compatible.private_getspectrum_summary_triplet_compare import SCHEMA


def _bits(value: float) -> str:
    data = struct.pack("<f", float(np.float32(value)))
    return "0x" + f"{struct.unpack('<I',data)[0]:08X}"


def _synthetic_manifest(tmp_path, *, decimal=",", encoding="utf-8-sig"):
    n=1024
    fs=32768
    triplet={"output_mean":1.25, "output_peak_x_bin":100.375,
             "output_peak_y":0.875}
    manifest={
        "schema":SCHEMA,
        "summary_power_stop_va":"0x007D17E7",
        "summary_fields_stop_va":"0x007D1900",
        "fft_n":n,
        "sample_rate_hz":fs,
        "spectrum_mode":1,
        "f_range_bits":_bits(510.565),
        "summary_power_file":"synthetic_power.bin",
        "output_mean_bits":_bits(triplet["output_mean"]),
        "output_peak_x_bits":_bits(triplet["output_peak_x_bin"]),
        "output_peak_y_bits":_bits(triplet["output_peak_y"]),
    }
    mp=tmp_path/"summary_capture.json"
    mp.write_text(json.dumps(manifest),encoding="utf-8")
    summary={
        "source":"APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE",
        "output_mean":triplet["output_mean"],
        "output_peak_frequency_hz":float(np.float32(triplet["output_peak_x_bin"]*float(np.float32(fs/n)))),
        "output_peak_y":triplet["output_peak_y"],
    }
    txt=spectrum_triplet_text(summary, decimal_separator=decimal)
    ref=tmp_path/"operator_copy.txt"
    ref.write_text(txt+"\n",encoding=encoding)
    return mp,ref,manifest,txt


@pytest.mark.parametrize("decimal", [",","."])
def test_synthetic_copy_text_from_raw_single_matches_no_archive_required(
    tmp_path, decimal,
):
    manifest,reference,metadata,expected=_synthetic_manifest(tmp_path,decimal=decimal)
    result=compare_original_copy_text(manifest,reference,decimal_separator=decimal)
    assert result["source"]==SOURCE
    assert result["candidate_built_only_from_original_single_words"] is True
    assert result["all_three_fields_text_equal"] is True
    assert all(result["field_text_equal"].values())
    assert result["candidate_delphi_formatfloat_rtl_verified"] is False
    assert result["same_original_window_clipboard_and_summary_authenticated"] is False
    text=json.dumps(result)
    assert expected not in text
    assert str(tmp_path) not in text
    assert "operator_copy.txt" not in text
    assert "summary_capture.json" not in text


def test_synthetic_copy_one_wrong_formatted_field_is_detected(tmp_path):
    manifest,ref,meta,text=_synthetic_manifest(tmp_path)
    fields=text.split("\t")
    fields[1]="0"
    ref.write_text("\t".join(fields),encoding="utf-8-sig")
    result=compare_original_copy_text(manifest,ref,decimal_separator=",")
    assert not result["all_three_fields_text_equal"]
    assert result["field_text_equal"] == {
        "mean_text":True,
        "peak_frequency_text":False,
        "peak_y_text":True,
    }


def test_synthetic_cp1251_and_utf8_sigil(tmp_path):
    manifest,ref,meta,text=_synthetic_manifest(tmp_path,encoding="cp1251")
    result=compare_original_copy_text(
        manifest,ref,decimal_separator=",",encoding="cp1251"
    )
    assert result["all_three_fields_text_equal"]


@pytest.mark.parametrize(("field","bad"), [
    ("schema","OTHER"),
    ("summary_power_stop_va","0x007D154B"),
    ("summary_fields_stop_va","0x007D1901"),
    ("fft_n",1000),("fft_n",True),
    ("sample_rate_hz",0),("sample_rate_hz",True),
    ("spectrum_mode",4),
    ("f_range_bits","0x00000000"),
    ("output_mean_bits","0x7FC00000"),
    ("output_peak_x_bits","ABCDEF01"),
    ("output_peak_y_bits","0xBF800000"),
])
def test_invalid_summary_metadata_fails_closed(tmp_path,field,bad):
    mp,ref,manifest,_=_synthetic_manifest(tmp_path)
    manifest[field]=bad
    mp.write_text(json.dumps(manifest),encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_copy_text(mp,ref)


def test_malformed_reference_triplet_and_symlinks_are_rejected(tmp_path):
    mp,ref,meta,_=_synthetic_manifest(tmp_path)
    ref.write_text("1,25\t3,5\n",encoding="utf-8-sig")
    with pytest.raises(ValueError):
        compare_original_copy_text(mp,ref)
    mp,ref,meta,text=_synthetic_manifest(tmp_path)
    alias=tmp_path/"copy_link.txt"
    try:
        alias.symlink_to(ref)
    except (OSError,NotImplementedError):
        pytest.skip("Symlinks unavailable")
    with pytest.raises(ValueError):
        compare_original_copy_text(mp,alias)


def test_same_data_wrong_decimal_locale_is_not_silent(tmp_path):
    mp,ref,meta,text=_synthetic_manifest(tmp_path,decimal=",")
    with pytest.raises(ValueError):
        compare_original_copy_text(mp,ref,decimal_separator=".")
