"""Stage111O: cached read-only GetSignal sample lookup for native mouse moves.

Source observation (private _Unit128.pas): pbAdcMouseMove 0084B4AC..4DE
passes the integer X coordinate to TQGrapher.UpdateCursor.  Original
TQGrapher canvas-to-sample orientation is NOT yet independently verified.

This is a *Qt display candidate*: select a sample in a chosen archive window
without reading the ZIP and running a full GetSignal on every mouse pixel.
Uses the same no-envelope GetSignal candidate as OfflineSession.exact_sample.
Does not access networks, an instrument, AUX4700 or original protected data.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numbers
import numpy as np

from .signal_idr_candidate import unfiltered_getsignal

SOURCE='APP_DERIVED_WAVEFORM_HOVER_CURSOR_IDR_CANDIDATE'


@dataclass(frozen=True)
class WaveformHoverWindow:
    channel: int
    sample_rate_hz: float
    start_index: int
    end_index_exclusive: int
    mode: str
    display_order: str
    signal_chronological: np.ndarray

    def pick(self, display_time_s: float) -> dict:
        """Match OfflineSession.exact_sample index convention, O(1) after setup."""
        if (isinstance(display_time_s,bool)
                or not isinstance(display_time_s,numbers.Real)
                or not math.isfinite(float(display_time_s))):
            raise ValueError('Cursor display coordinate must be finite')
        fs=self.sample_rate_hz
        first=self.start_index
        end=self.end_index_exclusive
        t=float(display_time_s)
        if not first/fs <= t < end/fs:
            raise ValueError('Cursor outside the local waveform window')
        display_idx=min(end-1,max(first,math.floor(t*fs+.5)))
        j=display_idx-first
        original_idx=(display_idx if self.display_order=='chronological'
                      else end-1-j)
        return {
            'source':SOURCE,
            'channel':self.channel,
            'display_index':display_idx,
            'index':original_idx,
            'time_s':display_idx/fs,
            'original_sample_time_s':original_idx/fs,
            'value_m_s2':float(self.signal_chronological[original_idx-first]),
            'mode':self.mode,'display_order':self.display_order,
            'original_plot_coordinate_parity_verified':False,
            'original_Delphi_CursorString_parity_verified':False,
            'original_mousemove_handler_source_verified':True,
        }


def prepare_waveform_hover_window(session,channel:int, *,
                                  start_s:float, seconds:float,
                                  mode:str,display_order:str)->WaveformHoverWindow:
    """One ZIP read + one reconstructed GetSignal window, then O(1) picks.

    The caller supplies an existing local OfflineSession; no device access.
    Original Delphi x87, TCanvas, plot orientation and complete signal
    numerical parity remain open.
    """
    if (not isinstance(channel,numbers.Integral) or isinstance(channel,bool)
            or not 1<=channel<=8 or mode not in ('ac','acdc')
            or display_order not in ('chronological','getsignal_buffer')):
        raise ValueError('Invalid channel, mode or original buffer order')
    if (not all(isinstance(v,numbers.Real) and not isinstance(v,bool)
                and math.isfinite(float(v)) for v in (start_s,seconds))
            or not 0<=start_s or not 0<seconds<=30):
        raise ValueError('Invalid waveform archive window')
    values,fs,_,_=session.samples(int(channel))
    if not math.isfinite(float(fs)) or fs<=0:
        raise ValueError('Invalid archive sample rate')
    values=np.asarray(values,dtype=np.float32)
    if values.ndim!=1:
        raise ValueError('Original archive samples must be a flat signal')
    first=round(start_s*fs)
    last=min(len(values),first+round(seconds*fs))
    if last<=first:
        raise ValueError('Selected waveform hover window is empty')
    frame=unfiltered_getsignal(values[first:last],fs,no_dc=(mode=='ac'))
    return WaveformHoverWindow(
        channel=int(channel),sample_rate_hz=float(fs),
        start_index=int(first),end_index_exclusive=int(last),
        mode=mode,display_order=display_order,
        signal_chronological=frame.chronological)
