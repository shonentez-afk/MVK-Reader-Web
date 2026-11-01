"""Stage111Z.16: fabricated local BIN/TSXML direct open, no DSP fabrication.

All data here are synthetic sinusoidal Float32 arrays, never original MVK
measurement archives, private IDR or source executables.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from mvk_compatible.core.direct_bin_session import (
    DirectBinSession, PROVENANCE,
)
from mvk_compatible.core.offline_export import OfflineSession
from .test_offline_core import fixture_zip


SERIAL = "MVK00000043"
STAMP = "2026-11-01--13-00-00"


def _make_pair(folder: Path, *, adc=4, n=8192, fs=65536,
               dtype="Single", offset=0, length_override=None,
               name=None, xml_extra=""):
    stem = name or f"{SERIAL}-ADC{adc}-{STAMP}.bin"
    signal = np.asarray(
        0.25 + 1.2 * np.sin(2*np.pi*128*np.arange(n)/fs),dtype="<f4"
    )
    path = folder/stem
    path.write_bytes(b"H"*offset + signal.tobytes())
    size = length_override if length_override is not None else n*4
    text = (
        f"<MainRoot><Channels><Channel>"
        f"<RealDataType>{dtype}</RealDataType>"
        f"<DataLength>{size}</DataLength>"
        f"<DataOffset>{offset}</DataOffset>"
        f"<ChannelFrequency>{fs}</ChannelFrequency>"
        f"</Channel></Channels></MainRoot>{xml_extra}"
    )
    companion = folder/(stem+".tsxml")
    companion.write_text(text,encoding="utf-8")
    return path,companion,signal


def test_direct_single_bin_tsxml_opens_without_r61_csv_or_dsp(tmp_path):
    p,sidecar,expected = _make_pair(tmp_path)
    s=DirectBinSession.open(p)
    assert isinstance(s, OfflineSession)
    assert s.available_channels==(4,)
    assert s.serial==SERIAL
    assert s.updates==1
    samples,fs,audit,filename=s.samples(4)
    np.testing.assert_array_equal(samples.view("<u4"), expected.view("<u4"))
    assert fs==65536.
    assert filename==p.name
    assert audit["source"]==PROVENANCE
    assert audit["physical_units_verified"] is False
    assert audit["dsp_metrics_available"] is False
    assert s.verify()["dsp_source"]=="NOT_AVAILABLE_NO_AUX_VALUES"
    assert not s.verify()["fft_original_parity_verified"]
    with pytest.raises(ValueError, match="VALUES/AUX"):
        s.calculations()
    with pytest.raises(ValueError, match="АЦП"):
        s.samples(1)
    with pytest.raises(ValueError, match="АЦП"):
        s.samples(8)


def test_sidecar_file_can_be_selected_instead_of_bin(tmp_path):
    p,sidecar,_=_make_pair(tmp_path,adc=3)
    s=DirectBinSession.open(sidecar)
    assert s.available_channels==(3,)
    assert s.path==p.absolute()


def test_alternate_pair_name_and_unrecognized_name_open_as_one_channel(tmp_path):
    p,sidecar,_=_make_pair(tmp_path,adc=4,name="my-saved-measurement.bin")
    sidecar.rename(p.with_suffix(".tsxml"))
    s=DirectBinSession.open(p)
    assert s.available_channels==(1,)
    assert s.serial=="LOCAL_BIN_SINGLE_CHANNEL"
    assert s.samples(1)[0].size==8192
    with pytest.raises(ValueError):
        s.samples(4)


def test_grouped_same_instrument_and_timestamp_adcs_only(tmp_path):
    p4,_,arr4=_make_pair(tmp_path,adc=4)
    p6,_,arr6=_make_pair(tmp_path,adc=6)
    _make_pair(tmp_path,adc=5,name="MVK00000043-ADC5-2026-11-01--13-00-01.bin")
    _make_pair(tmp_path,adc=1,name="MVK00000111-ADC1-2026-11-01--13-00-00.bin")
    s=DirectBinSession.open(p6)
    assert s.available_channels==(4,6)
    assert s.samples(4)[0].size==arr4.size
    assert s.samples(6)[0].size==arr6.size
    with pytest.raises(ValueError):
        s.samples(5)


def test_spectrum_and_waveform_reuse_existing_offline_math_without_dsp(tmp_path):
    p,_,arr=_make_pair(tmp_path)
    s=DirectBinSession.open(p)
    wave=s.waveform(4,0.,.1,mode="ac",points=1000)
    assert wave["source"]==PROVENANCE
    assert wave["physical_units_verified"] is False
    assert wave["window_samples"]==round(.1*65536)
    assert len(wave["amplitude"])>0
    assert "не проверена" in wave["unit"]
    spec=s.spectrum(4,8192,1,0.,max_hz=2000,max_points=1000)
    assert spec["source"]=="APP_DERIVED_DIRECT_BIN_FFT_CANDIDATE"
    assert spec["physical_units_verified"] is False
    assert spec["original_bin_decoder_parity_verified"] is False
    assert spec["n_fft"]==8192
    assert "калибровка" in spec["warning"]
    assert "условные единицы" in spec["unit"]
    assert np.max(spec["amplitude"])>0
    cursor=s.exact_sample(4,21/65536.,0.,.0625,"acdc")
    assert cursor["source"]==PROVENANCE
    assert cursor["physical_units_verified"] is False
    assert cursor["index"]==21


def test_declared_bin_offset_is_supported_but_no_undocumented_trailing_bytes(tmp_path):
    p,_,expected=_make_pair(tmp_path,offset=16)
    s=DirectBinSession.open(p)
    np.testing.assert_array_equal(s.samples(4)[0],expected)
    p.write_bytes(p.read_bytes()+b"junk")
    with pytest.raises(ValueError):
        DirectBinSession.open(p)


@pytest.mark.parametrize(("dtype","offset","length_override","fs"),[
    ("Double",0,None,65536),
    ("Int16",0,None,65536),
    ("Single",-1,None,65536),
    ("Single",0,123,65536),
    ("Single",0,8192*4+4,65536),
    ("Single",0,None,0),
    ("Single",0,None,"NaN"),
    ("Single",0,None,65536.5),
    ("Single",0,None,2000000),
])
def test_fails_closed_for_unsupported_or_false_tsxml_metadata(
    tmp_path, dtype, offset, length_override, fs
):
    p,_,_=_make_pair(
        tmp_path,dtype=dtype,offset=max(offset,0),
        length_override=length_override,fs=65536,
    )
    sidecar=p.with_name(p.name+".tsxml")
    original=sidecar.read_text(encoding="utf-8")
    if offset<0:
        original=original.replace(
            "<DataOffset>0</DataOffset>","<DataOffset>-1</DataOffset>"
        )
    if fs!=65536:
        original=original.replace(
            "<ChannelFrequency>65536</ChannelFrequency>",
            f"<ChannelFrequency>{fs}</ChannelFrequency>"
        )
    sidecar.write_text(original,encoding="utf-8")
    with pytest.raises(ValueError):
        DirectBinSession.open(p)


def test_file_mutation_same_size_is_detected_before_reuse(tmp_path):
    p,_,_=_make_pair(tmp_path)
    s=DirectBinSession.open(p)
    raw=bytearray(p.read_bytes())
    raw[150] ^= 0x01
    p.write_bytes(raw)
    with pytest.raises(ValueError, match="изменён"):
        s.samples(4)


def test_sidecar_mutation_same_file_invalidates_opened_session(tmp_path):
    p,sidecar,_=_make_pair(tmp_path)
    s=DirectBinSession.open(p)
    sidecar.write_text(
        sidecar.read_text().replace("65536","32768"),encoding="utf-8"
    )
    with pytest.raises(ValueError, match="изменён"):
        s.samples(4)


def test_missing_pair_or_ambiguous_sidecars_not_read_as_f32(tmp_path):
    p,sidecar,_=_make_pair(tmp_path)
    sidecar.unlink()
    with pytest.raises(ValueError, match="парная TSXML"):
        DirectBinSession.open(p)
    sidecar.write_text("<MainRoot/>",encoding="utf-8")
    with pytest.raises(ValueError):
        DirectBinSession.open(p)
    sidecar.write_text(_make_pair(tmp_path)[1].read_text())
    # A second filename convention for the SAME BIN is ambiguous.
    other=p.with_suffix(".tsxml")
    other.write_text(sidecar.read_text())
    with pytest.raises(ValueError,match="ровно одна"):
        DirectBinSession.open(p)


def test_external_dtd_entity_or_extra_xml_channels_are_refused(tmp_path):
    p,sidecar,_=_make_pair(tmp_path)
    sidecar.write_text(
        "<!DOCTYPE foo [<!ENTITY x SYSTEM 'file:///private'>]>"
        "<MainRoot><Channels><Channel><RealDataType>Single</RealDataType>"
        "</Channel></Channels></MainRoot>",encoding="utf-8"
    )
    with pytest.raises(ValueError,match="DTD"):
        DirectBinSession.open(p)
    _make_pair(tmp_path)
    text=sidecar.read_text()
    sidecar.write_text(text.replace("</Channels>",
        "<Channel><RealDataType>Single</RealDataType></Channel></Channels>"))
    with pytest.raises(ValueError,match="ровно один канал"):
        DirectBinSession.open(p)


def test_nonfinite_bin_is_refused_even_with_valid_xml(tmp_path):
    p,_,arr=_make_pair(tmp_path)
    arr[42]=np.float32(np.nan)
    p.write_bytes(arr.tobytes())
    with pytest.raises(ValueError,match="NaN/Inf"):
        DirectBinSession.open(p)


def test_mixed_fs_in_group_is_rejected(tmp_path):
    p,_,_=_make_pair(tmp_path,adc=4,fs=65536)
    _make_pair(tmp_path,adc=5,fs=32768)
    with pytest.raises(ValueError,match="разную частоту"):
        DirectBinSession.open(p)


def test_direct_pair_does_not_weaken_native_zip_audit(tmp_path):
    z=fixture_zip(tmp_path)
    original=OfflineSession.open(z)
    assert original.calculations()["source"]=="MVK_DSP"
    # A simple unverified ZIP cannot silently stand in for R6.1 export.
    from zipfile import ZipFile
    unverified=tmp_path/"unverified.zip"
    with ZipFile(unverified,"w") as archive:
        archive.writestr("record.bin",np.zeros(8192,dtype="<f4").tobytes())
        archive.writestr("record.bin.tsxml","<MainRoot/>")
    with pytest.raises(ValueError,match="EXPORT_AUDIT"):
        OfflineSession.open(unverified)


def test_direct_symlink_is_rejected(tmp_path):
    p,sidecar,_=_make_pair(tmp_path)
    alias=tmp_path/"alias.bin"
    try:
        alias.symlink_to(p)
    except (OSError,NotImplementedError):
        pytest.skip("System does not permit symlink")
    with pytest.raises(ValueError):
        DirectBinSession.open(alias)
