"""MVK Reader offline signal core. Does not communicate with instruments."""
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from scipy import signal

@dataclass
class Recording:
    path: Path
    channel: str
    fs: float
    units: str
    samples: np.ndarray
    started: str
    gain_metadata: str

    @property
    def duration(self): return len(self.samples) / self.fs


def load_recording(path):
    """Load single-channel BIN paired with TSXML; support embedded offsets and validate size."""
    path = Path(path)
    xml_path = path if path.name.lower().endswith('.tsxml') else Path(str(path) + '.tsxml')
    if not xml_path.is_file(): raise ValueError('Не найден файл описания: ' + str(xml_path))
    root = ET.parse(xml_path).getroot()
    channels = root.findall('./Channels/Channel')
    if len(channels) != 1: raise ValueError('В версии 0.1 поддерживается только один канал на файл')
    ch = channels[0]
    if ch.findtext('RealDataType') != 'Single': raise ValueError('Ожидался Float32 Single')
    fs = float(ch.findtext('ChannelFrequency') or root.findtext('FrequencyPerChannel'))
    if fs <= 0: raise ValueError('Некорректная частота дискретизации')
    offset = int(ch.findtext('DataOffset') or 0)
    size = int(ch.findtext('DataLength'))
    if offset < 0 or size <= 0 or size % 4: raise ValueError('Некорректная длина/смещение данных')
    if path.name.lower().endswith('.tsxml'):
        relative = (root.findtext('DataFileName') or '').replace('\\','/')
        binary = xml_path.parent / Path(relative).name
    else:
        binary = path
    if not binary.is_file() or binary.stat().st_size < offset+size: raise ValueError('BIN не найден или укорочен')
    values = np.memmap(binary, dtype='<f4', mode='r', offset=offset, shape=(size//4,))
    if not np.all(np.isfinite(values)): raise ValueError('В отсчётах обнаружены NaN/Inf')
    return Recording(binary, ch.findtext('ChannelName') or binary.stem, fs, ch.findtext('Units') or 'м/с²', values,
                     root.findtext('DateTime') or '', ch.findtext('InternalChannelGain') or '')


def metrics(x):
    x = np.asarray(x, dtype=np.float64)
    a = x - x.mean()
    rms = np.sqrt(np.mean(a*a))
    return {'mean_m_s2':float(x.mean()), 'rms_ac_m_s2':float(rms),
            'rms_with_dc_m_s2':float(np.sqrt(np.mean(x*x))),
            'min_m_s2':float(x.min()), 'max_m_s2':float(x.max()),
            'peak_to_peak_m_s2':float(np.ptp(x))}


def compute_spectrum(x, fs, df=0.25, kind='velocity', highpass_hz=1.0):
    """Hann-windowed, non-overlapping averaged power spectral estimate (RMS per bin).

    Important: estimator is NOT an asserted replica of MVKView's internal spectral method.
    Each segment is mean-removed. Coherent narrowband peak amplitude depends on bin alignment.
    """
    x = np.asarray(x, dtype=np.float64)
    n = int(round(fs / df))
    if n < 16 or len(x) < 16: raise ValueError('Слишком мало отсчётов')
    n = min(n, len(x))
    f, p = signal.welch(x, fs=fs, window='hann', nperseg=n, noverlap=0,
                        detrend='constant', scaling='spectrum')
    p = np.maximum(p, 0)
    # Spectral integration changes amplitude; avoid f=0 singularity.
    if kind=='velocity':
        factor = np.zeros_like(f)
        valid = f >= highpass_hz
        factor[valid] = 1000 / (2*np.pi*f[valid])
        unit='мм/с'
    elif kind=='displacement':
        factor = np.zeros_like(f)
        valid = f >= highpass_hz
        factor[valid] = 1e6 / (2*np.pi*f[valid])**2
        unit='мкм'
    else:
        factor = np.ones_like(f)
        factor[0]=0
        unit='м/с²'
    y = np.sqrt(p) * factor
    return f, y, unit


def spectrum_metrics(freq, amplitude, lo=1, hi=None):
    mask = (freq >= lo) & (freq <= (hi if hi else freq[-1]))
    if not mask.any(): raise ValueError('Пустая полоса анализа')
    f=freq[mask]; a=amplitude[mask]
    peak=int(np.argmax(a))
    return {'peak_frequency_hz':float(f[peak]), 'peak_rms':float(a[peak]),
            'spectrum_rms':float(np.linalg.norm(a)), 'frequency_min_hz':float(f[0]),
            'frequency_max_hz':float(f[-1])}


def downsample_for_plot(x, fs, points=9000):
    """Visual min-max envelope: preserve spikes instead of naive slicing."""
    x=np.asarray(x)
    k=max(1, int(np.ceil(len(x)/max(1,points//2))))
    usable=(len(x)//k)*k
    if usable==0: return np.arange(len(x))/fs,x
    chunks=x[:usable].reshape(-1,k)
    low=chunks.min(axis=1);high=chunks.max(axis=1)
    t=(np.arange(len(low))*k + k/2) / fs
    return np.repeat(t,2), np.column_stack((low,high)).reshape(-1)
