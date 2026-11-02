"""Stage111Z29C1 source instruction oracle; SYNTHETIC coefficients only.

Never checkout user's IDP or instrument captures into GitHub/CI.
"""
from __future__ import annotations

import numpy as np
import pytest

from mvk_compatible.core.envelope_fir_source_audit import (
    SCHEMA, audit_envelope_source_chain, audit_local_fir_stage,
    original_fir_instruction_oracle,
)
from mvk_compatible.core.envelope_idr_candidate import EnvelopeProfile,_fir_step


def _coeff(seed=41):
    rng=np.random.default_rng(seed)
    # Entire array is synthetic, not any original FIR coefficient.
    b=rng.uniform(-.07,.07,size=(10,512)).astype("<f4")
    return EnvelopeProfile(b,provenance="SYNTHETIC_RANDOM_FIR_QA_ONLY")


@pytest.mark.parametrize("stage,quadrature,n",[
    (1,True,1024),(4,True,1024),(5,True,512),
    (7,False,1024),(8,False,1024),(9,False,1024),
    (10,False,1024)
])
def test_scalar_original_instruction_order_bitwise_matches_optimized(stage,quadrature,n):
    rng=np.random.default_rng(218)
    x=(rng.uniform(-9,9,size=n)+1.25).astype("<f4")
    profile=_coeff()
    snapshot=x.tobytes()
    scalar=original_fir_instruction_oracle(x,stage,profile,quadrature=quadrature)
    optimized=_fir_step(x,stage,profile,quadrature=quadrature)
    assert scalar.dtype==optimized.dtype==np.float32
    assert scalar.tobytes()==optimized.tobytes()
    assert x.tobytes()==snapshot
    evidence=audit_local_fir_stage(x,stage,profile,quadrature=quadrature)
    assert evidence["schema"]==SCHEMA
    assert evidence["float32_source_instruction_total_words"]==len(scalar)
    assert evidence["float32_source_instruction_exact_words"]==len(scalar)
    assert evidence["bitwise_local_oracle_vs_optimized"]
    assert evidence["original_delphi_runtime_ulp_parity_verified"] is False
    assert evidence["private_coefficient_or_measurement_values_in_report"] is False


@pytest.mark.parametrize("code,fs,n,expected",[
    (1,65536,4193,(1,)),   # independent FIR envelope
    (5,65536,5000,(7,2)), # first decimation + I/Q
    (20,65536,2099,(5,)), # 2x effective envelope rate
    (20,20*65536,3000,(7,10,5)), # 2 decimators + I/Q
])
def test_entire_source_chain_matches_optimized_without_input_mutation(
    code,fs,n,expected
):
    rng=np.random.default_rng(1024+code)
    x=(5.3+rng.standard_normal(n)).astype("<f4")
    original=x.tobytes()
    report=audit_envelope_source_chain(
        x,fs,code,_coeff(),f_range=2.5)
    assert report["schema"]==SCHEMA
    assert report["stages"]==expected
    assert report["local_independent_scalar_vs_optimized_bitwise"]
    assert report["all_source_stages_bitwise"]
    assert report["original_runtime_output_dump_compared"] is False
    assert report["original_x87_full_precision_parity_verified"] is False
    assert not report["source_original_idp_coefficients_embedded"]
    assert x.tobytes()==original


@pytest.mark.parametrize("bad,stage",[
    ([1.,2.,3.],5),([float("nan")]*4096,1),
    ([float("inf")]*1024,1),([1.]*6100,1),
])
def test_source_scalar_refuses_invalid_input(bad,stage):
    with pytest.raises(ValueError,match="SOURCE_FIR"):
        original_fir_instruction_oracle(
            bad,stage,_coeff(),quadrature=stage==1)


def test_source_scalar_requires_valid_stage_and_profile():
    x=np.ones(1024,dtype="<f4")
    for s in (0,11,True,"1"):
        with pytest.raises(ValueError,match="stage"):
            original_fir_instruction_oracle(x,s,_coeff(),quadrature=False)
    with pytest.raises(ValueError,match="profile"):
        original_fir_instruction_oracle(x,1,None,quadrature=True)
    with pytest.raises(ValueError,match="FRange"):
        audit_envelope_source_chain(x,65536,1,_coeff(),f_range=0)
