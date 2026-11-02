"""Stage111Z.21: source-derived original TSXML bytes/gain and safe import.

Synthetic examples only. Original private _Unit125/_Unit128/EXE/BIN are NOT
stored in CI, repo fixtures or downloaded by these tests.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from mvk_compatible.core.direct_bin_session import DirectBinSession
from mvk_compatible.core.original_tsxml_contract import (
    inspect_original_tsxml,ORIGINAL_TSXML_SOURCE,GAIN_SOURCE
)

NAME="MVK00000043-ADC4-2026-11-01--13-00-00.bin"


def _full_xml(name=NAME,*,num=4,fs=65536,length=8192*4,
              dtype="Single",units="м/с2",gain="0.7786",
              offset="0",filename=None):
    # Full original writer shape: XML decl explicitly says windows-1251.
    actual=f".\\{name}" if filename is None else filename
    return (
        '<?xml version="1.0" encoding="windows-1251"?>\r\n'
        '<MainRoot>\r\n'
        '  <Culture>en-US</Culture>\r\n'
        '  <From Units="ms">0</From>\r\n'
        '  <To Units="ms">500</To>\r\n'
        '  <ChannelsQuantity>1</ChannelsQuantity>\r\n'
        f'  <FrequencyPerChannel>{fs}</FrequencyPerChannel>\r\n'
        f'  <DataFileName>{actual}</DataFileName>\r\n'
        '  <Channels><Channel Index="0">\r\n'
        f'  <ChannelName>MVK43-АЦП{num}</ChannelName>\r\n'
        f'  <ChannelNumber>{num}</ChannelNumber>\r\n'
        f'  <ChannelFrequency>{fs}</ChannelFrequency>\r\n'
        f'  <Units>{units}</Units>\r\n'
        f'  <RealDataType>{dtype}</RealDataType>\r\n'
        f'  <DataLength>{length}</DataLength>\r\n'
        f'  <DataOffset>{offset}</DataOffset>\r\n'
        f'  <InternalChannelGain>{gain}</InternalChannelGain>\r\n'
        '  </Channel></Channels>\r\n'
        '</MainRoot>'
    ).encode("cp1251")


def _write_pair(tmp_path,name=NAME,**kwargs):
    fs=int(kwargs.get("fs",65536))
    dtype=kwargs.get("dtype","Single")
    n=8192
    data=(np.arange(n,dtype=np.uint8).tobytes() if dtype=="Byte"
          else np.asarray(np.linspace(-1,1,n),dtype="<f4").tobytes())
    kwargs.setdefault("length",len(data))
    p=tmp_path/name
    p.write_bytes(data)
    x=tmp_path/(name+".tsxml")
    x.write_bytes(_full_xml(name,**kwargs))
    return p,x,data


def test_original_full_cp1251_sidecar_metadata_is_read_without_recalibration(tmp_path):
    p,x,raw=_write_pair(tmp_path)
    contract=inspect_original_tsxml(x.read_bytes(),actual_bin_filename=p.name)
    assert contract.source_meta_complete is True
    assert contract.sample_rate_hz==65536
    assert contract.data_type=="Single" and contract.sample_width_bytes==4
    assert contract.data_offset_bytes==0 and contract.data_length_bytes==32768
    assert contract.channel_number==4 and contract.channel_units_text=="м/с2"
    assert contract.file_name_declared==r".\MVK00000043-ADC4-2026-11-01--13-00-00.bin"
    assert contract.original_writer_offset_zero is True
    assert contract.gain_loader_branch=="DECLARED_POSITIVE_NO_APPLY_RANGE_SOURCE_BRANCH"
    assert contract.internal_gain_single==float(np.float32(.7786))
    assert contract.original_f_range_single_candidate==float(np.float32(.7786))
    assert contract.original_writer_gain_addr_0e_static is True
    assert contract.physical_units_verified is False
    assert contract.original_runtime_gain_verified is False
    s=DirectBinSession.open(p)
    assert s.available_channels==(4,)
    samples,fs,audit,name=s.samples(4)
    assert samples.tobytes()==raw
    assert audit["original_tsxml_contract_source"]==ORIGINAL_TSXML_SOURCE
    assert audit["original_tsxml_writer_fields_complete"] is True
    assert audit["declared_channel_number"]==4
    assert audit["declared_internal_channel_gain_single"]==float(np.float32(.7786))
    assert audit["original_loader_f_range_single_candidate"]==float(np.float32(.7786))
    assert audit["metadata_gain_was_applied_to_bin_samples"] is False
    assert audit["original_loader_runtime_f_range_verified"] is False
    assert s.verify()["channels"][0]["internal_channel_gain_single"]==float(np.float32(.7786))
    assert s.verify()["channels"][0]["bin_samples_gain_multiplied_by_reader"] is False
    assert s.verify()["channels"][0]["calibration_verified"] is False


def test_missing_and_nonpositive_gain_are_fallback_metadata_not_0_scaling(tmp_path):
    for txt in ["-2","0","-0.125"]:
        raw=_full_xml(gain=txt)
        meta=inspect_original_tsxml(raw,actual_bin_filename=NAME)
        assert meta.gain_loader_branch=="FALLBACK_DEFAULTCONFIG_RANGE_NOT_AVAILABLE"
        assert meta.original_f_range_single_candidate is None
    missing=_full_xml().replace(
        b"<InternalChannelGain>0.7786</InternalChannelGain>",b""
    )
    meta=inspect_original_tsxml(missing,actual_bin_filename=NAME)
    assert meta.gain_loader_branch=="FALLBACK_DEFAULTCONFIG_GAIN_MISSING_UNVERIFIED"
    assert meta.internal_gain_single is None
    assert not meta.source_meta_complete


def test_original_byte_counter_metadata_is_distinguished_but_not_recast_float(tmp_path):
    name="MVK00000043-ADC4-2026-11-01--13-00-00.bin"
    p,x,_=_write_pair(tmp_path,name,dtype="Byte",units="Count",gain="1")
    meta=inspect_original_tsxml(x.read_bytes(),actual_bin_filename=p.name)
    assert meta.data_type=="Byte"
    assert meta.sample_width_bytes==1
    assert meta.data_length_bytes==8192
    with pytest.raises(ValueError,match="RealDataType=Byte"):
        DirectBinSession.open(p)


def test_full_tsxml_wrong_channel_number_rejected_no_mixed_adc(tmp_path):
    p,x,_=_write_pair(tmp_path,num=3)
    with pytest.raises(ValueError,match="ChannelNumber"):
        DirectBinSession.open(p)


def test_nonstandard_filename_uses_declared_channel_not_guessed_adc1(tmp_path):
    p,x,raw=_write_pair(tmp_path,name="test-original.bin",num=6)
    s=DirectBinSession.open(p)
    assert s.available_channels==(6,)
    assert s.samples(6)[0].tobytes()==raw
    with pytest.raises(ValueError,match="АЦП"):
        s.samples(1)


@pytest.mark.parametrize(("wrong","pattern"),[
    ("other.bin","DataFileName"),
    (r".\other.bin","DataFileName"),
    (r"..\hidden.bin","DataFileName"),
    (r"C:\measurements\something.bin","DataFileName"),
    (r"/tmp/other.bin","DataFileName"),
    ("../"+NAME,"DataFileName")
])
def test_refuses_relative_escape_or_mismatched_bin_label(tmp_path,wrong,pattern):
    p,x,_=_write_pair(tmp_path,filename=wrong)
    with pytest.raises(ValueError,match=pattern):
        DirectBinSession.open(p)


def test_rejects_duplicate_metadata_in_same_channel(tmp_path):
    p,x,_=_write_pair(tmp_path)
    xml=x.read_bytes()
    xml=xml.replace(b"<DataLength>32768</DataLength>",
                    b"<DataLength>32768</DataLength><DataLength>32768</DataLength>")
    x.write_bytes(xml)
    with pytest.raises(ValueError,match="повторяющееся поле DataLength"):
        DirectBinSession.open(p)


def test_top_level_frequency_cannot_disagree_with_channel_frequency(tmp_path):
    p,x,_=_write_pair(tmp_path)
    xml=x.read_bytes()
    x.write_bytes(xml.replace(b"<FrequencyPerChannel>65536</FrequencyPerChannel>",
                              b"<FrequencyPerChannel>32768</FrequencyPerChannel>"))
    with pytest.raises(ValueError,match="FrequencyPerChannel"):
        DirectBinSession.open(p)


@pytest.mark.parametrize("gain",["nan","inf","1e999","text"])
def test_untrusted_gain_is_never_accepted_as_real_physical_calibration(
    tmp_path,gain
):
    p,x,_=_write_pair(tmp_path,gain=gain)
    with pytest.raises(ValueError,match="InternalChannelGain"):
        DirectBinSession.open(p)


def test_original_data_length_is_bytes_and_not_four_byte_sample_count(tmp_path):
    p,x,raw=_write_pair(tmp_path)
    x.write_bytes(x.read_bytes().replace(
        b"<DataLength>32768</DataLength>",b"<DataLength>8192</DataLength>"))
    with pytest.raises(ValueError,match="DataOffset\\+DataLength"):
        DirectBinSession.open(p)


def test_legacy_minimal_tsxml_is_still_supported_without_claim_of_original_writer(
    tmp_path
):
    from .test_stage111z16_direct_bin_tsxml import _make_pair
    p,_,expected=_make_pair(tmp_path)
    s=DirectBinSession.open(p)
    assert s.available_channels==(4,)
    arr,fs,audit,filename=s.samples(4)
    assert np.array_equal(arr,expected)
    assert audit["original_tsxml_writer_fields_complete"] is False
    assert audit["declared_internal_channel_gain_single"] is None
    assert audit["original_loader_gain_branch_from_idr"]==(
        "FALLBACK_DEFAULTCONFIG_GAIN_MISSING_UNVERIFIED")
    assert not audit["metadata_gain_was_applied_to_bin_samples"]


def test_mismatched_original_metadata_does_not_change_original_native_r61_zip(
    tmp_path
):
    from .test_offline_core import fixture_zip
    from mvk_compatible.core.offline_export import OfflineSession
    z=fixture_zip(tmp_path)
    s=OfflineSession.open(z)
    before=s.calculations()
    assert before["source"]=="MVK_DSP"
    s.verify()
    assert s.calculations()==before
