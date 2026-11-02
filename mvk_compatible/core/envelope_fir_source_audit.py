"""Stage111Z29C1: independently written scalar oracle for original FIR stages.

Source evidence: original _Unit115:007D1D50..007D1E0F (decimator)
and _Unit115:007D1E70..007D1F7B (paired I/Q + sqrt).
No original IDP coefficient bytes or user waveforms are stored here.

This is a *source instruction* audit of local candidates, NOT an original
Delphi execution and NOT an independent numerical runtime golden. Both
reconstructions approximate x87 intermediate precision with float64 product
followed by original explicit FSTP Single at each accumulator update.
"""
from __future__ import annotations

import hashlib
import math
import numpy as np

from .envelope_idr_candidate import (
    EnvelopeProfile, FIR_DECIM, FIR_TAPS, _fir_step, envelope_plan,
    process_original_envelope_candidate,
)
from .fft_idr_candidate import mean_center_float32

SCHEMA = "MVK_GETSIGNAL_ORIGINAL_SOURCE_FIR_SCALAR_AUDIT_V1"
MAX_AUDIT_INPUT = 6000


def original_fir_instruction_oracle(
    source, stage: int, profile: EnvelopeProfile, *, quadrature: bool
) -> np.ndarray:
    """Scalar implementation with original tap/order and FSTP boundaries.

    x87 DECOMPILED LOOP:
    output j uses sample at ((j+1)*decim -1 + taps - k);
    non-IQ coeff word k; I/Q pair words 2*k and 2*k+1.
    Internal I and Q are rounded to Float32 after EVERY product-plus-sum.
    The final hypot is rounded to Float32 once after sqrt.
    """
    if type(stage) is not int or not 1 <= stage <= 10:
        raise ValueError("SOURCE_FIR: stage must be 1..10")
    if not isinstance(profile, EnvelopeProfile):
        raise ValueError("SOURCE_FIR: explicit local coefficient profile required")
    x = np.asarray(source, dtype=np.float32)
    taps, stride = FIR_TAPS[stage], FIR_DECIM[stage]
    if (x.ndim != 1 or x.size > MAX_AUDIT_INPUT or
            x.size < taps+stride or not bool(np.isfinite(x).all())):
        raise ValueError("SOURCE_FIR: finite, bounded full input required")
    if quadrature and taps*2 > 512:
        raise ValueError("SOURCE_FIR: I/Q coefficient bank would exceed original table")
    coefficient = profile.bank(stage)
    samples_out = (len(x)-taps)//stride
    answer = np.empty(samples_out, dtype=np.float32)
    for j in range(samples_out):
        tail = (j+1)*stride - 1 + taps
        acc_i = np.float32(0.0)
        acc_q = np.float32(0.0)
        for k in range(taps):
            s = float(x[tail-k])
            if quadrature:
                # 007D1F1B/007D1F44: FSTP Single after every tap
                acc_i = np.float32(float(acc_i) + float(coefficient[2*k])*s)
                acc_q = np.float32(float(acc_q) + float(coefficient[2*k+1])*s)
            else:
                # 007D1DF2/007D1DF5: single stored scalar accumulator
                acc_i = np.float32(float(acc_i) + float(coefficient[k])*s)
        if quadrature:
            # 007D1F52–1F6D: square/plus/Sqrt then FSTP output Single
            answer[j] = np.float32(math.sqrt(
                float(acc_i)**2 + float(acc_q)**2))
        else:
            answer[j] = acc_i
    return answer


def _bits(x):
    return np.asarray(x,dtype=np.float32).view(np.uint32)


def audit_local_fir_stage(source, stage:int, profile:EnvelopeProfile,
                          *, quadrature:bool)->dict:
    """Return aggregate comparison; never disclose private FIR coefficients."""
    x=np.asarray(source,dtype=np.float32)
    oracle=original_fir_instruction_oracle(
        x,stage,profile,quadrature=quadrature)
    candidate=_fir_step(x,stage,profile,quadrature=quadrature)
    if len(oracle)!=len(candidate):
        raise ValueError("SOURCE_FIR: original and optimized output lengths differ")
    expected=_bits(oracle)
    got=_bits(candidate)
    matched=expected==got
    # Original numerical runtime has NOT been sampled; only two local
    # implementations of the IDR instruction ordering are compared.
    return {
        "schema":SCHEMA,
        "source_code_range":(
            "UNIT115_007D1E70_007D1F7B_IQ" if quadrature
            else "UNIT115_007D1D50_007D1E0F_DECIMATION"
        ),
        "stage":stage,
        "quadrature":quadrature,
        "input_sample_count":len(x),
        "output_sample_count":len(oracle),
        "float32_source_instruction_exact_words":int(matched.sum()),
        "float32_source_instruction_total_words":len(oracle),
        "bitwise_local_oracle_vs_optimized":bool(np.all(matched)),
        "local_profile_source":profile.provenance,
        "original_delphi_runtime_ulp_parity_verified":False,
        "original_live_adc_ring_position_verified":False,
        "private_coefficient_or_measurement_values_in_report":False,
    }


def audit_envelope_source_chain(source, sample_rate:int, code:int,
                                profile:EnvelopeProfile, *,
                                f_range:float=1.0)->dict:
    """Trace *all* stages of one bounded original FIR chain independently.

    Source-centering is the already verified 007D2344 candidate. This
    deliberately does NOT create or certify an original runtime snapshot.
    """
    x=np.asarray(source,dtype=np.float32)
    if (x.ndim!=1 or not 0<len(x)<=MAX_AUDIT_INPUT or
            not bool(np.isfinite(x).all()) or
            not math.isfinite(f_range) or f_range<=0):
        raise ValueError("SOURCE_FIR: invalid bounded input or FRange")
    plan=envelope_plan(len(x),sample_rate,code)
    stages=tuple(
        s for s in (plan["pre_stage"],plan["second_stage"],plan["stage"]) if s
    )
    centered,_=mean_center_float32(x)
    reference=centered
    audit=[]
    for i,stage in enumerate(stages):
        is_quadrature=(i==len(stages)-1)
        details=audit_local_fir_stage(
            reference,stage,profile,quadrature=is_quadrature)
        audit.append(details)
        reference=original_fir_instruction_oracle(
            reference,stage,profile,quadrature=is_quadrature)
    output=np.asarray(reference.astype(np.float64)*f_range,dtype=np.float32)
    optimized=process_original_envelope_candidate(
        x,sample_rate,code,profile,f_range=f_range)["chronological"]
    if len(output)!=len(optimized):
        raise ValueError("SOURCE_FIR: candidate and scalar output lengths differ")
    bit_equal=np.array_equal(_bits(output),_bits(optimized))
    return {
        "schema":SCHEMA,
        "signal_length":len(x),
        "code":code,
        "sample_rate_hz":sample_rate,
        "stages":stages,
        "stage_comparisons":audit,
        "source_centering":"EXISTING_UNIT115_007D2344_FLOAT32_CANDIDATE",
        "output_sample_count":len(output),
        "local_independent_scalar_vs_optimized_bitwise":bool(bit_equal),
        "all_source_stages_bitwise":all(
            item["bitwise_local_oracle_vs_optimized"] for item in audit
        ),
        "source_original_idp_coefficients_embedded":False,
        "original_runtime_output_dump_compared":False,
        "original_x87_full_precision_parity_verified":False,
        "original_end_of_history_selected_correctly_verified":False,
    }
