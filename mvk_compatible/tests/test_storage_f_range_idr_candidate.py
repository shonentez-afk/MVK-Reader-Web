"""Stage111J test original float ring scaling vs Native calibrated BIN.

All test samples are artificial; FRange for any actual MVK instrument unknown.
"""
import numpy as np
import pytest
from mvk_compatible.core.storage_f_range_idr_candidate import (
    prepare_original_fft_input,DOMAIN_ORIGINAL_STORAGE,DOMAIN_CALIBRATED_BIN)
from mvk_compatible.core import OfflineSession
from mvk_compatible.tests.test_offline_core import fixture_zip


def test_original_storage_read_divides_f32_before_dc_once():
    raw=np.array([0.,2.,4.,8.],dtype='f4')
    before=raw.copy()
    d=prepare_original_fft_input(raw,f_range=4.,input_domain=DOMAIN_ORIGINAL_STORAGE)
    np.testing.assert_array_equal(d['samples_before_dc_removal'],[0.,.5,1.,2.])
    np.testing.assert_array_equal(raw,before)
    assert d['original_storage_read_divided_by_range']
    assert not d['original_source_buffer_provenance_verified']


def test_native_calibrated_bin_not_treated_as_original_float_storage_by_default():
    d=prepare_original_fft_input([0.,2.,4.],f_range=4.)
    assert d['input_domain']==DOMAIN_CALIBRATED_BIN
    assert not d['original_storage_read_divided_by_range']
    np.testing.assert_array_equal(d['samples_before_dc_removal'],[0.,2.,4.])


@pytest.mark.parametrize('bad',['guess','original_byte_storage','',None])
def test_unknown_storage_domain_refused(bad):
    with pytest.raises(ValueError,match='domain'):
        prepare_original_fft_input([1.,2.],f_range=1.,input_domain=bad)


@pytest.mark.parametrize('bad',[float('nan'),float('inf')])
def test_nonfinite_buffer_rejected(bad):
    with pytest.raises(ValueError,match='finite'):
        prepare_original_fft_input([1.,bad])


def test_source_storage_path_neutralizes_f_range_for_linear_spectrum(tmp_path):
    session=OfflineSession.open(fixture_zip(tmp_path))
    ref=session.spectrum(1,4096,1,start_s=0.,backend='numpy',
                         max_hz=32768,max_points=2048,
                         f_range=1.,input_domain=DOMAIN_CALIBRATED_BIN)
    original_ring=session.spectrum(1,4096,1,start_s=0.,backend='numpy',
                         max_hz=32768,max_points=2048,
                         f_range=4.,input_domain=DOMAIN_ORIGINAL_STORAGE)
    post_only=session.spectrum(1,4096,1,start_s=0.,backend='numpy',
                         max_hz=32768,max_points=2048,
                         f_range=4.,input_domain=DOMAIN_CALIBRATED_BIN)
    a=np.asarray(ref['amplitude'])
    b=np.asarray(original_ring['amplitude'])
    c=np.asarray(post_only['amplitude'])
    idx=int(np.argmax(a))
    assert a[idx]>0
    assert b[idx]==pytest.approx(a[idx],rel=1e-5)
    assert c[idx]==pytest.approx(a[idx]*4.,rel=1e-5)
    assert original_ring['original_storage_read_divided_by_range']
    assert original_ring['original_source_buffer_provenance_verified'] is False
    assert original_ring['input_domain']==DOMAIN_ORIGINAL_STORAGE
    assert not post_only['original_storage_read_divided_by_range']
    # ORIGINAL buffer assumption requires evidence and is never automatic.
    assert session.calculations()['source']=='MVK_DSP'


def test_mode_zero_original_storage_path_has_different_log_amplitude(tmp_path):
    session=OfflineSession.open(fixture_zip(tmp_path))
    direct=session.spectrum(1,4096,0,start_s=0.,backend='numpy',
                           max_hz=32768,max_points=2048,f_range=4.)
    stored=session.spectrum(1,4096,0,start_s=0.,backend='numpy',
                           max_hz=32768,max_points=2048,f_range=4.,
                           input_domain=DOMAIN_ORIGINAL_STORAGE)
    idx=int(np.argmax(direct['amplitude']))
    assert direct['amplitude'][idx]-stored['amplitude'][idx]==pytest.approx(
        20*np.log10(4.),rel=1e-5)


def test_backend_and_cursor_share_explicit_input_domain(tmp_path):
    session=OfflineSession.open(fixture_zip(tmp_path))
    d=session.compare_fft_backends(1,4096,1,0.,f_range=4.,
                                   input_domain=DOMAIN_ORIGINAL_STORAGE)
    assert d['input_domain']==DOMAIN_ORIGINAL_STORAGE
    assert not d['original_delphi_parity_verified']
