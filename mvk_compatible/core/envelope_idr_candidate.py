"""Stage111E original envelope chain: local/private coefficient loader + IDR algorithm.

Original private evidence: _Unit115 007D1158, 007D1C48, 007D1D50, 007D1E70;
the user's own mvkview.idp 0x8CD980,0x8D2A58,0x8CDA00,0x8CDA2C,0x8CDA58.

Do NOT commit/share original IDP or coefficients. A user must supply the exact
local original IDP file for coefficients to enable this candidate.
No network, Qt, FastAPI, device commands, generated approximation or hidden DSP.
Numerical parity with original x87 runtime remains UNVERIFIED.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import math
import numpy as np
from .fft_idr_candidate import mean_center_float32

# These are *derived* control settings/rates (not the proprietary FIR payload).
ENVELOPE_RATES=(1,65536,65536,65536,65536,32768,32768,32768,
 16384,16384,16384,8192,8192,8192,4096,4096,4096,2048,2048,2048,
 65536,32768,16384,8192,4096,2048,65536,32768,16384,8192,4096,2048)
ENVELOPE_STAGES=(0,1,2,3,4,2,3,4,2,3,4,2,3,4,2,3,4,2,3,4,
 5,5,5,5,5,5,6,6,6,6,6,6)
FIR_TAPS=(0,97,129,161,193,51,49,45,89,177,353)
FIR_DECIM=(0,4,4,4,8,2,1,2,4,8,16)
VALID_RATIOS=(1,2,4,8,10,20,40,80,160)
_PRIVATE_IDP_SHA256="77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438"
_PRIVATE_IMAGE_OFFSET=0x400ed8
_PRIVATE_FIR_ADDRESS=0x8cda58
_PRIVATE_FIR_FLOAT_COUNT=10*512


@dataclass(frozen=True)
class EnvelopeProfile:
    """Ten float32 FIR banks. Coefficients are *never* embedded in source."""
    banks:np.ndarray
    provenance:str="PRIVATE_PROFILE_USER_SUPPLIED"

    def __post_init__(self):
        b=np.asarray(self.banks,dtype=np.float32)
        if b.shape!=(10,512) or not np.isfinite(b).all():
            raise ValueError("Envelope profile requires ten finite 512-float32 banks")
        b=b.copy()
        b.setflags(write=False)
        object.__setattr__(self,"banks",b)

    @classmethod
    def from_original_local_idp(cls,filename:str|Path)->"EnvelopeProfile":
        """Load exact local user's IDP only on explicit request, no Git export."""
        path=Path(filename)
        if path.is_symlink() or not path.is_file() or path.stat().st_size>80_000_000:
            raise ValueError("Expected a regular local original IDP file")
        raw=path.read_bytes()
        if (not raw.startswith(b"IDR proj v.3")
            or hashlib.sha256(raw).hexdigest()!=_PRIVATE_IDP_SHA256):
            raise ValueError("Unrecognised private IDP version/fingerprint")
        off=_PRIVATE_IMAGE_OFFSET
        def integers(address,count):
            chunk=raw[address-off:address-off+count*4]
            if len(chunk)!=count*4:
                raise ValueError("Incomplete private IDP memory image")
            return tuple(int(x) for x in np.frombuffer(chunk,dtype='<u4'))
        for address,size,expected in (
            (0x8cd980,32,ENVELOPE_RATES),
            (0x8d2a58,32,ENVELOPE_STAGES),
            (0x8cda00,11,FIR_TAPS),
            (0x8cda2c,11,FIR_DECIM)):
            if integers(address,size)!=expected:
                raise ValueError("Private IDP filter metadata mismatch")
        begin=_PRIVATE_FIR_ADDRESS-off
        end=begin+_PRIVATE_FIR_FLOAT_COUNT*4
        if begin<0 or end>len(raw):
            raise ValueError("Private IDP FIR bank outside memory image")
        banks=np.frombuffer(raw[begin:end],dtype='<f4').reshape(10,512).copy()
        return cls(banks,provenance="USER_SUPPLIED_LOCAL_IDP_SHA256_VERIFIED")

    def bank(self,index:int)->np.ndarray:
        if not 1<=index<=10:
            raise ValueError("Invalid FIR stage index")
        return self.banks[index-1]


def envelope_plan(signal_length:int,sample_rate:int,code:int)->dict:
    """IDR 007D1158: adjusted input length, stages and reported output rate.

    NOTE original uses uint32 integer division for sample_rate / target and
    returns a length of input requested from history, not the final sample count.
    """
    if not isinstance(signal_length,int) or signal_length<=0 or signal_length>2_000_000:
        raise ValueError("Signal length outside safe offline bounds")
    if not isinstance(sample_rate,int) or sample_rate<=0 or sample_rate>10_000_000:
        raise ValueError("Invalid integer sample rate")
    if not isinstance(code,int) or not 1<=code<=31:
        raise ValueError("EnvelopeCode must be 1..31")
    target=ENVELOPE_RATES[code]
    ratio=sample_rate//target
    if ratio not in VALID_RATIOS:
        raise ValueError(f"Original Delphi Invalid sample rate: ratio {ratio}")
    stage=ENVELOPE_STAGES[code]
    pre_stage={1:None,2:7,4:8,8:9,10:10,
               20:7,40:8,80:9,160:10}[ratio]
    second_stage=10 if ratio in (20,40,80,160) else None
    # 007D118F: extra historical length for second-stage filter.
    offset=353 if second_stage is not None else 0
    offset={1:offset,2:offset*2+45,4:offset*4+89,
            8:offset*8+177,10:offset*16+353,
            20:offset*2+45,40:offset*4+89,
            80:offset*8+177,160:offset*16+353}[ratio]
    adjusted=signal_length+offset+FIR_TAPS[stage]*FIR_DECIM[stage]
    if adjusted>2_000_000:
        raise ValueError("Adjusted envelope length exceeds configured offline bound")
    return {'code':code,'sample_rate_hz':sample_rate,'target_rate':target,
            'ratio':ratio,'stage':stage,'pre_stage':pre_stage,
            'second_stage':second_stage,'adjusted_input_length':adjusted,
            'history_padding':adjusted-signal_length,
            'reported_output_rate_hz':target//FIR_DECIM[stage],
            'source':'APP_DERIVED_ENVELOPE_LENGTH_IDR_CANDIDATE'}


def _fir_step(data:np.ndarray,stage:int,profile:EnvelopeProfile,*,quadrature:bool)->np.ndarray:
    taps,step=FIR_TAPS[stage],FIR_DECIM[stage]
    if len(data)<taps+step:
        raise ValueError("Original Delphi Invalid signal length for envelope/decimation")
    n=(len(data)-taps)//step
    idx=(np.arange(n,dtype=np.int64)+1)*step-1+taps
    bank=profile.bank(stage)
    # Original accumulator is stored to float32 after every tap (x87 FSTP).
    i=np.zeros(n,dtype=np.float32)
    q=np.zeros(n,dtype=np.float32) if quadrature else None
    for j in range(taps):
        x=data[idx-j].astype(np.float64)
        i=np.asarray(i.astype(np.float64)+float(bank[2*j] if quadrature else bank[j])*x,dtype=np.float32)
        if quadrature:
            q=np.asarray(q.astype(np.float64)+float(bank[2*j+1])*x,dtype=np.float32)
    if quadrature:
        return np.asarray(np.sqrt(i.astype(np.float64)**2+q.astype(np.float64)**2),dtype=np.float32)
    return i


def process_original_envelope_candidate(
    samples:np.ndarray,sample_rate:int,code:int,profile:EnvelopeProfile,
    *,f_range:float=1.0
)->dict:
    """IDR: NoDC -> optional decimators -> I/Q FIR -> sqrt(I²+Q²) -> FRange.

    True historical input must be supplied; NEVER silently zero-pad an
    incomplete archive. The GetSignal result array is reversed, like Delphi.
    """
    if not isinstance(profile,EnvelopeProfile):
        raise ValueError("Private coefficient profile is required; no approximation")
    if not math.isfinite(f_range) or f_range<=0:
        raise ValueError("Invalid original FRange")
    raw=np.asarray(samples,dtype=np.float32)
    if raw.ndim!=1 or not len(raw) or not np.isfinite(raw).all():
        raise ValueError("Envelope input must be finite float32 1D samples")
    plan=envelope_plan(len(raw),sample_rate,code)
    centered,removed_mean=mean_center_float32(raw)
    step_data=centered
    if plan['pre_stage']:
        step_data=_fir_step(step_data,plan['pre_stage'],profile,quadrature=False)
    if plan['second_stage']:
        step_data=_fir_step(step_data,plan['second_stage'],profile,quadrature=False)
    result=_fir_step(step_data,plan['stage'],profile,quadrature=True)
    output=np.asarray(result.astype(np.float64)*f_range,dtype=np.float32)
    rms=float(np.float32(np.sqrt(np.mean(result.astype(np.float64)**2))*f_range))
    return {'chronological':output,'getsignal_buffer':output[::-1].copy(),
            'rms_m_s2':rms,'removed_mean_m_s2':removed_mean,
            'output_samples':len(output),
            'output_sample_rate_hz':plan['reported_output_rate_hz'],
            'stages_used':tuple(x for x in (plan['pre_stage'],plan['second_stage'],plan['stage']) if x),
            'source':'APP_DERIVED_ENVELOPE_IDR_PRIVATE_COEFFICIENT_CANDIDATE',
            'profile_source':profile.provenance,
            'original_executable_numerical_parity_verified':False,
            'warning':'Original FIR samples from user-supplied local IDP; x87 rounding, window position, TQGrapher and original comparison not certified'}
