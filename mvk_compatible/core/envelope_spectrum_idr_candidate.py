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
import math
import numpy as np
from .envelope_idr_candidate import (EnvelopeProfile, envelope_plan,
    process_original_envelope_candidate, FIR_TAPS, FIR_DECIM)
from .fft_idr_candidate import check_n, idr_power_spectrum

SOURCE='APP_DERIVED_ENVELOPE_SPECTRUM_IDR_CANDIDATE'
_INTEGRATION_CONSTANT=159.154943091895  # original 007D217C Extended 1000/(2*pi), documented
_MODE_UNITS=('дБ, IDR-кандидат','м/с²','мм/с','мкм')


def required_original_history(n_fft:int, sample_rate:int, code:int)->dict:
    """Reverse FIR length recurrences for EXACTLY N power-of-two FFT samples.

    This INVERSE is an independent Stage111F calculation, distinct from
    GetAdjustedEnvelopeLength. Original archive-end/window selection still
    requires MVKView comparison. Never use zero padding or truncate output.
    """
    n=check_n(n_fft)
    if n<1024:
        raise ValueError('Original visual spectrum minimum FFT N is 1024')
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


def _delphi_integration_power(power:np.ndarray, n:int, fs_out:int,
                              repetitions:int)->np.ndarray:
    """007D2164: each integration multiplies P[k] by (159.15494/f[k])**2.

    Original uses an Extended literal then float32 stores at each pass.
    Bin zero is set to zero prior to the division by bin number.
    """
    p=np.asarray(power,dtype=np.float32).copy()
    if p.ndim!=1 or len(p)!=n//2 or fs_out<=0 or repetitions not in (1,2):
        raise ValueError('Invalid original integration configuration')
    freq=np.arange(len(p),dtype=np.float64)*(float(fs_out)/n)
    factor=np.zeros(len(p),dtype=np.float64)
    factor[1:]=(_INTEGRATION_CONSTANT/freq[1:])**2
    for _ in range(repetitions):
        p=np.asarray(p.astype(np.float64)*factor,dtype=np.float32)
    return p


def envelope_spectrum_idr_candidate(samples:np.ndarray,sample_rate:int,code:int,
                                    profile:EnvelopeProfile,*,n_fft:int=4096,
                                    mode:int=1,backend:str='idr_float32',
                                    f_range:float=1.0)->dict:
    """No silent data changes: require exact FIR history for exact FFT N.

    Supports original modes 0..3 with source-based 007D2164 conversion.
    All values remain APP_DERIVED_CANDIDATE, NEVER original instrument DSP.
    """
    if mode not in range(4):
        raise ValueError('Original spectrum modes are 0..3')
    if not math.isfinite(f_range) or f_range<=0:
        raise ValueError('FRange must be positive and finite')
    if not isinstance(profile,EnvelopeProfile):
        raise ValueError('Original local IDP EnvelopeProfile is mandatory')
    plan=required_original_history(n_fft,sample_rate,code)
    a=np.asarray(samples,dtype=np.float32)
    if a.ndim!=1 or len(a)!=plan['input_samples'] or not np.isfinite(a).all():
        raise ValueError('Exact recorded FIR input length is required; no padding/truncation')
    # GetSpectrum's pre-FIR f32 mean is done in this function once.
    env=process_original_envelope_candidate(a,sample_rate,code,profile,f_range=1.)
    transformed=np.asarray(env['chronological'],dtype=np.float32)
    if len(transformed)!=n_fft:
        raise ValueError('FIR output length does not match FFT N; operation refused')
    # IMPORTANT: 007D14B3 is BEFORE filtering, no second call to 007D2344.
    power, second_removed=idr_power_spectrum(transformed,backend,remove_dc=False)
    assert second_removed==0.0
    fs_out=int(env['output_sample_rate_hz'])
    low=max(2,round(n_fft/(2.0*fs_out)))
    if low>=len(power):
        raise ValueError('Invalid lower-band cutoff for FFT output rate')
    p=np.asarray(power,dtype=np.float32).copy()
    p[:low]=0
    if mode in (2,3):
        p=_delphi_integration_power(p,n_fft,fs_out,mode-1)
    frequency=np.arange(n_fft//2,dtype=np.float64)*(fs_out/n_fft)
    if mode==0:
        amplitude=np.full(len(p),-180.,dtype=np.float64)
        pos=p>0
        amplitude[pos]=10*(np.log10(p[pos].astype(np.float64))-2*np.log10(n_fft//2))
    else:
        amplitude=np.asarray(np.sqrt(p.astype(np.float64)/2.0)*
                             (f_range/(n_fft/2.0)),dtype=np.float32).astype(np.float64)
    return {'source':SOURCE,'fft_backend':backend,'channel_source':'MVK_ADC_CALIBRATED_BIN',
            'n_fft':n_fft,'mode':mode,'unit':_MODE_UNITS[mode],
            'frequency_hz':frequency.tolist(),'amplitude':amplitude.tolist(),
            'df_hz':fs_out/n_fft,'output_sample_rate_hz':fs_out,
            'f_range_used':float(f_range),'original_f_range_verified':False,
            'low_bins_zeroed':low,'source_history_samples':len(a),
            'envelope_stages':plan['stages'],'output_samples':len(transformed),
            'raw_mean_removed_m_s2':env['removed_mean_m_s2'],
            'mean_subtraction_count':1,'fft_second_mean_subtraction':False,
            'private_coefficient_source':profile.provenance,
            'power_integration_passes':max(0,mode-1),
            'original_delphi_numerical_parity_verified':False,
            'original_window_selection_verified':False,
            'warning':'Research reconstruction only; FFT/window/FRange/x87 and original export require same-record verification'}
