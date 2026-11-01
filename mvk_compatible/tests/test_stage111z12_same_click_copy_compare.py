"""Stage111Z.12 — synthetic-only same-click Copy record comparisons.

No original archive, source EXE/IDP, user screenshot or real clipboard is
embedded here. Synthetic values represent a deliberately different graph
record from the old Stage111Z.10 GetSpectrum call to detect false matching.
"""
from __future__ import annotations

import json
import struct

import numpy as np
import pytest

from mvk_compatible.core.spectrum_summary_export_candidate import (
    spectrum_triplet_text,
)
from mvk_compatible.private_spectrum_copy_selected_record_compare import (
    SCHEMA, SOURCE, compare_original_copy_selected_record,
)


def _bits(value: float) -> str:
    raw = struct.unpack("<I",struct.pack("<f",float(np.float32(value))))[0]
    return f"0x{raw:08X}"


def _fabricated_same_click(tmp_path):
    # These values are INVENTED; they are not original MVKView measurements.
    mean=np.float32(5.625)
    peak_bin=np.float32(79.75)
    xscale=np.float32(0.25)
    peak_y=np.float32(5.53125)
    m={
        "schema": SCHEMA,
        "copy_breakpoint_va":"0x0084BC8C",
        "output_mean_bits":_bits(mean),
        "output_peak_x_bin_bits":_bits(peak_bin),
        "output_peak_y_bits":_bits(peak_y),
        "graph_xscale_bits":_bits(xscale),
        "original_clipboard_file":"same_click.txt",
        "decimal_separator":",",
    }
    f=tmp_path/"same_click.json"
    f.write_text(json.dumps(m),encoding="utf-8")
    text=spectrum_triplet_text({
        "source":"APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE",
        "output_mean":mean,
        "output_peak_frequency_hz":float(np.float32(float(peak_bin)*float(xscale))),
        "output_peak_y":peak_y,
    },decimal_separator=",")
    copy=tmp_path/"same_click.txt"
    copy.write_text(text+"\n",encoding="utf-8")
    return f,copy,m,text


def test_synthetic_one_click_record_and_graph_xscale_match(tmp_path):
    manifest,copy,data,text=_fabricated_same_click(tmp_path)
    result=compare_original_copy_selected_record(manifest)
    assert result["source"]==SOURCE and result["schema"]==SCHEMA
    assert result["formatting_digits_source"] == [3,4,4]
    assert result["all_three_text_fields_equal"] is True
    assert result["text_fields_equal"] == {
        "mean":True,"peak_frequency_hz":True,"peak_amplitude":True
    }
    assert result["no_archive_derived_or_inferred_fs_f_range"] is True
    assert result["selected_record_same_as_previous_GetSpectrum_authenticated"] is False
    assert result["original_Delphi_RTL_general_formatting_parity_verified"] is False
    exposed=json.dumps(result)
    assert text not in exposed
    assert str(tmp_path) not in exposed
    assert "same_click.txt" not in exposed


def test_current_copy_record_must_not_reuse_earlier_getspectrum_triplet(tmp_path):
    manifest,copy,data,text=_fabricated_same_click(tmp_path)
    # Another invocation's candidate means/frequency/amplitude (fabricated).
    different_copy="6,89\t3800\t0,7786"
    copy.write_text(different_copy+"\n",encoding="utf-8")
    result=compare_original_copy_selected_record(manifest)
    assert result["all_three_text_fields_equal"] is False
    assert not any(result["text_fields_equal"].values())


def test_each_wrong_synthetic_field_is_detectable(tmp_path):
    manifest,copy,data,text=_fabricated_same_click(tmp_path)
    fields=text.split("\t")
    for i,name in enumerate(("mean","peak_frequency_hz","peak_amplitude")):
        changed=list(fields)
        changed[i]="0"
        copy.write_text("\t".join(changed),encoding="utf-8")
        result=compare_original_copy_selected_record(manifest)
        assert result["text_fields_equal"][name] is False
        assert sum(result["text_fields_equal"].values()) == 2


@pytest.mark.parametrize(("field","bad"),[
    ("schema","WRONG"),
    ("copy_breakpoint_va","0x0084BC8D"),
    ("output_mean_bits","0x7FC00000"),
    ("output_peak_x_bin_bits","0xBF800000"),
    ("output_peak_y_bits","0x7F800000"),
    ("graph_xscale_bits","0x00000000"),
    ("graph_xscale_bits","0xBF800000"),
    ("graph_xscale_bits","0x7F800000"),
    ("output_mean_bits","43FF4853"),
    ("original_clipboard_file","../private.txt"),
    ("original_clipboard_file","C:\\Private\\copy.txt"),
    ("original_clipboard_file","manifest.json"),
    ("decimal_separator",";"),
])
def test_bad_source_words_and_malformed_manifest_fail_closed(tmp_path,field,bad):
    manifest,copy,data,text=_fabricated_same_click(tmp_path)
    data[field]=bad
    manifest.write_text(json.dumps(data),encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_copy_selected_record(manifest)


def test_wrong_filename_or_source_clipboard_shape_fails_closed(tmp_path):
    manifest,copy,data,text=_fabricated_same_click(tmp_path)
    copy.write_text("1,5\t2,5\n",encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_copy_selected_record(manifest)
    manifest,copy,data,text=_fabricated_same_click(tmp_path)
    data["extra"]="unexpected field"
    manifest.write_text(json.dumps(data),encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_copy_selected_record(manifest)


def test_clipboard_symlink_is_never_followed(tmp_path):
    manifest,copy,data,text=_fabricated_same_click(tmp_path)
    copy.unlink()
    hidden=tmp_path/"hidden.txt"
    hidden.write_text(text,encoding="utf-8")
    try:
        copy.symlink_to(hidden)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are not supported on this OS")
    with pytest.raises(ValueError):
        compare_original_copy_selected_record(manifest)
