"""Stage111Z29A: synthetic local comparator QA, NEVER real original dump."""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import numpy as np
import pytest

from mvk_compatible.core.offline_export import OfflineSession
from mvk_compatible.core.signal_idr_candidate import unfiltered_getsignal
from mvk_compatible.private_getsignal_original_pair_compare import (
    compare_original_getsignal_return,main
)
from .test_offline_core import fixture_zip


def _source(tmp_path,*,count=1024,first=128,mode="ac"):
    path=fixture_zip(tmp_path)
    s=OfflineSession.open(path)
    samples,fs,_,_=s.samples(2)
    frame=unfiltered_getsignal(
        samples[first:first+count],fs,no_dc=mode=="ac")
    reference=tmp_path/"private_operator_getsignal.bin"
    reference.write_bytes(frame.getsignal_buffer.tobytes())
    return path,reference,frame


@pytest.mark.parametrize("mode",["ac","acdc"])
def test_fake_operator_buffer_matches_only_for_correct_mode_window(tmp_path,mode):
    path,reference,frame=_source(tmp_path,mode=mode)
    before=path.read_bytes()
    a=compare_original_getsignal_return(
        path,reference,channel=2,first_sample=128,sample_count=1024,mode=mode)
    assert a["float32_words_exact"]==a["float32_words_total"]==1024
    assert a["float32_ulp_max"]==a["float32_ulp_median"]==0
    assert a["float32_first_mismatch_index"] is None
    assert a["candidate_output_matches_operator_dump_bitwise"]
    assert a["original_return_buffer_expected_reverse_order"]
    assert not a["original_same_run_identity_authenticated"]
    assert not a["original_frange_and_ring_end_runtime_verified"]
    assert not a["original_pageadc_pixel_parity_verified"]
    assert a["private_byte_values_or_source_paths_in_report"] is False
    assert str(tmp_path) not in json.dumps(a)
    assert reference.name not in json.dumps(a)
    assert path.read_bytes()==before


def test_wrong_start_channel_and_ac_flag_are_not_false_passes(tmp_path):
    path,reference,_=_source(tmp_path)
    for kwargs in [
        dict(channel=1,first_sample=128,mode="ac"),
        dict(channel=2,first_sample=129,mode="ac"),
        dict(channel=2,first_sample=128,mode="acdc"),
    ]:
        a=compare_original_getsignal_return(
            path,reference,sample_count=1024,**kwargs)
        assert not a["candidate_output_matches_operator_dump_bitwise"]
        assert a["float32_words_exact"]<1024


def test_chronological_array_is_not_original_reverse_return(tmp_path):
    path,reference,frame=_source(tmp_path)
    reference.write_bytes(frame.chronological.tobytes())
    a=compare_original_getsignal_return(
        path,reference,channel=2,first_sample=128,
        sample_count=1024,mode="ac")
    assert not a["candidate_output_matches_operator_dump_bitwise"]


def test_one_bit_changed_reports_first_mismatch_and_ulps(tmp_path):
    path,reference,_=_source(tmp_path)
    raw=np.frombuffer(reference.read_bytes(),dtype="<u4").copy()
    raw[73]^=np.uint32(1)
    reference.write_bytes(raw.tobytes())
    result=compare_original_getsignal_return(
        path,reference,channel=2,first_sample=128,
        sample_count=1024,mode="ac")
    assert result["float32_first_mismatch_index"]==73
    assert result["float32_words_exact"]==1023
    assert result["float32_ulp_max"]>=1
    assert result["original_getsignal_output_sha256"]!=result["candidate_output_sha256"]


def test_zero_placeholder_nan_symlink_and_missing_data_rejected(tmp_path):
    path,reference,_=_source(tmp_path)
    original=reference.read_bytes()
    with pytest.raises(ValueError,match="lacks full"):
        compare_original_getsignal_return(
            path,reference,channel=2,first_sample=4090,
            sample_count=1024,mode="ac")
    reference.write_bytes(b"\0"*len(original))
    with pytest.raises(ValueError,match="all zero"):
        compare_original_getsignal_return(
            path,reference,channel=2,first_sample=128,
            sample_count=1024,mode="ac")
    ref=np.frombuffer(original,dtype="<f4").copy()
    ref[20]=np.nan
    reference.write_bytes(ref.tobytes())
    with pytest.raises(ValueError,match="Invalid original"):
        compare_original_getsignal_return(
            path,reference,channel=2,first_sample=128,
            sample_count=1024,mode="ac")
    reference.write_bytes(original[:-4])
    with pytest.raises(ValueError,match="length"):
        compare_original_getsignal_return(
            path,reference,channel=2,first_sample=128,
            sample_count=1024,mode="ac")
    reference.write_bytes(original)
    alias=tmp_path/"fake_link.bin"
    try:alias.symlink_to(reference)
    except (OSError,NotImplementedError):pytest.skip("no symlink support")
    with pytest.raises(ValueError,match="local path"):
        compare_original_getsignal_return(
            path,alias,channel=2,first_sample=128,
            sample_count=1024,mode="ac")


@pytest.mark.parametrize("channel,first,n,mode",[
    (0,0,1024,"ac"),(9,0,1024,"ac"),(True,0,1024,"ac"),
    (1,-1,1024,"ac"),(1,True,1024,"ac"),(1,0,0,"ac"),
    (1,0,262145,"ac"),(1,0,1024,"guess"),
])
def test_private_compare_refuses_unknown_metadata(tmp_path,channel,first,n,mode):
    path,reference,_=_source(tmp_path)
    with pytest.raises(ValueError):
        compare_original_getsignal_return(
            path,reference,channel=channel,first_sample=first,
            sample_count=n,mode=mode)


def test_cli_aggregate_report_never_prints_private_path_or_value(tmp_path):
    path,reference,_=_source(tmp_path)
    args=["--source-native-zip",str(path),
          "--original-getsignal-bin",str(reference),
          "--channel","2","--first-sample","128",
          "--sample-count","1024","--mode","ac"]
    f=io.StringIO()
    with redirect_stdout(f):
        assert main(args)==0
    obj=json.loads(f.getvalue())
    assert obj["float32_words_exact"]==1024
    assert str(path) not in f.getvalue()
    assert str(reference) not in f.getvalue()
    assert obj["original_same_run_identity_authenticated"] is False
