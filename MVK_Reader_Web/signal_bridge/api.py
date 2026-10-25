"""Read-only extension to existing MVK Reader Web. No device access."""
from pathlib import Path
import json
import numpy as np
from fastapi import APIRouter, HTTPException, Query
from .signal_processing import spectra,time_stats,FilterConfig,filter_acceleration
router=APIRouter(prefix='/api/signal',tags=['MVK raw ADC offline'])
ROOT=Path(__file__).resolve().parent.parent/'signal_data'

def meta():
    p=ROOT/'manifest.json'
    if not p.is_file():raise HTTPException(404,'No offline signal snapshot. Import PCAPNG from CLI.')
    return json.loads(p.read_text(encoding='utf8'))

def load_adc(adc):
    if not 1<=adc<=8:raise HTTPException(422,'ADC must be 1..8')
    meta()
    p=ROOT/f'adc{adc}.npy'
    if not p.is_file():raise HTTPException(404,'ADC not found')
    return np.load(p,allow_pickle=False,mmap_mode='r')

@router.get('/status')
def status():
    m=meta();return {**m,'channels':[{'adc':i,'samples':int(load_adc(i).size)} for i in range(1,9)],'live_device_connection':False}

@router.get('/adc/{adc}/waveform')
def waveform(adc:int,seconds:float=Query(1.,gt=0,le=10),points:int=Query(2000,ge=100,le=10000),start_s:float|None=Query(None,ge=0)):
    x=load_adc(adc);fs=65536;n=min(len(x),int(fs*seconds))
    end=len(x) if start_s is None else min(len(x),int(fs*start_s)+n)
    begin=max(0,end-n);x=x[begin:end]
    if not n:raise HTTPException(422,'No samples')
    step=max(1,int(np.ceil(n/points)));ix=np.arange(0,n,step)
    return {'adc':adc,'unit':'raw ADC counts (uncalibrated)','fs_hz':fs,'time_s':((ix+begin)/fs).tolist(),'values':np.asarray(x[ix],dtype=float).tolist(),'samples':len(x),'start_s':begin/fs,'duration_s':len(x)/fs,'total_s':int(load_adc(adc).size)/fs}

@router.get('/adc/{adc}/spectrum')
def spectrum(adc:int,nperseg:int=Query(65536,ge=256,le=262144),kind:str=Query('raw',pattern='^(raw|acceleration|velocity|displacement)$'),gain:float|None=Query(None),low_hz:float=Query(1,gt=0),high_hz:float=Query(1000,gt=0),filter_kind:str=Query('none',pattern='^(none|lowpass|highpass|bandpass)$'),start_s:float|None=Query(None,ge=0),duration_s:float=Query(4,gt=0,le=10)):
    if kind!='raw' and gain is None:raise HTTPException(422,'Physical units require an explicit verified m/s^2-per-count gain')
    if gain is not None and (not np.isfinite(gain) or gain<=0):raise HTTPException(422,'Gain must be positive and finite')
    if not low_hz<high_hz<32768:raise HTTPException(422,'Invalid frequency range')
    x=load_adc(adc)
    if x.size<nperseg:raise HTTPException(422,'Not enough samples')
    end=len(x) if start_s is None else min(len(x),int(65536*(start_s+duration_s)))
    begin=max(0,end-int(65536*duration_s));x=np.asarray(x[begin:end],dtype=float)
    if x.size<nperseg:raise HTTPException(422,'Selected interval shorter than FFT window')
    x=x*(1 if gain is None else gain)
    try:
        x=filter_acceleration(x,65536,FilterConfig(kind=filter_kind,low_hz=low_hz,high_hz=high_hz))
        result=spectra(x,65536,nperseg=nperseg,fmin=low_hz,fmax=high_hz)
    except (ValueError,TypeError) as exc:raise HTTPException(422,str(exc)) from exc
    # inspect function schema; covered by API regression tests
    return {'adc':adc,'kind':kind,'gain':gain,'start_s':begin/65536,'duration_s':len(x)/65536,'spectrum':_extract(result,kind)}

def _extract(result,kind):
    if kind=='raw' or kind=='acceleration':key='accel_psd'
    elif kind=='velocity':key='velocity_psd'
    else:key='displacement_psd'
    return {'available_keys':list(result),'frequencies_hz':np.asarray(result['frequencies_hz']).tolist(),'values':np.asarray(result[key]).tolist(),'unit':('raw²/Hz' if kind=='raw' else ('(m/s²)²/Hz' if kind=='acceleration' else ('mm/s)²/Hz' if kind=='velocity' else '(µm)²/Hz')))}
