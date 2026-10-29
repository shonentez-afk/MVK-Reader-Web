"""Stage111O source MouseMove cached waveform, synthetic data only."""
import numpy as np
import pytest

from mvk_compatible.core.waveform_hover_idr_candidate import (
    SOURCE,prepare_waveform_hover_window)


class FakeSession:
    def __init__(self):
        self.samples_called=0
        self.original=np.arange(256,dtype='f4')*.125
    def samples(self,channel):
        assert channel==1
        self.samples_called+=1
        return self.original,64.,{},'synthetic.bin'


@pytest.mark.parametrize('mode',['ac','acdc'])
@pytest.mark.parametrize('order',['chronological','getsignal_buffer'])
def test_one_preparation_many_mouse_pixels_without_rereading_archive(mode,order):
    from mvk_compatible.core.signal_idr_candidate import unfiltered_getsignal
    session=FakeSession()
    stored=session.original.copy()
    window=prepare_waveform_hover_window(session,1,start_s=1.,seconds=2.,
                                         mode=mode,display_order=order)
    assert session.samples_called==1
    expected=unfiltered_getsignal(stored[64:192],64.,no_dc=(mode=='ac'))
    for i in range(64,192):
        selection=window.pick(i/64.)
        from_display=i
        original=(i if order=='chronological' else 191-(i-64))
        assert selection['display_index']==from_display
        assert selection['index']==original
        assert selection['value_m_s2']==float(expected.chronological[original-64])
        assert selection['time_s']==pytest.approx(from_display/64.)
        assert selection['original_sample_time_s']==pytest.approx(original/64.)
        assert selection['source']==SOURCE
        assert selection['original_mousemove_handler_source_verified']
        assert not selection['original_plot_coordinate_parity_verified']
        assert not selection['original_Delphi_CursorString_parity_verified']
    assert session.samples_called==1
    np.testing.assert_array_equal(session.original,stored)


def test_mouse_hover_rejects_outside_without_guessing_or_padding():
    obj=prepare_waveform_hover_window(FakeSession(),1,start_s=1.,seconds=2.,
                                     mode='acdc',display_order='chronological')
    for p in (0.,.99999,3.,3.5,float('nan'),float('inf'),-1.):
        with pytest.raises(ValueError,match='outside|finite'):
            obj.pick(p)
    p=obj.pick(1.01)
    assert p['display_index']==65
    p=obj.pick(2.999)
    assert p['display_index']==191


@pytest.mark.parametrize('invalid',[
    {'channel':0}, {'channel':9},{'channel':True},
    {'mode':'envelope'},{'mode':'unknown'},{'display_order':'unknown'},
    {'start_s':-1.},{'start_s':float('nan')},{'seconds':0.},
    {'seconds':32.},{'seconds':float('inf')}])
def test_hover_source_requires_explicit_safe_window(invalid):
    args=dict(channel=1,start_s=1.,seconds=2.,mode='ac',
              display_order='chronological')
    args.update(invalid)
    session=FakeSession()
    with pytest.raises(ValueError):
        prepare_waveform_hover_window(session,args.pop('channel'),**args)
    assert session.samples_called==0


def test_hover_source_refuses_empty_window_and_zero_length_archive():
    session=FakeSession()
    with pytest.raises(ValueError,match='empty'):
        prepare_waveform_hover_window(session,1,start_s=10.,seconds=1.,
                                      mode='ac',display_order='chronological')


def test_hover_cache_matches_existing_offline_exact_sample_contract(tmp_path):
    from mvk_compatible.core import OfflineSession
    from mvk_compatible.tests.test_offline_core import fixture_zip
    session=OfflineSession.open(fixture_zip(tmp_path))
    for mode in ('ac','acdc'):
        for order in ('chronological','getsignal_buffer'):
            cached=prepare_waveform_hover_window(
                session,1,start_s=0.,seconds=.0625,
                mode=mode,display_order=order)
            for t in (0.,31/65536,1024/65536,4095/65536):
                previous=session.exact_sample(
                    1,t,0.,.0625,mode,order)
                fast=cached.pick(t)
                assert fast['index']==previous['index']
                assert fast['display_index']==previous['display_index']
                assert fast['value_m_s2']==previous['value_m_s2']
                assert fast['original_sample_time_s']==previous['original_sample_time_s']
