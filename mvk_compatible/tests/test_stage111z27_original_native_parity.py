"""Stage111Z.27 offline comparison tests: synthetic only, no real MVK data."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import zipfile

import numpy as np
import pytest

from mvk_compatible.core.original_native_parity import compare_original_native
from mvk_compatible.original_native_parity_cli import main as cli_main
from .test_offline_core import fixture_zip


def _original_from_fixture(tmp_path, *, count=4096):
    native = fixture_zip(tmp_path, sample_count=count)
    original = tmp_path / "original_local"
    original.mkdir()
    with zipfile.ZipFile(native) as z:
        for name in z.namelist():
            if name.endswith((".bin", ".bin.tsxml")):
                (original/name).write_bytes(z.read(name))
    first = sorted(original.glob("*-ADC1-*.bin"))[0]
    return first, native


def _alter_original(original: Path, adc: int, mutate):
    source = list(original.parent.glob(f"*-ADC{adc}-*.bin"))[0]
    data = source.read_bytes()
    source.write_bytes(mutate(data))
    return source


def test_bitwise_equal_is_observed_not_attested_one_session(tmp_path):
    original, native = _original_from_fixture(tmp_path)
    old_sha=hashlib.sha256(original.read_bytes()).hexdigest()
    report=compare_original_native(original,native)
    assert report["schema"]=="MVK_STAGE111Z27_ORIGINAL_NATIVE_LOCAL_COMPARISON_V1"
    assert report["compared_adc"]==list(range(1,9))
    assert report["all_eight_adc_present_in_original"]
    assert report["bin_bytes_equal_on_matching_file_starts"]
    assert report["tsxml_bytes_equal"]
    assert report["verdict"]=="OBSERVED_BIN_EQUAL_BUT_SAME_RUN_NOT_ATTESTED"
    assert not report["original_same_run_proven"]
    assert not report["auto_applied_f_range_to_original"]
    assert not report["auto_applied_f_range_to_native"]
    assert all(x["bitwise_mismatch_count_on_common_prefix"]==0 for x in report["channels"])
    assert report["channels"][0]["original_bin_sha256"]==old_sha
    assert hashlib.sha256(original.read_bytes()).hexdigest()==old_sha


def test_single_bit_mismatch_has_exact_index_and_float_bits(tmp_path):
    original,native=_original_from_fixture(tmp_path)
    _alter_original(original,4,lambda b: b[:31*4]+struct.pack("<f",13.375)+b[32*4:])
    report=compare_original_native(original,native)
    assert not report["bin_bytes_equal_on_matching_file_starts"]
    assert report["verdict"]=="OBSERVED_BIN_DIFFERENCES_SAME_RUN_NOT_ATTESTED"
    ch=report["channels"][3]
    assert ch["bitwise_mismatch_count_on_common_prefix"]==1
    assert ch["first_bitwise_mismatches"][0]["index_in_compared_file"]==31
    assert ch["max_absolute_numeric_difference"]>0
    assert ch["rms_numeric_difference"]>0


def test_negative_zero_is_not_bitwise_equal_to_positive_zero(tmp_path):
    original,native=_original_from_fixture(tmp_path)
    _alter_original(original,2,lambda b:struct.pack("<I",0x80000000)+b[4:])
    report=compare_original_native(original,native)
    ch=report["channels"][1]
    assert ch["bitwise_mismatch_count_on_common_prefix"]==1
    assert ch["numeric_value_equal_count_on_common_prefix"]==4096
    assert ch["max_absolute_numeric_difference"]==0


def test_tsxml_gain_disagreement_never_scales_bin_automatically(tmp_path):
    original,native=_original_from_fixture(tmp_path)
    xml=list(original.parent.glob("*-ADC4-*.bin.tsxml"))[0]
    s=xml.read_text()
    xml.write_text(s.replace("</Channel>","<InternalChannelGain>0.7786</InternalChannelGain></Channel>"))
    report=compare_original_native(original,native)
    ch=report["channels"][3]
    assert ch["observed_bin_bitwise_equal"]
    assert not ch["tsxml_byte_equal"]
    assert "internal_channel_gain_single" in ch["metadata_differences"]
    assert ch["original_metadata"]["f_range_loader_candidate_only"]==pytest.approx(float(np.float32(.7786)))
    assert not ch["original_and_native_calibration_domain_proven_identical"]
    assert not report["original_same_run_proven"]


def test_differing_original_byte_count_not_silently_padded(tmp_path):
    original,native=_original_from_fixture(tmp_path)
    source=_alter_original(original,4,lambda b:b[:-4])
    sidecar=source.with_name(source.name+".tsxml")
    sidecar.write_text(sidecar.read_text().replace("<DataLength>16384</DataLength>",
                                                  "<DataLength>16380</DataLength>"))
    report=compare_original_native(original,native)
    ch=report["channels"][3]
    assert not ch["lengths_equal"]
    assert ch["compared_samples_from_file_start"]==4095
    assert ch["bitwise_mismatch_count_on_common_prefix"]==0
    assert not ch["observed_bin_bitwise_equal"]
    assert "data_length_bytes" in ch["metadata_differences"]


def test_nonmatching_instrument_serial_refused(tmp_path):
    original,native=_original_from_fixture(tmp_path)
    renamed=original.parent/"MVK99999999-ADC1-2026-10-29--13-32-12.bin"
    # Use a single original file to prevent mixing a group; intentionally
    # keep BIN/TSXML exact and let the instrument name mismatch fail.
    renamed.write_bytes(original.read_bytes())
    (renamed.with_name(renamed.name+".tsxml")).write_bytes(
        (original.with_name(original.name+".tsxml")).read_bytes())
    with pytest.raises(ValueError, match="different instruments"):
        compare_original_native(renamed,native)


def test_partial_original_group_cannot_pass_full_eight_adc_gate(tmp_path):
    original,native=_original_from_fixture(tmp_path)
    for ch in range(2,9):
        for p in original.parent.glob(f"*-ADC{ch}-*.bin*"):
            p.unlink()
    report=compare_original_native(original,native)
    assert report["compared_adc"]==[1]
    assert not report["all_eight_adc_present_in_original"]
    assert report["verdict"]=="PARTIAL_CHANNEL_COMPARISON_SAME_RUN_NOT_ATTESTED"


def test_rejects_orig_byte_count_as_accelerometer(tmp_path):
    original,native=_original_from_fixture(tmp_path)
    xml=original.with_name(original.name+".tsxml")
    xml.write_text(xml.read_text().replace("<RealDataType>Single</RealDataType>",
                                           "<RealDataType>Byte</RealDataType>"))
    with pytest.raises(ValueError,match="RealDataType=Byte"):
        compare_original_native(original,native)


def test_missing_tsxml_and_tampered_native_bin_both_rejected(tmp_path):
    original,native=_original_from_fixture(tmp_path)
    xml=original.with_name(original.name+".tsxml")
    xml.unlink()
    with pytest.raises(ValueError):
        compare_original_native(original,native)
    # Restore original, but corrupt Native archive's actual ADC data without
    # updating its audit: physical SHA must be checked independently.
    xml.write_text("<MainRoot><Channels><Channel><RealDataType>Single</RealDataType><DataLength>16384</DataLength><DataOffset>0</DataOffset><ChannelFrequency>65536</ChannelFrequency></Channel></Channels></MainRoot>")
    with zipfile.ZipFile(native) as z:
        contents={name:z.read(name) for name in z.namelist()}
    name=next(n for n in contents if "-ADC1-" in n and n.endswith(".bin"))
    contents[name]=contents[name][0:4]+struct.pack("<f",100.)+contents[name][8:]
    changed=tmp_path/"tampered.zip"
    with zipfile.ZipFile(changed,"w") as z:
        for key,value in contents.items():z.writestr(key,value)
    with pytest.raises(ValueError,match="physical BIN SHA256"):
        compare_original_native(original,changed)


def test_cli_private_json_no_overwrite_and_exit_codes(tmp_path,capsys):
    original,native=_original_from_fixture(tmp_path)
    path=tmp_path/"qa_local.json"
    assert cli_main([str(original),str(native),"--report",str(path)])==0
    saved=json.loads(path.read_text())
    assert saved["original_same_run_proven"] is False
    assert not any("/mnt/data" in str(v) for v in saved.values())
    assert cli_main([str(original),str(native),"--report",str(path)])==2
    assert "REFUSED" in capsys.readouterr().err
    _alter_original(original,3,lambda b:b[:12]+struct.pack("<f",3.14159)+b[16:])
    assert cli_main([str(original),str(native),"--require-bin-equal"])==3
    assert "NOT ATTESTED" in capsys.readouterr().out
