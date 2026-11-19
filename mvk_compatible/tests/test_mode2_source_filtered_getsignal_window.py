"""Original HTag-selected LIVE filtered GetSignal, synthetic only.

No private FIR banks, IDP, RAW/PCAP or physical MVK01. Local -3 IPC
is never an instrument command or a Delphi HTag.
"""
from __future__ import annotations

from hashlib import sha256
import json
import numpy as np
import pytest

from mvk_compatible.core.original_source_long_window import (
    REQUEST_NAME,submit_source_getsignal_envelope_window,
    load_source_long_window,
)
from mvk_compatible.core.envelope_idr_candidate import (
    EnvelopeProfile,process_original_envelope_candidate,envelope_plan,
)
from .test_stage111z31fj_original_long_window import (
    long_source_status,response_fixture,
)

@pytest.mark.parametrize("code,expected,post,fs",[
    (20,1361,655,32768),(1,1407,327,16384),(26,1359,1310,65536)])
def test_filtered_getsignal_uses_original_hscale_extra_history(
        tmp_path,code,expected,post,fs):
    root,status=long_source_status(tmp_path)
    req=submit_source_getsignal_envelope_window(
        root,status,1,9,code,
        request_id="0123456789abcdef0123456789abcdef")
    assert req is not None and req.h_tag==-3
    assert req.original_h_tag==9 and req.original_bspec_lines==0
    assert req.samples==expected
    selected=65536*20//1000
    assert envelope_plan(selected,65536,code)["adjusted_input_length"]==expected
    cmd=json.loads((root/REQUEST_NAME).read_text())
    assert cmd["source_h_tag"]==-3 and cmd["original_h_tag"]==9
    assert cmd["envelope_code"]==code and cmd["samples"]==expected
    assert load_source_long_window(root,status,req) is None
    payload=response_fixture(root,status,req,
        override=lambda m:m.update(original_h_tag=9))
    window=load_source_long_window(root,status,req)
    assert window is not None
    samples=window.preview.channels[1].samples
    assert samples.tobytes()==payload
    assert sha256(payload).hexdigest()==window.preview.channels[1].sha256
    synthetic=EnvelopeProfile(np.zeros((10,512),dtype="<f4"),
                              provenance="SYNTHETIC_QA_ONLY")
    calculated=process_original_envelope_candidate(
        samples,65536,code,synthetic,f_range=1.)
    assert calculated["output_samples"]==post
    assert calculated["output_sample_rate_hz"]==fs
    assert np.array_equal(
        calculated["getsignal_buffer"],
        calculated["chronological"][::-1])
    assert calculated["original_executable_numerical_parity_verified"] is False

def test_filtered_getsignal_refuses_forged_htag_short_history(tmp_path):
    root,status=long_source_status(tmp_path)
    req=submit_source_getsignal_envelope_window(root,status,1,9,20)
    response_fixture(root,status,req,override=lambda m:m.update(original_h_tag=8))
    with pytest.raises(ValueError,match="malformed source window"):
        load_source_long_window(root,status,req)
    status["source_original_storage"]["channels"][0]["available_elements"]=1310
    assert submit_source_getsignal_envelope_window(
        root,status,1,9,20) is None
    with pytest.raises(ValueError):
        submit_source_getsignal_envelope_window(root,status,1,14,20)
    with pytest.raises(ValueError):
        submit_source_getsignal_envelope_window(root,status,1,9,0)
    with pytest.raises(ValueError):
        submit_source_getsignal_envelope_window(root,status,1,9,24)
