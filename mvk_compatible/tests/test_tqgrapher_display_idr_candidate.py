"""Stage111J original visual series count and CursorString regressions; synthetic."""
import numpy as np
import pytest
from mvk_compatible.core.tqgrapher_display_idr_candidate import (
    spectrum_display_contract,cursor_string_candidate)


@pytest.mark.parametrize('n,bins',[
    (1024,400),(4096,1600),(16384,6400),(65536,25600),
    (262144,102400)])
def test_original_TQGrapher_series_shorter_than_power_array(n,bins):
    data=spectrum_display_contract(n,65536)
    assert data['full_fft_power_bins']==n//2
    assert data['grapher_series_bins']==bins
    assert data['grapher_series_bins']<data['full_fft_power_bins']
    assert data['grapher_last_index']==bins-1
    assert data['x_scale_single_hz']==float(np.float32(65536/n))
    assert data['grapher_last_frequency_hz']==float(np.float32(
        (bins-1)*data['x_scale_single_hz']))
    assert data['display_truncation']=='TRUNC((NFFT/2)/EXTENDED_1_28)'
    assert data['original_pixel_rectangle_verified'] is False


def test_original_cursor_string_crlf_names_and_order():
    x=cursor_string_candidate(37.5,.125,x_name='Гц',y_name='м/с²')
    assert x['text']=='37,5 Гц\r\n0,125 м/с²'
    assert x['cursor_sep']=='\r\n'
    assert not x['original_Delphi_FormatFloat_parity_verified']
    assert not x['original_axis_localization_verified']


def test_original_two_series_emits_each_y_line():
    r=cursor_string_candidate(32.,2.,x_name='Hz',y_name='acc',
                              second_y=3.,second_y_name='vel',
                              decimal_separator='.')
    assert r['text']=='32 Hz\r\n2 acc\r\n3 vel'
    assert len(r['y_texts'])==2


@pytest.mark.parametrize('invalid',[(0,65536),(500,65536),
                                    (4000,65536),(1024,0),
                                    (1024,float('inf'))])
def test_invalid_grapher_geometry_refused(invalid):
    with pytest.raises(ValueError):
        spectrum_display_contract(*invalid)


def test_nan_y_and_invalid_second_series_names_refused():
    with pytest.raises(ValueError):
        cursor_string_candidate(1,float('nan'))
    with pytest.raises(ValueError):
        cursor_string_candidate(1,2,second_y=3)
