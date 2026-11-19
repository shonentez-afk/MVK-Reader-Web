"""Unified local numerical/output parity gate; all fixtures synthetic.

No original vendor bytes, secret FIR banks, device socket or uploaded traces.
"""
from __future__ import annotations

from datetime import datetime,timezone
import json
import math
from pathlib import Path
import struct
from xml.etree import ElementTree as ET

import numpy as np
import pytest

from mvk_compatible.core.envelope_idr_candidate import (
    _source_getsignal_rms_stepwise,
)
from mvk_compatible.core.envelope_spectrum_idr_candidate import (
    _delphi_integration_power,
)
from mvk_compatible.core.original_mode2_source_files import (
    source_data_filename,build_original_tsxml_compatible,
)
from mvk_compatible.core.original_mode2_paired_acceptance import (
    compare_original_mode2_pair,
)


def test_getsignal_rms_matches_stored_qword_scalar_sum_not_pairwise_mean():
    source=np.random.default_rng(77).standard_normal(10017).astype("<f4")
    acc=0.0
    for item in source:
        x=float(item)
        acc=float(acc+x*x)
    expected=float(np.float32(math.sqrt(acc/len(source))*float(np.float32(2.5))))
    assert _source_getsignal_rms_stepwise(source,2.5)==expected
    assert source.tobytes()==np.asarray(source,dtype="<f4").tobytes()
    for invalid in (0,-1,float("nan"),1e300):
        with pytest.raises(ValueError):
            _source_getsignal_rms_stepwise(source,invalid)
    with pytest.raises(ValueError):
        _source_getsignal_rms_stepwise(np.array([np.inf],dtype="f4"),1.)


@pytest.mark.parametrize("passes",[1,2])
def test_spectrum_power_integration_single_inverse_df_rounds_every_pass(passes):
    p=np.arange(512,dtype=np.float32)**2  # source GetSpectrum power is N/2
    before=p.copy()
    got=_delphi_integration_power(p,1024,32768,passes)
    scalar=p.copy()
    reciprocal=float(np.float32(1024./32768))
    scalar[0]=0
    for k in range(1,len(p)):
        for _ in range(passes):
            scalar[k]=np.float32(
                float(scalar[k])*(159.154943091895/k*reciprocal)**2)
    assert np.array_equal(got.view("u4"),scalar.view("u4"))
    assert np.array_equal(p,before)
    assert got[0]==0


def test_original_cyrillic_filename_is_allowed_in_cp1251_tsxml_not_slugged():
    when=datetime(2026,11,19,10,30,0,tzinfo=timezone.utc)
    name=source_data_filename(
        device="Стенд 7",channel_label="АЦП1",
        user_prefix="Проверка#",when=when)
    assert "Стенд 7-АЦП1" in name
    xml,details=build_original_tsxml_compatible(
        channel=1,binary_basename=name,size_bytes=4096,
        rate_hz=65536,local_time=when,device_label="Стенд 7",
        channel_label="АЦП1",adc_units="м/с2",adc_gain=1.0)
    root=ET.fromstring(xml)
    assert root.findtext("DataFileName")==".\\"+name
    assert root.findtext("Channels/Channel/ChannelName")=="Стенд 7-АЦП1"
    assert details["original_delphi_tsxml_byte_parity_verified"] is False
    for unsafe in ("../bad.bin","..x.bin",r"C:\bad.bin","/abs.bin","bad\x00.bin"):
        with pytest.raises(ValueError):
            build_original_tsxml_compatible(
                channel=1,binary_basename=unsafe,size_bytes=4,
                rate_hz=65536,local_time=when,device_label="MVK",
                channel_label="ADC1")


def test_local_pair_exact_files_float32_and_source_stream_but_not_delphi_parity(tmp_path):
    ref=tmp_path/"original"
    new=tmp_path/"candidate"
    ref.mkdir();new.mkdir()
    samples=np.array([.125,-.75,4.,12.5],dtype="<f4").tobytes()
    content={
        "incoming.raw":b"SYNTHETIC_TCP_ONLY",
        "ADC1.bin":samples,
        "source.tsxml":('<?xml version="1.0" encoding="windows-1251"?>\r\n'
                       '<R>Стенд</R>\r\n').encode("cp1251"),
        "VALUES.csv":"Отсчёт;Значение\r\n1;2\r\n".encode("cp1251"),
    }
    for folder in (ref,new):
        for name,blob in content.items():
            (folder/name).write_bytes(blob)
    files=[
        dict(kind="ADC_BIN_F32",reference_name="ADC1.bin",
             candidate_name="ADC1.bin"),
        dict(kind="TSXML_CP1251",reference_name="source.tsxml",
             candidate_name="source.tsxml"),
        dict(kind="VALUES_CSV",reference_name="VALUES.csv",
             candidate_name="VALUES.csv"),
    ]
    report=compare_original_mode2_pair(
        ref,new,session_id="SYNTHETIC_TEST",
        files=files,reference_raw_name="incoming.raw",
        candidate_raw_name="incoming.raw")
    assert report["same_input_tcp_raw_verified"]
    assert report["raw_proof"]["same_original_tcp_bytes"]
    assert report["file_pairs_compared"]==3
    assert report["all_pairs_byte_identical"]
    assert report["pairs"][0]["bitwise_equal_float32_words"]==4
    assert report["pairs"][0]["exact_float32_bitwise_match"]
    assert not report["original_delphi_compatibility_verified"]
    assert not report["original_1_to_1_release_gate_passed"]
    assert "original/" not in json.dumps(report)

    # A one-ULP changed Single and an unchanged SHA-bound RAW must be
    # reported as a numerical/file mismatch, not as 1:1 parity.
    mutated=bytearray(samples)
    mutated[0]^=1
    (new/"ADC1.bin").write_bytes(mutated)
    different=compare_original_mode2_pair(
        ref,new,session_id="SYNTHETIC_TEST",
        files=files,reference_raw_name="incoming.raw",
        candidate_raw_name="incoming.raw")
    assert not different["all_pairs_byte_identical"]
    assert different["pairs"][0]["different_float32_words"]==1
    assert different["pairs"][0]["first_different_float32_word"]==0
    assert different["pairs"][1]["byte_identical"]


def test_local_pair_requires_same_tcp_source_and_never_follows_symlink(tmp_path):
    ref=tmp_path/"original";new=tmp_path/"candidate"
    ref.mkdir();new.mkdir()
    (ref/"incoming.raw").write_bytes(b"ONE")
    (new/"incoming.raw").write_bytes(b"TWO")
    (ref/"spectrum.bin").write_bytes(np.ones(16,dtype="<f4").tobytes())
    (new/"spectrum.bin").write_bytes(np.ones(16,dtype="<f4").tobytes())
    entry=[dict(kind="GETSPECTRUM_POWER_F32",
                reference_name="spectrum.bin",candidate_name="spectrum.bin")]
    with pytest.raises(ValueError,match="different RAW"):
        compare_original_mode2_pair(
            ref,new,session_id="SYNTH",files=entry,
            reference_raw_name="incoming.raw",
            candidate_raw_name="incoming.raw")
    with pytest.raises(ValueError,match="both streams"):
        compare_original_mode2_pair(
            ref,new,session_id="SYNTH",files=entry,
            reference_raw_name="incoming.raw")
    (new/"incoming.raw").write_bytes(b"ONE")
    (new/"spectrum.bin").unlink()
    (new/"spectrum.bin").symlink_to(ref/"spectrum.bin")
    with pytest.raises(ValueError,match="linked"):
        compare_original_mode2_pair(
            ref,new,session_id="SYNTH",files=entry,
            reference_raw_name="incoming.raw",
            candidate_raw_name="incoming.raw")
