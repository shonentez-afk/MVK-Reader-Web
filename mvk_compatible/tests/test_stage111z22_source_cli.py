"""Stage111Z.22: operator CLI never exposes filenames/raw captures."""
from __future__ import annotations

import json

from mvk_compatible.offline_source_audit_cli import (
    inspect_local_bin_sidecar,main
)
from .test_stage111z21_original_tsxml import _write_pair
from .test_stage111z22_original_fft_pair import _pair


def test_local_original_single_sidecar_manifest_redacts_paths(tmp_path,capsys):
    p,xml,raw=_write_pair(tmp_path)
    before=p.read_bytes(),xml.read_bytes()
    result=inspect_local_bin_sidecar(p)
    assert result["data_type"]=="Single"
    assert result["sample_count"]==8192
    assert result["channel_frequency_hz"]==65536
    assert result["original_writer_fields_complete"] is True
    assert result["physical_units_verified"] is False
    assert result["samples_scaled_by_this_inspection"] is False
    assert result["f_range_source_candidate_static_only"] is not None
    assert "bin_sha256" in result and len(result["bin_sha256"])==64
    assert "tsxml_sha256" in result and len(result["tsxml_sha256"])==64
    assert result["file_names_and_paths_exposed"] is False
    assert result["contains_original_sample_data"] is False
    assert p.read_bytes()==before[0] and xml.read_bytes()==before[1]
    assert main(["inspect",str(xml)])==0
    printed=capsys.readouterr().out
    manifest=json.loads(printed)
    assert manifest==result
    assert p.name not in printed
    assert str(tmp_path) not in printed


def test_byte_counter_sidecar_metadata_inspected_but_not_fft(tmp_path):
    p,_,_=_write_pair(tmp_path,dtype="Byte",units="Count",gain="1")
    r=inspect_local_bin_sidecar(p)
    assert r["data_type"]=="Byte" and r["sample_count"]==8192
    assert r["status"].startswith("BYTE_COUNTER_METADATA_ONLY")
    assert not r["samples_scaled_by_this_inspection"]
    assert r["original_signal_spectrum_numeric_parity_verified"] is False


def test_compare_original_fft_cli_offline_no_source_paths(tmp_path,capsys):
    t,p,_,_=_pair(tmp_path)
    assert main(["verify-fft",str(t),str(p),"--fs","4096"])==0
    out=capsys.readouterr().out
    d=json.loads(out)
    assert d["n_fft"]==4096 and d["peak_frequency_hz"]==50.
    assert d["float32_bit_exact_bins"]==2048
    assert t.name not in out and p.name not in out
    assert str(tmp_path) not in out
    assert not d["original_float32_radix2_bit_parity_verified"]
