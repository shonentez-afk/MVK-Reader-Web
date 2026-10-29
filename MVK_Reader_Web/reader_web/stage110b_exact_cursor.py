"""Stage110B OFFLINE exact signal and FFT bin inspection. No device access."""
import math
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
from fastapi import HTTPException, Query

def register_cursor_routes(router, read_samples, spectrum_for_zip, get_archive):
    @router.get('/sessions/{session_id}/waveform_cursor')
    def waveform_cursor(session_id:str, channel:int=Query(1,ge=1,le=8),
                        time_s:float=Query(...,ge=0), start_s:float=Query(0,ge=0),
                        seconds:float=Query(1,gt=0,le=30),mode:str='acdc'):
        try:
            if not all(math.isfinite(x) for x in (time_s,start_s,seconds)):
                raise ValueError('Курсор должен иметь конечные координаты')
            if mode not in ('ac','acdc'):raise ValueError('Некорректный режим')
            samples,fs,_,_=read_samples(get_archive(session_id),channel)
            a=round(start_s*fs);b=min(len(samples),a+round(seconds*fs))
            if b<=a or not a/fs<=time_s<b/fs:raise ValueError('Курсор за пределами окна BIN')
            i=min(b-1,max(a,math.floor(time_s*fs+.5)))
            raw=float(samples[i])
            mean=float(np.mean(samples[a:b],dtype=np.float64))
            return {'channel':channel,'sample_index':i,'time_s':i/fs,
                    'requested_time_s':time_s,'value_m_s2':raw-mean if mode=='ac' else raw,
                    'stored_bin_value_m_s2':raw,'window_mean_m_s2':mean,'mode':mode,
                    'source':'MVK_ADC_CALIBRATED_BIN','precision':'UNDECIMATED_SAMPLE',
                    'warning':'AC candidate: mean of selected window; original Delphi parity unverified'}
        except (ValueError,KeyError,zipfile.BadZipFile,ET.ParseError) as e:
            raise HTTPException(422,str(e)) from e

    @router.get('/sessions/{session_id}/spectrum_cursor')
    def spectrum_cursor(session_id:str, channel:int=Query(1,ge=1,le=8),
                        frequency_hz:float=Query(...,ge=0,le=32768),n_fft:int=65536,
                        mode:int=Query(1,ge=0,le=3),start_s:float|None=Query(None,ge=0)):
        try:
            if not math.isfinite(frequency_hz) or (start_s is not None and not math.isfinite(start_s)):
                raise ValueError('Курсор должен иметь конечные координаты')
            d=spectrum_for_zip(get_archive(session_id),channel,n_fft,mode,
                               start_s=start_s,max_hz=32768,max_points=262144)
            i=math.floor(frequency_hz/d['df_hz']+.5)
            if i<0 or i>=len(d['frequency_hz']):
                raise ValueError('Ячейка Найквиста не входит в исходный график')
            return {'channel':channel,'bin_index':i,'frequency_hz':d['frequency_hz'][i],
                    'requested_frequency_hz':frequency_hz,'amplitude':d['amplitude'][i],
                    'df_hz':d['df_hz'],'unit':d['unit'],'mode':d['mode'],
                    'n_fft':d['n_fft'],'source':d['source'],
                    'precision':'UNDECIMATED_FFT_BIN','warning':d['warning']}
        except (ValueError,KeyError,zipfile.BadZipFile,ET.ParseError) as e:
            raise HTTPException(422,str(e)) from e
