"""Stage111: pure offline MVKView-compatible data core; NO HTTP, GUI or device commands.

Derived from independently tested Stage110A/B research, retaining strict provenance
and its explicit candidate status for local FFT/AC. DSP figures are original AUX.
"""
from __future__ import annotations

import csv
import hashlib
import xml.etree.ElementTree as ET
import io
import json
import math
import re
import zipfile
from pathlib import Path
from dataclasses import dataclass

import numpy as np
from .fft_idr_candidate import idr_power_spectrum
from .spectrum_display_source import source_derived_mode_display
from .dsp_tach_timeline import read_verified_dsp_tach_tick, source_sensor_status
from .signal_idr_candidate import unfiltered_getsignal
from .getsignal_input_evidence import archive_input_window_evidence
from .tqgrapher_cursor_candidate import CursorGeometry, cursor_from_spectrum
from .spectrum_metrics_idr_candidate import original_spectrum_summary
from .narrowband_idr_candidate import narrowband_from_samples
from .calibration_candidate import resolve_f_range
from .storage_f_range_idr_candidate import (prepare_original_fft_input,DOMAIN_CALIBRATED_BIN)
from .envelope_idr_candidate import EnvelopeProfile,envelope_plan,process_original_envelope_candidate
from .envelope_spectrum_idr_candidate import (required_original_history, envelope_spectrum_idr_candidate, _delphi_integration_power)

VERSION = 'Stage111 compatibility core 0.1 (research)'
MAX_ARCHIVE_MB = 1024
MAX_BIN_SAMPLES = 10_000_000
MAX_VALUES_BYTES = 4_000_000
MAX_AUX_BYTES = 16_000_000
BIN_NAME_RE = re.compile(r'^MVK\d+-ADC([1-8])-\d{4}-\d{2}-\d{2}--\d{2}-\d{2}-\d{2}\.bin$')


def require_members(z: zipfile.ZipFile) -> tuple[list[str], dict]:
    files = z.namelist()
    required = ('EXPORT_AUDIT.json', 'VALUES_ALL_ADC_RECONSTRUCTED.csv', 'TABLE_LAST_AUX_RECONSTRUCTED.csv')
    for f in required:
        if f not in files:
            raise ValueError(f'В архиве отсутствует {f}')
    if len(files) != len(set(files)):
        raise ValueError('Дублируются имена файлов в ZIP')
    if z.getinfo('EXPORT_AUDIT.json').file_size > 256_000:
        raise ValueError('Аудит экспорта слишком велик')
    if z.getinfo('VALUES_ALL_ADC_RECONSTRUCTED.csv').file_size > MAX_VALUES_BYTES:
        raise ValueError('VALUES превышает разрешённый размер')
    adc_map = {}
    for name in files:
        if '/' in name or '\\' in name:
            continue
        match = BIN_NAME_RE.fullmatch(name)
        if match:
            n = int(match.group(1))
            if n in adc_map: raise ValueError(f'Дублируется BIN АЦП{n}')
            adc_map[n] = name
    if set(adc_map) != set(range(1, 9)):
        raise ValueError('Нужны восемь BIN из одного комплекта Stage107/R6.1')
    audit = json.loads(z.read('EXPORT_AUDIT.json'))
    if not isinstance(audit,dict) or 'instrument_serial' not in audit:
        raise ValueError('Нет подтверждённой идентичности сеанса')
    manifest = audit.get('output_file_sha256')
    if not isinstance(manifest, dict) or len(manifest) < 18:
        raise ValueError('Отсутствует полный манифест SHA256 из Native R6.1/Stage107')
    for file_name in required[1:]:
        expected = manifest.get(file_name)
        if not isinstance(expected, str) or len(expected) != 64 or hashlib.sha256(z.read(file_name)).hexdigest() != expected:
            raise ValueError(f'Нарушена контрольная сумма {file_name} по EXPORT_AUDIT')
    # Protect against a ZIP accidentally containing channels of different sessions.
    stems={(n.rsplit('-ADC',1)[0], n.rsplit('-ADC',1)[1][1:]) for n in adc_map.values()}
    if len(stems)!=1 or next(iter(stems))[0]!=audit['instrument_serial']:
        raise ValueError('BIN принадлежат разным приборам или сеансам')
    for n,name in adc_map.items():
        counterpart = f'{name}.tsxml'
        if counterpart not in files: raise ValueError(f'Нет TSXML АЦП{n}')
        if z.getinfo(counterpart).file_size > 64_000:
            raise ValueError(f'TSXML АЦП{n} слишком велик')
        expected = manifest.get(counterpart)
        if not isinstance(expected,str) or hashlib.sha256(z.read(counterpart)).hexdigest() != expected:
            raise ValueError(f'Нарушена контрольная сумма TSXML АЦП{n}')
        channel_audit = next((c.get('bin_sha256') for c in audit.get('channels',[]) if c.get('adc')==n),None)
        if manifest.get(name) != channel_audit:
            raise ValueError(f'Нарушена контрольная сумма BIN АЦП{n} в манифесте')
    return [adc_map[n] for n in range(1,9)], audit


def read_values(z: zipfile.ZipFile):
    raw = z.read('VALUES_ALL_ADC_RECONSTRUCTED.csv').decode('cp1251')
    rows = list(csv.reader(io.StringIO(raw), delimiter='|'))
    if len(rows)<4 or rows[0][0]!='sep=' or len(rows[1])!=585 or len(rows[2])!=585:
        raise ValueError('Неверная схема оригинального VALUES 8x73+время')
    for col in range(1,585):
        assert_name = f'АЦП {(col-1)//73+1}'
        if rows[1][col] != assert_name:
            raise ValueError('Перемешаны каналы в VALUES')
    data = rows[3:]
    if not data or any(len(r)!=585 for r in data):
        raise ValueError('Повреждена или пустая матрица VALUES')
    return rows[2], data


def parse_number(raw: str):
    s=str(raw).strip().replace(',', '.')
    try:
        x=float(s)
        return x if math.isfinite(x) else None
    except ValueError:
        return None


def status_at(values: list[str], index: int):
    return values[index].strip()


def read_validated_aux_tick(z: zipfile.ZipFile, audit: dict, tick_index: int):
    """Optional unrounded full AUX (incl. PIK / PIK-PIK).

    Provenance sidecar is mandatory because a free-floating AUX file could be
    taken from another 30-second measurement and silently mixed with BIN/VALUES.
    """
    if 'aux4700.jsonl' not in z.namelist() or 'AUX_PROVENANCE.json' not in z.namelist():
        return None
    if z.getinfo('aux4700.jsonl').file_size > MAX_AUX_BYTES:
        raise ValueError('Слишком большой AUX4700')
    if z.getinfo('AUX_PROVENANCE.json').file_size > 10_000:
        raise ValueError('Слишком большой AUX provenance')
    provenance=json.loads(z.read('AUX_PROVENANCE.json'))
    if hashlib.sha256(z.read('aux4700.jsonl')).hexdigest() != provenance.get('aux4700_sha256'):
        raise ValueError('Нарушена контрольная сумма AUX4700 по provenance')
    if provenance.get('source_raw_sha256')!=audit.get('source_raw_sha256'):
        raise ValueError('AUX4700 принадлежит другому RAW-сеансу')
    needed=tick_index+1
    out={}
    for line in z.read('aux4700.jsonl').splitlines():
        if not line: continue
        item=json.loads(line)
        if item.get('update')!=needed: continue
        ch=item.get('adc')
        if ch not in range(1,9) or ch in out or any(len(item.get(k, []))!=n for k,n in
             [('third_octave_acceleration_rms',43),('band_rms',24),('band_peak_equiv',24),('band_span_equiv',24)]):
            raise ValueError('Повреждён AUX4700 для расчётного обновления')
        out[ch]=item
    if set(out)!=set(range(1,9)):
        raise ValueError('Неполный AUX4700 для выбранного обновления')
    return out


def validate_aux_values_row(aux:dict, row:list[str]):
    """Validate unrounded AUX against independently exported rounded VALUES.

    Stage107 writes 4 significant digits with decimal comma; this check is
    exact at the display-precision level and guards against mixed/altered AUX.
    """
    for ch in range(1,9):
        values=row[1+73*(ch-1):1+73*ch]
        obj=aux[ch]
        # Source arrays come from actual register words. Do not allow NaN/Inf,
        # strings, booleans or unrounded PIK/P-P values to bypass provenance.
        for source_key in ('third_octave_acceleration_rms','band_rms',
                           'band_peak_equiv','band_span_equiv'):
            for x in obj[source_key]:
                if type(x) not in (int,float) or not math.isfinite(x):
                    raise ValueError('AUX4700: invalid nonfinite/non-numeric original DSP value')
        for arr,offset in ((obj['third_octave_acceleration_rms'],0), (obj['band_rms'],49)):
            for k,value in enumerate(arr):
                if not math.isfinite(float(value)):
                    raise ValueError('AUX содержит нечисловые значения')
                if format(float(value),'.4g')!=values[offset+k].strip().replace(',','.'):
                    raise ValueError('AUX и VALUES не совпадают: другая запись или повреждение')
        if 'status_hex' in obj:
            text_status=values[45].strip().lower()
            normalized='0x00000000' if text_status in ('ок','ok','0') else text_status
            if obj['status_hex'].strip().lower()!=normalized:
                raise ValueError('Статус AUX не совпадает с VALUES')


def calculated_for_zip(path: Path, tick: int = -1) -> dict:
    with zipfile.ZipFile(path) as z:
        _, audit = require_members(z)
        headers, rows = read_values(z)
        if tick < -len(rows) or tick >= len(rows):
            raise ValueError('Номер расчётного обновления вне диапазона')
        tick_index=tick if tick>=0 else len(rows)+tick
        row = rows[tick]
        aux_tick = read_validated_aux_tick(z, audit, tick_index)
        if aux_tick is not None:
            validate_aux_values_row(aux_tick,row)
        # Existing audited TIMELINE is extended in place with original raw
        # DSP/TACH register words. Old exports remain readable but UNKNOWN.
        tick_registers = read_verified_dsp_tach_tick(z,audit,tick_index,len(rows))
        channels = []
        for channel in range(1,9):
            off = 1+73*(channel-1)
            vals = row[off:off+73]
            # 43 measured third-octave bands, 24 measured RMS fixed/user values.
            bands = [{'name': headers[off+k], 'rms_m_s2': parse_number(vals[k])}
                     for k in range(43)]
            measures = []
            for k in range(49,73):
                units = 'м/с²' if (k-49)%3==0 else ('мм/с' if (k-49)%3==1 else 'мкм')
                measures.append({'name': headers[off+k], 'value': parse_number(vals[k]), 'unit': units})
            aux_channel = aux_tick.get(channel) if aux_tick else None
            if aux_channel:
                for k,item in enumerate(measures):
                    item['value'] = float(aux_channel['band_rms'][k])
                for k,item in enumerate(bands):
                    item['rms_m_s2'] = float(aux_channel['third_octave_acceleration_rms'][k])
            peak = ([{'name':headers[off+49+k], 'value':float(v), 'unit':measures[k]['unit']}
                     for k,v in enumerate(aux_channel['band_peak_equiv'])] if aux_channel else None)
            span = ([{'name':headers[off+49+k], 'value':float(v), 'unit':measures[k]['unit']}
                     for k,v in enumerate(aux_channel['band_span_equiv'])] if aux_channel else None)
            channels.append({
                'channel': channel,
                'parameters_peak_24':peak,
                'parameters_peak_peak_24':span,
                'third_octave': bands,
                'parameters_24': measures,
                'sensor_voltage_v': parse_number(vals[46]),
                'broadband_acceleration_m_s2': parse_number(vals[47]),
                'crest_factor': parse_number(vals[48]),
                'overload_status': status_at(vals, 43),
                'buffer_status': status_at(vals, 44),
                'sensor_status': status_at(vals, 45),
                'sensor_status_details': source_sensor_status(
                    aux_channel if (aux_channel and 'status_raw' in aux_channel) else None,
                    status_at(vals,45)),
                'data_source': ('MVK_DSP_AUX4700_FULL_PRECISION' if aux_channel else 'MVK_DSP_FROM_AUX4700_VIA_VALUES'),
                'health': 'ALERT' if vals[45].strip().lower() not in ('ок','ok','0x00000000','0') else 'OK',
            })
        return {
            'version':VERSION,'serial':audit['instrument_serial'],
            'updates':len(rows),'tick':tick_index,
            'timestamp':row[0], 'time_kind':'HOST_CLOCK_VALUES',
            'channels':channels,'source':'MVK_DSP',
            'precision':('unrounded AUX4700' if aux_tick else 'rounded VALUES CSV'),
            'peak_metrics_available': bool(aux_tick),
            'dsp_tach': tick_registers,
            'control_status': tick_registers.get('control_status'),
            'warning':'Временные метки VALUES — часы ПК; расчёты не пересчитаны приложением. ПИК/ПИК-ПИК доступны только при проверенном AUX4700 того же RAW.',
        }


def read_samples(path: Path, channel: int):
    if channel < 1 or channel > 8:
        raise ValueError('Номер АЦП должен быть 1..8')
    with zipfile.ZipFile(path) as z:
        files, audit = require_members(z)
        name=files[channel-1]
        info=z.getinfo(name)
        if info.file_size % 4 or info.file_size > MAX_BIN_SAMPLES*4:
            raise ValueError('BIN имеет некорректный размер')
        data=z.read(name)
        match = next((c for c in audit.get('channels',[]) if c.get('adc')==channel), None)
        if not match or match.get('bin_sha256') != hashlib.sha256(data).hexdigest():
            raise ValueError('Нарушена контрольная сумма BIN относительно EXPORT_AUDIT')
        metadata = ET.fromstring(z.read(name+'.tsxml'))
        chs = metadata.findall('./Channels/Channel')
        if len(chs)!=1 or chs[0].findtext('RealDataType')!='Single':
            raise ValueError('Некорректная структура TSXML')
        if (int(chs[0].findtext('DataLength') or -1)!=len(data) or
            int(chs[0].findtext('DataOffset') or -1)!=0 or
            int(chs[0].findtext('ChannelFrequency') or -1)!=65536):
            raise ValueError('Размер BIN и частота не совпадают с TSXML')
        samples=np.frombuffer(data, dtype='<f4')
        if not np.isfinite(samples).all():
            raise ValueError('В BIN найдены NaN или Inf')
        # Native output is *already* calibrated; do not apply K twice.
        return samples, 65536.0, audit, name


def reduce_minmax(samples:np.ndarray, fs:float, offset:int, points:int):
    """Preserve waveform extrema instead of decimating one point per time bin."""
    count = max(1, (len(samples)+max(1,points//2)-1)//max(1,points//2))
    times,values=[],[]
    for i in range(0,len(samples),count):
        block=samples[i:i+count]
        low=int(np.argmin(block))
        high=int(np.argmax(block))
        # Actual sample times, in chronological order, for cursor binary search.
        picks=(low,) if low==high else tuple(sorted((low,high)))
        for j in picks:
            times.append((offset+i+j)/fs)
            values.append(float(block[j]))
    return times,values


def waveform_for_zip(path: Path, channel: int, start_s: float, seconds: float,
                     mode: str='acdc', points:int=4000,
                     display_order: str='chronological', *,
                     sample_provider=None)->dict:
    """GetSignal no-envelope f32 candidate; separate original buffer from BIN time."""
    if mode not in ('ac','acdc'):
        raise ValueError('Режим должен быть ac или acdc')
    if display_order not in ('chronological','getsignal_buffer'):
        raise ValueError('Неизвестный порядок отображения')
    # Stage111Z.16: opt-in verified local BIN/TSXML reader. The R6.1 ZIP
    # default and its audit/CSV requirements remain strictly unchanged.
    samples, fs, audit, filename=(sample_provider(channel) if sample_provider
                                 is not None else read_samples(path,channel))
    if not math.isfinite(start_s) or not math.isfinite(seconds) or not 0<=start_s<=len(samples)/fs or not 0<seconds<=30:
        raise ValueError('Неверные границы окна временного сигнала')
    a=round(start_s*fs)
    b=min(len(samples),a+round(seconds*fs))
    if b<=a:raise ValueError('Нет отсчётов в выбранном окне')
    source_window=archive_input_window_evidence(
        samples,first=a,end=b,sample_rate_hz=fs,
        native_audit=bool(isinstance(audit,dict) and
            audit.get('instrument_serial') and audit.get('output_file_sha256')),
        channel=channel,
        source_raw_sha256=audit.get('source_raw_sha256') if isinstance(audit,dict) else None)
    frame=unfiltered_getsignal(samples[a:b],fs,no_dc=mode=='ac')
    signal=(frame.chronological if display_order=='chronological' else frame.getsignal_buffer)
    xx,yy=reduce_minmax(signal,fs,a,points)
    return {'version':VERSION,'channel':channel,'sample_rate_hz':fs,
            'total_samples':int(len(samples)), 'window_samples':int(len(signal)),
            'start_s':a/fs,'end_s':b/fs,
            'time_s':xx,'amplitude':yy,'unit':'м/с²',
            'input_source_window':source_window,
            'requested_window_truncated_by_archive_end':
                (b < a+round(seconds*fs)),
            'mean_m_s2':frame.window_mean,
            'removed_mean_m_s2':frame.removed_mean,
            'rms_m_s2':frame.rms_value,
            'peak_m_s2':float(np.max(np.abs(signal))),
            'mode':mode,'display_order':display_order,
            'source':'MVK_ADC_CALIBRATED_BIN',
            'local_processing':'GETSIGNAL_NO_ENVELOPE_IDR_CANDIDATE',
            'time_axis_kind':('ARCHIVE_SAMPLE_TIME' if display_order=='chronological'
                else 'GETSIGNAL_RETURN_BUFFER_POSITION_NOT_ARCHIVE_TIME'),
            'original_plot_coordinate_parity_verified':False,
            'processing_note':('AC: NoDC=True, f32 running-mean subtraction 007D2344; '
               'AC+DC: NoDC=False; GetSignal returns array reversed 007D0DEC. '
               'Envelope not implemented; TQGrapher display orientation still unverified.'),
            'file':filename}


def spectrum_for_zip(path:Path,channel:int,n_fft:int,mode:int,start_s:float|None=None,
                     max_hz:float=10000.0, max_points:int=5000, backend:str='idr_float32',
                     *, f_range:float|None=None,
                     input_domain:str=DOMAIN_CALIBRATED_BIN,
                     sample_provider=None)->dict:
    applied_range,range_source=resolve_f_range(f_range)
    if n_fft<1024 or n_fft>262144 or n_fft&(n_fft-1):
        raise ValueError('FFT N должно быть степенью двойки 1024..262144, максимум оригинала')
    if mode not in range(4):raise ValueError('Допустимы четыре режима 0..3')
    samples,fs,audit,filename=(sample_provider(channel) if sample_provider
                                is not None else read_samples(path,channel))
    start = max(0,len(samples)-n_fft) if start_s is None else round(start_s*fs)
    if start<0 or start+n_fft>len(samples):
        raise ValueError('Не хватает данных для выбранного окна FFT')
    # Same local pre-DC, pre-Hann Float32 BIN window can now be matched
    # against GetSignal by SHA; this is NOT original Delphi same-run parity.
    source_window=archive_input_window_evidence(
        samples,first=start,end=start+n_fft,sample_rate_hz=fs,
        native_audit=bool(isinstance(audit,dict) and
            audit.get('instrument_serial') and audit.get('output_file_sha256')),
        channel=channel,
        source_raw_sha256=audit.get('source_raw_sha256') if isinstance(audit,dict) else None)
    # Original GetSpectrum (0x007D14B3) ALWAYS removes stored f32 mean.
    # Stage111B reconstructed IDR FFT is still candidate, NOT instrument DSP.
    prepared=prepare_original_fft_input(
        samples[start:start+n_fft],f_range=f_range,input_domain=input_domain)
    # Source 007D149A pushes bool 1: original FAdcDataType==1 storage
    # reader divides PAdcFloatData by FRange BEFORE mean removal and FFT.
    # This is an explicit operator hypothesis, never inferred from Native BIN.
    power, removed_mean=idr_power_spectrum(
        prepared['samples_before_dc_removal'],backend=backend)
    power=np.asarray(power,dtype=np.float64)
    # Original 007D158B..007D15BC: Max(2, Round((N/fs)*0.5)).
    # Helper 007B1CF0 is unsigned Max, verified in PRIVATE _Unit114.pas.
    low_bins=max(2,round(n_fft/fs*.5))
    if low_bins>len(power):
        raise ValueError('Неверная нижняя частотная граница FFT')
    power[:low_bins]=0.0
    # Original 007D2164 modifies POWER in-place before the linear amplitude
    # and before summary aggregation, not only the plotted amplitude.
    display_power=(np.asarray(power,dtype=np.float32)
                   if mode<2 else
                   _delphi_integration_power(power,n_fft,int(fs),mode-1))
    # Mean / peak metrics use the whole original N/2 power array, NOT
    # N bins decimated for visualization. FRange=1 is not yet Delphi verified.
    summary=original_spectrum_summary(display_power,n_fft=n_fft,fs_out=fs,
                                      f_range=applied_range,spectrum_mode=mode)
    freq=np.fft.rfftfreq(n_fft,1/fs)[:n_fft//2]
    # Stage30B: SOURCE VERIFIED log10 helper 00447DB8 (FLDLG2/FYL2X)
    # and explicit intermediate Float32 offset/scale plus full Float32 Y.
    # Does NOT redo FFT/integration; x87 bitwise parity remains unverified.
    y=source_derived_mode_display(display_power,n_fft=n_fft,
                                  mode=mode,f_range=applied_range).astype(np.float64)
    if mode==0:
        unit='дБ (source-verified log10, Float32 staging)'
        note='Original 00447DB8 log10 SOURCE-VERIFIED; NumPy vs Delphi x87 и полный Y 1:1 не доказано'
    else:
        unit=('','м/с²','мм/с','мкм')[mode]
        note='Original Float32 display scale source-verified; x87 1:1 не доказано; power integration 007D2164 remains candidate'
    keep=np.flatnonzero(freq<=max_hz)
    if len(keep)>max_points:
        # Retain local maxima rather than throw away narrow resonances.
        chunk=math.ceil(len(keep)/max_points)
        keep=np.array([keep[i:i+chunk][np.argmax(y[keep[i:i+chunk]])] for i in range(0,len(keep),chunk)],dtype=np.int64)
    return {'version':VERSION,'channel':channel,'n_fft':n_fft,'df_hz':fs/n_fft,
            'start_s':start/fs,'end_s':(start+n_fft)/fs,
            'input_source_window':source_window,
            'mode':mode,'mode_name':('Логарифмич.','Линейный ВУ','Линейный ВС','Линейный ВП')[mode],
            'frequency_hz':freq[keep].tolist(),'amplitude':y[keep].tolist(),
            'unit':unit,'source':'APP_DERIVED_FFT_MVKVIEW_CANDIDATE',
            'warning':note,'file':filename,
            'fft_backend':backend,'detrended_before_fft':True,
            'spectrum_summary':summary,'original_f_range_verified':False,
            'f_range_used':applied_range,'f_range_source':range_source,
            'f_range_applied_to_display':mode!=0,
            'log10_helper_source_verified':True,
            'display_float32_intermediate_source_model':True,
            'original_display_y_runtime_parity_verified':False,
            'input_domain':input_domain,
            'original_storage_read_divided_by_range':
                prepared['original_storage_read_divided_by_range'],
            'original_source_buffer_provenance_verified':False,
            'low_bins_zeroed':low_bins,
            'removed_mean_m_s2':removed_mean,'original_delphi_numerical_parity':False}



def open_zip_file(path: Path) -> Path:
    """Reject links, absent/nonlocal files and overlarge archives before parsing."""
    path=Path(path).absolute()
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != '.zip':
        raise ValueError('Нужен локальный обычный ZIP-файл')
    if path.stat().st_size > MAX_ARCHIVE_MB*1024*1024:
        raise ValueError('Архив превышает разрешённый размер')
    return path


@dataclass(frozen=True)
class OfflineSession:
    """One completed Native R6.1 export. Read-only; no sockets or side effects."""
    path: Path
    serial: str
    updates: int
    started_utc: str | None

    @classmethod
    def open(cls, file: str | Path):
        path=open_zip_file(Path(file))
        with zipfile.ZipFile(path) as z:
            files, audit=require_members(z)
            _, rows=read_values(z)
        return cls(path=path, serial=str(audit['instrument_serial']),
                   updates=len(rows),started_utc=audit.get('capture_started_utc'))

    def calculations(self, tick: int=-1)->dict:
        return calculated_for_zip(self.path,tick)

    def samples(self,channel:int)->tuple:
        return read_samples(self.path,channel)

    def waveform(self,channel:int,start_s:float,seconds:float,
                 mode:str='acdc',points:int=4000,display_order:str='chronological')->dict:
        return waveform_for_zip(self.path,channel,start_s,seconds,mode,points,display_order)

    def spectrum(self,channel:int,n_fft:int=65536,mode:int=1,
                 start_s:float|None=None,max_hz:float=10000.,max_points:int=5000,
                 backend:str='idr_float32', *, f_range:float|None=None,
                 input_domain:str=DOMAIN_CALIBRATED_BIN)->dict:
        return spectrum_for_zip(self.path,channel,n_fft,mode,start_s,max_hz,max_points,backend,
                                f_range=f_range,input_domain=input_domain)

    def narrowband(self,channel:int,frequency_hz:float, *,
                   n_fft:int=4096,start_s:float|None=None,
                   get_noise_peak:bool=False,backend:str='idr_float32',
                   f_range:float|None=None,
                   input_domain:str=DOMAIN_CALIBRATED_BIN)->dict:
        """Original GetNarrowbandValue / optional GetNoisePeak offline candidate.

        This is distinct from DSP AUX4700 and GetSpectrum OutputPeakX/Y.
        Archive window selection is explicit and source parity not certified.
        """
        samples,fs,_,filename=self.samples(channel)
        if not isinstance(n_fft,int) or n_fft<1024 or n_fft>262144 or n_fft&(n_fft-1):
            raise ValueError('Narrowband FFT N must be a power of 2: 1024..262144')
        if start_s is not None and (not math.isfinite(start_s) or start_s<0):
            raise ValueError('Invalid archive start time')
        first=max(0,len(samples)-n_fft) if start_s is None else round(start_s*fs)
        last=first+n_fft
        if last>len(samples):
            raise ValueError('Insufficient real BIN samples for narrowband window')
        applied,range_source=resolve_f_range(f_range)
        result=narrowband_from_samples(samples[first:last],
             sample_rate_hz=fs,input_frequency_hz=frequency_hz,
             get_noise_peak=get_noise_peak,f_range=applied,backend=backend,
             input_domain=input_domain)
        result.update(channel=channel,file=filename,
                      f_range_source=range_source,
                      original_f_range_verified=False,
                      archive_window_start_s=first/fs,
                      archive_window_end_s=last/fs,
                      original_archive_position_parity_verified=False)
        return result

    def spectrum_envelope(self,channel:int,code:int,n_fft:int,
                          profile:EnvelopeProfile, *,
                          end_s:float|None=None,mode:int=1,
                          backend:str='idr_float32',f_range:float|None=None,
                          input_domain:str=DOMAIN_CALIBRATED_BIN)->dict:
        """Archival candidate of Delphi GetSpectrum envelope path, read-only.

        Process exactly the real FIR history needed to yield n_fft samples,
        then compute the un-decimated spectrum without a second DC removal.
        end_s is a local input-window selection, NOT proven MVKView position.
        """
        samples,fs,audit,filename=self.samples(channel)
        if not float(fs).is_integer():
            raise ValueError('Original envelope FFT requires integer ADC sample rate')
        plan=required_original_history(n_fft,int(fs),code)
        if end_s is not None and (not math.isfinite(end_s) or end_s<=0):
            raise ValueError('Invalid endpoint for archival window')
        end=len(samples) if end_s is None else round(end_s*fs)
        start=end-plan['input_samples']
        if start<0 or end>len(samples):
            raise ValueError('Insufficient actual BIN history for envelope FFT; no padding')
        if end<=start:raise ValueError('Empty original FFT input')
        source_window=archive_input_window_evidence(
            samples,first=start,end=end,sample_rate_hz=fs,
            native_audit=bool(isinstance(audit,dict) and
                audit.get('instrument_serial') and audit.get('output_file_sha256')),
            channel=channel,
            source_raw_sha256=audit.get('source_raw_sha256') if isinstance(audit,dict) else None)
        applied,range_source=resolve_f_range(f_range)
        result=envelope_spectrum_idr_candidate(
            samples[start:end],int(fs),code,profile,
            n_fft=n_fft,mode=mode,backend=backend,f_range=applied,
            input_domain=input_domain)
        return dict(result,channel=channel,file=filename,
                    f_range_source=range_source,
                    input_source_window=source_window,
                    pre_fir_original_ring_start_index_unverified=True,
                    archive_input_start_s=start/fs,archive_input_end_s=end/fs,
                    full_fft_bins=True,
                    original_archive_position_parity_verified=False)

    def envelope(self,channel:int,code:int,start_s:float,seconds:float,
                 profile:EnvelopeProfile,*,f_range:float=1.0,
                 display_order:str='getsignal_buffer',points:int=4000)->dict:
        """Only with explicit private local FIR profile; no fabricated envelope.

        For offline BIN the requested time window must include the *entire*
        GetAdjustedEnvelopeLength history; short archives fail closed.
        Source GUI absolute time axis for envelope is not verified.
        """
        if display_order not in ('chronological','getsignal_buffer'):
            raise ValueError('Invalid envelope display order')
        if not all(math.isfinite(v) for v in (start_s,seconds)) or start_s<0 or seconds<=0 or seconds>30:
            raise ValueError('Invalid envelope window')
        samples,fs,audit,filename=self.samples(channel)
        if not float(fs).is_integer():
            raise ValueError('Original envelope requires integer ADC sample rate')
        rate=int(fs)
        desired=round(seconds*rate)
        if desired<1:
            raise ValueError('Empty output window')
        plan=envelope_plan(desired,rate,code)
        end=round((start_s+seconds)*rate)
        begin=end-plan['adjusted_input_length']
        if begin<0 or end>len(samples):
            raise ValueError('Original envelope requires more real BIN history: no zero-padding allowed')
        source_window=archive_input_window_evidence(
            samples,first=begin,end=end,sample_rate_hz=fs,
            native_audit=bool(isinstance(audit,dict) and
                audit.get('instrument_serial') and audit.get('output_file_sha256')),
            channel=channel,
            source_raw_sha256=audit.get('source_raw_sha256') if isinstance(audit,dict) else None)
        processed=process_original_envelope_candidate(
            samples[begin:end],rate,code,profile,f_range=f_range)
        raw=(processed['chronological'] if display_order=='chronological'
             else processed['getsignal_buffer'])
        # x is output *buffer position*, not yet an original Delphi graph time.
        output_rate=processed['output_sample_rate_hz']
        xx,yy=reduce_minmax(raw,output_rate,0,points)
        return {'version':VERSION,'channel':channel,'code':code,
                'source':processed['source'],'file':filename,
                'profile_source':processed['profile_source'],
                'input_source_window':source_window,
                'post_fir_getsignal_return_float32_sha256':hashlib.sha256(
                    np.asarray(processed['getsignal_buffer'],dtype='<f4').tobytes()).hexdigest(),
                'post_fir_unreversed_float32_sha256':hashlib.sha256(
                    np.asarray(processed['chronological'],dtype='<f4').tobytes()).hexdigest(),
                'original_getsignal_vs_getspectrum_envelope_numeric_parity_verified':False,
                'post_fir_getsignal_output_samples':processed['output_samples'],
                'original_getsignal_envelope_output_runtime_verified':False,
                'time_s':xx,'amplitude':yy,'unit':'м/с²',
                'output_samples':processed['output_samples'],
                'output_sample_rate_hz':output_rate,
                'rms_m_s2':processed['rms_m_s2'],
                'removed_mean_m_s2':processed['removed_mean_m_s2'],
                'stages_used':processed['stages_used'],
                'display_order':display_order,
                'x_axis_kind':'OUTPUT_BUFFER_RELATIVE_POSITION_NOT_ORIGINAL_TIME',
                'original_delphi_numerical_parity_verified':False,
                'warning':processed['warning']}

    def exact_sample(self,channel:int,time_s:float,start_s:float=0.,
                     seconds:float=1.,mode:str='acdc',
                     display_order:str='chronological')->dict:
        if (mode not in ('ac','acdc') or
            display_order not in ('chronological','getsignal_buffer') or
            not all(math.isfinite(v) for v in (time_s,start_s,seconds))):
            raise ValueError('Неверный режим, порядок или координата')
        samples,fs,_,_=self.samples(channel)
        if start_s<0 or seconds<=0 or seconds>30:
            raise ValueError('Неверное временное окно')
        a=round(start_s*fs);b=min(len(samples),a+round(seconds*fs))
        if b<=a or not a/fs<=time_s<b/fs:
            raise ValueError('Курсор вне временного окна')
        display_idx=min(b-1,max(a,math.floor(time_s*fs+.5)))
        j=display_idx-a
        stored_idx=(display_idx if display_order=='chronological' else b-1-j)
        frame=unfiltered_getsignal(samples[a:b],fs,no_dc=mode=='ac')
        v=frame.chronological[stored_idx-a]
        return {'channel':channel,'index':stored_idx,
                'display_index':display_idx,'time_s':display_idx/fs,
                'original_sample_time_s':stored_idx/fs,
                'value_m_s2':float(v),
                'raw_bin_m_s2':float(samples[stored_idx]),
                'window_mean_m_s2':frame.window_mean,
                'removed_mean_m_s2':frame.removed_mean,
                'window_rms_m_s2':frame.rms_value,
                'source':'MVK_ADC_CALIBRATED_BIN',
                'local_processing':'GETSIGNAL_NO_ENVELOPE_IDR_CANDIDATE',
                'mode':mode,'display_order':display_order,
                'candidate_ac':mode=='ac',
                'original_plot_coordinate_parity_verified':False}

    def exact_fft_bin(self,channel:int,frequency_hz:float,n_fft:int=65536,
                      mode:int=1,start_s:float|None=None,backend:str='idr_float32')->dict:
        if not math.isfinite(frequency_hz) or frequency_hz<0:
            raise ValueError('Частота курсора должна быть положительной')
        d=self.spectrum(channel,n_fft,mode,start_s,32768,262144,backend)
        i=math.floor(frequency_hz/d['df_hz']+.5)
        if not 0<=i<len(d['frequency_hz']):
            raise ValueError('FFT-бин вне частотного диапазона')
        return {'channel':channel,'bin':i,'frequency_hz':d['frequency_hz'][i],
                'value':d['amplitude'][i],'unit':d['unit'],'mode':mode,
                'df_hz':d['df_hz'],'source':d['source'],
                'warning':d['warning'],'fft_backend':backend}

    def pixel_spectrum_cursor(self,channel:int,pixel:float,geometry:CursorGeometry,
                              *,n_fft:int=65536,mode:int=1,
                              start_s:float|None=None,backend:str='idr_float32',
                              precise:bool=True,averaging:int=1,
                              f_range:float|None=None,
                              input_domain:str=DOMAIN_CALIBRATED_BIN)->dict:
        """Original TQGrapher pixel peak candidate over UNDECIMATED FFT bins.

        This is not the independently calculated DSP, nor a bitwise verified
        clone of the original Delphi executable. It uses the common spectrum
        backend and sample calibration without opening sockets or Qt.
        """
        full=self.spectrum(channel,n_fft,mode,start_s,
                           max_hz=32768,max_points=n_fft//2,backend=backend,
                           f_range=f_range,input_domain=input_domain)
        if len(full['frequency_hz'])!=n_fft//2:
            raise ValueError('Нужен полный непрореженный FFT для пиксельного курсора')
        return cursor_from_spectrum(full,pixel,geometry,
                                    precise=precise,averaging=averaging)

    def compare_fft_backends(self,channel:int,n_fft:int=65536,mode:int=1,
                             start_s:float|None=None, *, f_range:float|None=None,
                             input_domain:str=DOMAIN_CALIBRATED_BIN)->dict:
        """Compare two APP-DERIVED candidates, not against original Delphi."""
        a=self.spectrum(channel,n_fft,mode,start_s,32768,n_fft//2,'idr_float32',
                        f_range=f_range,input_domain=input_domain)
        b=self.spectrum(channel,n_fft,mode,start_s,32768,n_fft//2,'numpy',
                        f_range=f_range,input_domain=input_domain)
        x=np.asarray(a['amplitude'],dtype=np.float64)
        y=np.asarray(b['amplitude'],dtype=np.float64)
        err=np.abs(x-y)
        peak=int(np.argmax(y))
        return {'source':'APP_DERIVED_BACKEND_COMPARISON','channel':channel,
                'n_fft':n_fft,'mode':mode,'df_hz':a['df_hz'],
                'f_range_used':a['f_range_used'],
                'f_range_source':a['f_range_source'],
                'input_domain':a['input_domain'],
                'window_mean_m_s2':a['removed_mean_m_s2'],
                'max_absolute_difference':float(err.max()),
                'rms_absolute_difference':float(np.sqrt(np.mean(err**2))),
                'reference_peak_bin':peak,
                'relative_difference_at_reference_peak':float(err[peak]/max(abs(y[peak]),1e-30)),
                'original_delphi_parity_verified':False,
                'note':'IDR float32 candidate versus NumPy, NOT original Delphi'}

    def verify(self)->dict:
        """Decode and verify all channels and full original DSP source."""
        calc=self.calculations(-1)
        channels=[]
        for ch in range(1,9):
            samples,fs,_,_=self.samples(ch)
            channels.append({'adc':ch,'samples':int(len(samples)),
                             'fs_hz':fs,'health':calc['channels'][ch-1]['health']})
        return {'status':'verified_offline_export','serial':self.serial,
                'updates':self.updates,'channels':channels,
                'dsp_source':calc['source'],'precision':calc['precision'],
                'no_device_connection':True,'fft_original_parity_verified':False}
