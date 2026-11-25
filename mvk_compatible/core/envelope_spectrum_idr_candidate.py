"""Stage111F: original-structure envelope -> FFT chain, OFFLINE candidate only.

PRIVATE Delphi evidence: _Unit115 GetSpectrum 007D13D4..007D17E7.
007D14B3 removes float32 mean from RAW data ONCE, then optional 007D1C48
decimators and 007D1E70 I/Q magnitude, then 007D1FE8 Hann/FFT.
NO second mean subtraction after the positive envelope. Lower bins zeroed
per Max(2, Round(N/(2*output_fs))); modes 2/3 apply original 007D2164
power-domain integration once/twice. Original x87 parity remains unverified.

Original FIR coefficient payload is NOT in this module/repository:
provide explicitly verified local EnvelopeProfile from user's IDP.
"""
from __future__ import annotations
import hashlib
import math
import numpy as np
from .envelope_idr_candidate import (EnvelopeProfile, envelope_plan,
    process_original_envelope_candidate, FIR_TAPS, FIR_DECIM)
from .fft_idr_candidate import check_n, idr_power_spectrum
from .spectrum_display_source import source_derived_mode_display
from .calibration_candidate import resolve_f_range
from .storage_f_range_idr_candidate import (
    prepare_original_fft_input, DOMAIN_CALIBRATED_BIN, DOMAIN_ORIGINAL_STORAGE)
from .spectrum_metrics_idr_candidate import original_spectrum_summary

SOURCE='APP_DERIVED_ENVELOPE_SPECTRUM_IDR_CANDIDATE'
# Original private MVKView 1.0.47 IDP 007D219C contains an 80-bit
# Extended literal: 159.154943091895335768870545223308.
# The old 159.154943091895 value was TRUNCATED (not source-exact).
# Numerical constant only; never publish source bytes or private files.
_INTEGRATION_CONSTANT_EXTENDED_DECIMAL="159.154943091895335768870545223308"
_INTEGRATION_CONSTANT=float(_INTEGRATION_CONSTANT_EXTENDED_DECIMAL)
_MODE_UNITS=('дБ, IDR-кандидат','м/с²','мм/с','мкм')


def required_original_history(n_fft:int, sample_rate:int, code:int)->dict:
    """Reverse FIR length recurrences for EXACTLY N power-of-two FFT samples.

    This INVERSE is an independent Stage111F calculation, distinct from
    GetAdjustedEnvelopeLength. Original archive-end/window selection still
    requires MVKView comparison. Never use zero padding or truncate output.
    """
    n=check_n(n_fft)
    # bSpecLines is PRE-FIR. The source FFT executes on Params.Count
    # AFTER FIR/decimation, which can legitimately fall below 1024.
    # N=4 is reachable at 65536/2048 and I/Q decimation 8.
    # Original 007D1801 skips the empty summary interval and returns zero.
    if n<4:
        raise ValueError('Source post-FIR FFT requires at least 4 samples')
    dummy=envelope_plan(1,sample_rate,code)
    stages=tuple(t for t in
        (dummy['pre_stage'],dummy['second_stage'],dummy['stage']) if t)
    length=n
    for stage in reversed(stages):
        length=length*FIR_DECIM[stage]+FIR_TAPS[stage]
        if length>2_000_000:
            raise ValueError('Unreasonably long required source history; not available')
    return {'n_fft':n,'sample_rate_hz':sample_rate,'code':code,
            'input_samples':length,'stages':stages,
            'output_sample_rate_hz':dummy['reported_output_rate_hz'],
            'fft_df_hz':dummy['reported_output_rate_hz']/n,
            'length_derivation':'INVERTED_FIR_RECURRENCES_RESEARCH_ONLY',
            'original_window_selection_verified':False}


def source_selected_envelope_fft_plan(selected_bspec_lines_n:int,
                                      sample_rate:int,code:int)->dict:
    """Delphi 007D1462: bSpecLines is PRE-FIR length, not final FFT N.

    Calls source GetAdjustedEnvelopeLength(Params.Count,EnvelopeCode);
    007D1C48 decimates in place; 007D1E70 runs analytic I/Q FIR
    and mutates Params.Count. 007D1FE8 THEN FFTs Params.Count.
    All source-derived control lengths: not original Win32 sample parity.
    """
    # Original _Unit128.pas bSpecLines has an exact sparse menu:
    # 2048 is a power of two but it is NOT an original bSpecLines Tag.
    if (type(selected_bspec_lines_n) is not int or
            selected_bspec_lines_n not in
            (1024,4096,8192,16384,32768,65536,131072,262144)):
        raise ValueError("Invalid original bSpecLines menu N")
    selected=check_n(selected_bspec_lines_n)
    info=envelope_plan(selected,sample_rate,code)
    stages=tuple(x for x in (
        info["pre_stage"],info["second_stage"],info["stage"]) if x)
    source_count=info["adjusted_input_length"]
    count=source_count
    states=[]
    for stage in stages:
        taps=FIR_TAPS[stage]
        decim=FIR_DECIM[stage]
        if count<taps+decim:
            raise ValueError("Original GetSpectrum lacks full FIR input")
        next_count=(count-taps)//decim
        states.append({"stage":stage,"input_count":count,"taps":taps,
                       "decimation":decim,"output_count":next_count})
        count=next_count
    if count<2 or count>262144 or count&(count-1):
        raise ValueError("Original source FIR produced unsupported radix-2 FFT count")
    reverse=count
    for stage in reversed(stages):
        reverse=reverse*FIR_DECIM[stage]+FIR_TAPS[stage]
    if reverse!=source_count:
        # Exact integer inverse for the hexadecimal source ratio table.
        raise ValueError("Source GetAdjustedLength and FIR inverse disagree")
    fs_out=info["reported_output_rate_hz"]
    if fs_out*selected!=sample_rate*count:
        raise ValueError("Source FIR output Fs/N is not original frequency grid")
    return {
        "original_bSpecLines_pre_fir_n":selected,
        "source_getadjusted_length_samples":source_count,
        "source_fir_stage_lengths":tuple(states),
        "original_params_count_after_fir":count,
        "post_fir_fft_n":count,
        "post_fir_sample_rate_hz":fs_out,
        "post_fir_df_hz":fs_out/count,
        "input_rate_hz":sample_rate,
        "envelope_code":code,
        "output_power_bins":count//2,
        "source_params_count_proven_by_pascal":True,
        "original_runtime_post_fir_float32_verified":False,
        "original_x87_hann_fft_power_parity_verified":False,
        "source":"_Unit115.pas:007D1158-007D1230/007D1462-007D1546",
    }


def source_selected_envelope_spectrum_candidate(
        source_ring_samples:np.ndarray,sample_rate:int,code:int,
        profile:EnvelopeProfile,*,selected_bspec_lines_n:int,
        mode:int=1,backend:str="idr_float32",
        f_range:float=1.0,
        input_domain:str=DOMAIN_CALIBRATED_BIN)->dict:
    """Compute FIR/IQ candidate from exact real PRE-FIR source-ring window.

    Selected bSpecLines is BEFORE FIR, while n_fft is AFTER FIR.
    Refuses any missing/padded history and does not mutate the RAW/BIN.
    """
    plan=source_selected_envelope_fft_plan(
        selected_bspec_lines_n,sample_rate,code)
    source=np.asarray(source_ring_samples,dtype=np.float32)
    if (source.ndim!=1 or len(source)!=plan["source_getadjusted_length_samples"]
            or not np.isfinite(source).all()):
        raise ValueError("Exact source GetAdjustedEnvelopeLength window required")
    if plan["post_fir_fft_n"]<4:
        raise ValueError("Post-FIR FFT below the supported original menu range")
    outcome=envelope_spectrum_idr_candidate(
        source,sample_rate,code,profile,
        n_fft=plan["post_fir_fft_n"],mode=mode,
        backend=backend,f_range=f_range,input_domain=input_domain)
    if (outcome["source_history_samples"]!=len(source) or
            outcome["n_fft"]!=plan["post_fir_fft_n"] or
            outcome["output_samples"]!=plan["post_fir_fft_n"]):
        raise ValueError("Source GetSpectrum FIR output and FFT window mismatch")
    return {**outcome,
            "source":"SOURCE_SELECTED_GETSPECTRUM_FIR_IQ_IDR_CANDIDATE",
            "source_bSpecLines_pre_fir_n":selected_bspec_lines_n,
            "original_source_fft_plan":plan,
            "calibrated_go_ring_input":input_domain==DOMAIN_CALIBRATED_BIN,
            "source_verified_go_ring_required":True,
            "original_delphi_numerical_parity_verified":False}


def _delphi_integration_power(power:np.ndarray, n:int, fs_out:int,
                              repetitions:int)->np.ndarray:
    """007D2164: each integration multiplies P[k] by (159.15494/f[k])**2.

    Original uses an Extended literal then float32 stores at each pass.
    Bin zero is set to zero prior to the division by bin number.
    """
    p=np.asarray(power,dtype=np.float32).copy()
    if p.ndim!=1 or len(p)!=n//2 or fs_out<=0 or repetitions not in (1,2):
        raise ValueError('Invalid original integration configuration')
    # 007D16A7/007D1731 passes a stored Single(N/Fs) into 007D2164.
    # In each bin: (ExtendedConstant/k * storedSingleInverseDf)^2,
    # multiplying power and FSTP Single-storing after EACH pass.
    inverse_df=np.float32(float(n)/float(fs_out))
    if not np.isfinite(inverse_df) or inverse_df<=0:
        raise ValueError("Original integration reciprocal df invalid")
    # Original 007D2179..2192: Extended constant / bin * stored
    # Single(N/Fs), square in Extended, multiply Power Single, FSTP Single
    # after EACH pass. GNU x86 NumPy longdouble has 64-bit significand;
    # Windows NumPy may alias to binary64. Do NOT label that fallback
    # exact Win32 x87 runtime parity.
    precision=(np.longdouble if
        np.finfo(np.longdouble).nmant>np.finfo(np.float64).nmant
        else np.float64)
    bins=np.arange(1,len(p),dtype=precision)
    factors=np.zeros(len(p),dtype=precision)
    const=precision(_INTEGRATION_CONSTANT_EXTENDED_DECIMAL)
    product=(const/bins)*precision(inverse_df)
    factors[1:]=product*product
    for _ in range(repetitions):
        with np.errstate(over='ignore',invalid='ignore'):
            p=np.asarray(p.astype(precision)*factors,dtype=np.float32)
        if not np.isfinite(p).all():
            raise ValueError("Original spectrum integration overflows Float32")
    return p


def envelope_spectrum_idr_candidate(samples:np.ndarray,sample_rate:int,code:int,
                                    profile:EnvelopeProfile,*,n_fft:int=4096,
                                    mode:int=1,backend:str='idr_float32',
                                    f_range:float=1.0,
                                    input_domain:str=DOMAIN_CALIBRATED_BIN)->dict:
    """No silent data changes: require exact FIR history for exact FFT N.

    Supports original modes 0..3 with source-based 007D2164 conversion.
    All values remain APP_DERIVED_CANDIDATE, NEVER original instrument DSP.
    """
    if mode not in range(4):
        raise ValueError('Original spectrum modes are 0..3')
    if not math.isfinite(f_range) or f_range<=0:
        raise ValueError('FRange must be positive and finite')
    f_range,_=resolve_f_range(f_range)
    if not isinstance(profile,EnvelopeProfile):
        raise ValueError('Original local IDP EnvelopeProfile is mandatory')
    plan=required_original_history(n_fft,sample_rate,code)
    a=np.asarray(samples,dtype=np.float32)
    if a.ndim!=1 or len(a)!=plan['input_samples'] or not np.isfinite(a).all():
        raise ValueError('Exact recorded FIR input length is required; no padding/truncation')
    # Stage111J original _Unit115:007D14A5 -> 007D2228(flag=1):
    # Float32 ring storage (ONLY if that original storage domain is proven)
    # is read as Single(Single(buffer_value)/FRange) BEFORE RemoveMean/FIR.
    # Reuse the EXACT normal-GetSpectrum domain helper already tested;
    # never infer source storage type from a Native R6 calibrated BIN.
    prepared=prepare_original_fft_input(
        a,f_range=f_range,input_domain=input_domain)
    pre_fir_read=prepared['samples_before_dc_removal']
    pre_fir_read_float32_sha256=hashlib.sha256(
        np.asarray(pre_fir_read,dtype='<f4').tobytes()).hexdigest()
    # Original GetSpectrum's pre-FIR f32 mean is removed exactly once.
    env=process_original_envelope_candidate(
        pre_fir_read,sample_rate,code,profile,f_range=1.)
    transformed=np.asarray(env['chronological'],dtype=np.float32)
    if len(transformed)!=n_fft:
        raise ValueError('FIR output length does not match FFT N; operation refused')
    # The array passed DIRECTLY into original-inspired Hann/FFT is NOT
    # the input BIN, not the reversed GetSignal return, and not a second
    # mean-centered array. Its SHA can be compared privately to an x32dbg
    # snapshot at 007D1FE8 without disclosing any user signal samples.
    fft_input_float32_sha256=hashlib.sha256(
        np.asarray(transformed,dtype='<f4').tobytes()).hexdigest()
    # IMPORTANT: 007D14B3 is BEFORE filtering, no second call to 007D2344.
    power, second_removed=idr_power_spectrum(transformed,backend,remove_dc=False)
    assert second_removed==0.0
    fs_out=int(env['output_sample_rate_hz'])
    low=max(2,round(n_fft/(2.0*fs_out)))
    if low>len(power):
        raise ValueError('Invalid lower-band cutoff for FFT output rate')
    p=np.asarray(power,dtype=np.float32).copy()
    p[:low]=0
    if mode in (2,3):
        p=_delphi_integration_power(p,n_fft,fs_out,mode-1)
    spectrum_summary=original_spectrum_summary(p,n_fft=n_fft,fs_out=fs_out,
                                                f_range=f_range,spectrum_mode=mode)
    frequency=np.arange(n_fft//2,dtype=np.float64)*(fs_out/n_fft)
    # Original GetSpectrum writes Float32 Y for ALL modes, including log.
    amplitude=source_derived_mode_display(p,n_fft=n_fft,mode=mode,
                                         f_range=f_range).astype(np.float64)
    return {'source':SOURCE,'fft_backend':backend,
            'channel_source':(
                'RESEARCH_ASSUMED_ORIGINAL_FLOAT_STORAGE' if
                input_domain==DOMAIN_ORIGINAL_STORAGE else 'MVK_ADC_CALIBRATED_BIN'),
            'input_domain':input_domain,
            'original_storage_read_divided_by_range':
                prepared['original_storage_read_divided_by_range'],
            'original_source_buffer_provenance_verified':False,
            'calibrated_native_bin_is_original_storage_verified':False,
            'pre_fir_read_float32_sha256':pre_fir_read_float32_sha256,
            'pre_fir_read_sample_count':len(pre_fir_read),
            'pre_fir_read_is_original_runtime_verified':False,
            'n_fft':n_fft,'mode':mode,'unit':_MODE_UNITS[mode],
            'frequency_hz':frequency.tolist(),'amplitude':amplitude.tolist(),
            'df_hz':fs_out/n_fft,'output_sample_rate_hz':fs_out,
            'f_range_used':float(f_range),'original_f_range_verified':False,
            'spectrum_summary':spectrum_summary,
            'low_bins_zeroed':low,'source_history_samples':len(a),
            'envelope_stages':plan['stages'],'output_samples':len(transformed),
            'raw_mean_removed_m_s2':env['removed_mean_m_s2'],
            'mean_subtraction_count':1,'fft_second_mean_subtraction':False,
            'pre_fft_envelope_float32_sha256':fft_input_float32_sha256,
            'pre_fft_envelope_samples':len(transformed),
            'pre_fft_envelope_is_unreversed_chronological':True,
            'original_pre_fft_envelope_runtime_parity_verified':False,
            'private_coefficient_source':profile.provenance,
            'power_integration_passes':max(0,mode-1),
            'log10_helper_source_verified':True,
            'display_float32_intermediate_source_model':True,
            'original_display_y_runtime_parity_verified':False,
            'original_delphi_numerical_parity_verified':False,
            'original_window_selection_verified':False,
            'warning':(
                'Source-verified original float-ring /FRange applied BEFORE FIR, '
                'but choosing Native BIN as original storage is unverified; '
                'real same-run original Win32 pre-FIR and pre-FFT buffers missing'
                if input_domain==DOMAIN_ORIGINAL_STORAGE else
                'Native calibrated BIN left unchanged before FIR; '
                'original Delphi Float32 ring identity/FRange and runtime parity unverified')}
