"""Stage111I: FRange calibration provenance regression; all measurements SYNTHETIC.

Original _Unit115 constructor 007D0A61 -> FRange Single=1.0;
GetSpectrum uses FRange in linear and aggregate outputs.
This NEVER asserts archive/ADC calibration has been recovered.
"""
import json
import numpy as np
import pytest

from mvk_compatible.core import OfflineSession
from .test_offline_core import fixture_zip


@pytest.fixture
def session(tmp_path):
    return OfflineSession.open(fixture_zip(tmp_path))


def full(session,mode,scale=None,backend='numpy'):
    return session.spectrum(
        1,4096,mode,start_s=0.,max_hz=32768,max_points=2048,
        backend=backend,f_range=scale)


def test_plain_spectrum_explicit_one_same_data_but_not_same_provenance(session):
    a=full(session,1)
    b=full(session,1,1.)
    np.testing.assert_array_equal(a['amplitude'],b['amplitude'])
    assert a['f_range_used']==b['f_range_used']==1.
    assert a['f_range_source']=='DEFAULT_ONE_NOT_CALIBRATION_VERIFIED'
    assert b['f_range_source']=='OPERATOR_SUPPLIED_UNVERIFIED'
    assert a['original_f_range_verified'] is False
    assert b['spectrum_summary']['f_range']==1.


@pytest.mark.parametrize('mode',[1,2,3])
def test_linear_modes_scale_once_without_changing_raw_bin_frequency(session,mode):
    original=full(session,mode)
    changed=full(session,mode,2.5)
    values=np.asarray(original['amplitude'])
    values2=np.asarray(changed['amplitude'])
    idx=int(np.argmax(values))
    assert values[idx]>0
    assert values2[idx]==pytest.approx(values[idx]*2.5,rel=1e-5)
    assert changed['spectrum_summary']['output_mean']==pytest.approx(
        original['spectrum_summary']['output_mean']*2.5,rel=1e-5)
    assert changed['spectrum_summary']['output_peak_y']==pytest.approx(
        original['spectrum_summary']['output_peak_y']*2.5,rel=1e-5)
    assert changed['spectrum_summary']['output_peak_x_bin']==pytest.approx(
        original['spectrum_summary']['output_peak_x_bin'],rel=1e-7)
    assert changed['f_range_applied_to_display']
    assert changed['f_range_source']=='OPERATOR_SUPPLIED_UNVERIFIED'
    assert changed['original_f_range_verified'] is False


def test_log_mode_is_range_invariant_but_aggregates_are_not(session):
    a=full(session,0)
    b=full(session,0,3.)
    np.testing.assert_array_equal(a['amplitude'],b['amplitude'])
    assert not b['f_range_applied_to_display']
    assert b['spectrum_summary']['output_mean']==pytest.approx(
        3*a['spectrum_summary']['output_mean'],rel=1e-5)


@pytest.mark.parametrize('bad',[False,True,0,-1,float('inf'),float('nan'),1e-99,1e99])
def test_invalid_f_range_fails_closed(session,bad):
    with pytest.raises(ValueError,match='FRange'):
        full(session,1,bad)


def test_default_narrowband_dsp_unaffected_by_user_range(session):
    instrument=session.calculations()
    a=session.narrowband(1,64.,n_fft=4096,start_s=0.,backend='numpy',f_range=1)
    b=session.narrowband(1,64.,n_fft=4096,start_s=0.,backend='numpy',f_range=2.5)
    assert b['output_value']==pytest.approx(a['output_value']*2.5,rel=1e-6)
    assert session.calculations()==instrument
    assert instrument['source']=='MVK_DSP'


def test_backend_comparison_uses_one_identical_range(session):
    d=session.compare_fft_backends(1,4096,1,0.,f_range=2.5)
    assert d['f_range_used']==2.5
    assert d['f_range_source']=='OPERATOR_SUPPLIED_UNVERIFIED'
    assert not d['original_delphi_parity_verified']


def test_triplet_comparator_explicit_plain_calibration_path(tmp_path,capsys):
    from mvk_compatible.triplet_reference_compare import main
    from mvk_compatible.core.spectrum_summary_export_candidate import spectrum_triplet_text
    archive=fixture_zip(tmp_path)
    session=OfflineSession.open(archive)
    spectrum=session.spectrum(1,4096,1,start_s=0.,max_hz=32768,
                              max_points=2048,backend='numpy',f_range=2.5)
    text=spectrum_triplet_text(spectrum['spectrum_summary'],decimal_separator=',')
    ref=tmp_path/'synthetic-copy.txt'
    ref.write_text(text,encoding='utf-8')
    code=main(['--archive',str(archive),'--reference',str(ref),
        '--channel','1','--n-fft','4096','--mode','1','--start-s','0',
        '--backend','numpy','--f-range','2.5'])
    assert code==0
    report=json.loads(capsys.readouterr().out)
    assert report['within_supplied_tolerances']
    assert report['candidate_f_range_used']==2.5
    assert report['candidate_f_range_source']=='OPERATOR_SUPPLIED_UNVERIFIED'
    assert not report['candidate_f_range_original_verified']
    assert not report['candidate_window_origin_verified']
    assert not report['original_delphi_parity_verified']
    assert 'values' not in report


def test_separate_reference_calibration_mismatch_detected(tmp_path,capsys):
    from mvk_compatible.triplet_reference_compare import main
    from mvk_compatible.core.spectrum_summary_export_candidate import spectrum_triplet_text
    archive=fixture_zip(tmp_path)
    session=OfflineSession.open(archive)
    spectrum=full(session,1)
    txt=spectrum_triplet_text(spectrum['spectrum_summary'],decimal_separator=',')
    ref=tmp_path/'synthetic-original-copy.txt'
    ref.write_text(txt,encoding='utf-8')
    code=main(['--archive',str(archive),'--reference',str(ref),
        '--channel','1','--n-fft','4096','--mode','1','--start-s','0',
        '--backend','numpy','--f-range','5'])
    report=json.loads(capsys.readouterr().out)
    assert code==1
    assert not report['within_supplied_tolerances']
    assert report['candidate_f_range_used']==5.
    assert not report['original_delphi_parity_verified']


def test_stage111i_source_single_is_not_python_double():
    from mvk_compatible.core.calibration_candidate import resolve_f_range
    candidate=1.234567890123
    got,source=resolve_f_range(candidate)
    assert got==float(np.float32(candidate))
    assert got!=candidate
    assert source=='OPERATOR_SUPPLIED_UNVERIFIED'
    assert resolve_f_range(None)==(1.,'DEFAULT_ONE_NOT_CALIBRATION_VERIFIED')


@pytest.mark.parametrize('value',[0.,-1.,float('nan'),float('inf'),1e-99,1e99,True,'1'])
def test_stage111i_all_invalid_single_ranges_fail_closed(value):
    from mvk_compatible.core.calibration_candidate import resolve_f_range
    with pytest.raises(ValueError,match='FRange'):
        resolve_f_range(value)


def test_stage111i_envelope_and_narrowband_provenance_are_consistent(session):
    from mvk_compatible.tests.test_envelope_idr_candidate import fake_profile
    a=session.narrowband(1,64.,n_fft=4096,backend='numpy')
    b=session.narrowband(1,64.,n_fft=4096,backend='numpy',f_range=2.5)
    assert a['f_range_source']=='DEFAULT_ONE_NOT_CALIBRATION_VERIFIED'
    assert b['f_range_source']=='OPERATOR_SUPPLIED_UNVERIFIED'
    assert not b['original_f_range_verified']
    c=session.spectrum_envelope(1,20,1024,fake_profile(),end_s=.0625,backend='numpy')
    d=session.spectrum_envelope(1,20,1024,fake_profile(),end_s=.0625,
                                backend='numpy',f_range=2.5)
    assert c['f_range_source']=='DEFAULT_ONE_NOT_CALIBRATION_VERIFIED'
    assert d['f_range_source']=='OPERATOR_SUPPLIED_UNVERIFIED'
    assert d['f_range_used']==2.5
    assert d['spectrum_summary']['output_peak_y']==pytest.approx(
        c['spectrum_summary']['output_peak_y']*2.5,rel=1e-5)


def test_stage111i_direct_envelope_and_narrowband_fail_on_single_overflow():
    from mvk_compatible.tests.test_envelope_idr_candidate import fake_profile
    from mvk_compatible.core.envelope_spectrum_idr_candidate import (
        required_original_history,envelope_spectrum_idr_candidate)
    from mvk_compatible.core.narrowband_idr_candidate import narrowband_from_full_power
    with pytest.raises(ValueError,match='FRange'):
        narrowband_from_full_power(np.zeros(512,dtype='f4'),
            n_fft=1024,sample_rate_hz=32768,
            input_frequency_hz=1600.,f_range=1e99)
    n=required_original_history(1024,65536,20)['input_samples']
    with pytest.raises(ValueError,match='FRange'):
        envelope_spectrum_idr_candidate(np.zeros(n,dtype='f4'),65536,20,
            fake_profile(),n_fft=1024,backend='numpy',f_range=1e99)
