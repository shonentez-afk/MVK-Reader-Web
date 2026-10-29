"""Stage111G: synthetic-only local candidate Copy/Save, no production exports."""
from pathlib import Path
import pytest
from mvk_compatible.core.spectrum_summary_export_candidate import (
    spectrum_triplet_text,append_research_summary_csv,RESEARCH_HEADER)
from mvk_compatible.core.spectrum_metrics_idr_candidate import original_spectrum_summary
import numpy as np


def metrics():
    a=np.zeros(512,dtype='f4')
    a[40:43]=[5,10,3]
    return original_spectrum_summary(a,n_fft=1024,fs_out=32768)


def test_copy_triplet_has_exact_original_three_field_tab_structure():
    text=spectrum_triplet_text(metrics(),decimal_separator=',')
    fields=text.split('\t')
    assert len(fields)==3
    assert all(field for field in fields)
    assert all('\n' not in x and '\r' not in x for x in fields)
    assert ',' in fields[0] or ',' in fields[2]


def test_source_based_copy_never_accepts_instrument_aux_data():
    x=metrics()
    x['source']='MVK_DSP_AUX4700'
    with pytest.raises(ValueError,match='Source-derived'):
        spectrum_triplet_text(x)


def test_copy_pipe_and_decimal_dot_is_explicit_candidate():
    text=spectrum_triplet_text(metrics(),separator='|',decimal_separator='.')
    assert len(text.split('|'))==3
    assert '\t' not in text


def test_local_save_header_and_safe_append(tmp_path):
    target=tmp_path/'candidate.csv'
    a=append_research_summary_csv(target,metrics())
    b=append_research_summary_csv(target,metrics())
    raw=target.read_bytes()
    assert raw.startswith(('sep=|\r\n'+RESEARCH_HEADER+'\r\n').encode('utf-8'))
    assert raw.count(b'sep=|')==1
    assert len(raw.decode('utf-8').splitlines())==4
    assert '|' in raw.decode('utf-8').splitlines()[2]
    assert not a['original_delphi_export_format_verified']
    assert a['row_values']==b['row_values']==3


def test_original_vendor_csv_is_not_silently_appended(tmp_path):
    target=tmp_path/'SPEC-FREQ-2026-10-29.csv'
    target.write_text('sep=|\r\noriginal vendor header\r\n1|2|3\r\n',encoding='utf-8')
    original=target.read_bytes()
    with pytest.raises(ValueError,match='original MVKView'):
        append_research_summary_csv(target,metrics())
    assert target.read_bytes()==original


def test_local_save_refuses_symlink_and_non_csv(tmp_path):
    orig=tmp_path/'orig.csv';orig.write_text('private data')
    link=tmp_path/'link.csv';link.symlink_to(orig)
    with pytest.raises(ValueError):
        append_research_summary_csv(link,metrics())
    with pytest.raises(ValueError):
        append_research_summary_csv(tmp_path/'bad.txt',metrics())


def test_local_save_rejects_infinite_and_bad_separator():
    x=metrics();x['output_peak_y']=float('inf')
    with pytest.raises(ValueError):spectrum_triplet_text(x)
    with pytest.raises(ValueError):spectrum_triplet_text(metrics(),separator=',')


def test_baseline_archived_getspectrum_populates_source_derived_summary(tmp_path):
    from mvk_compatible.core import OfflineSession
    from mvk_compatible.tests.test_offline_core import fixture_zip
    session=OfflineSession.open(fixture_zip(tmp_path))
    d=session.spectrum(1,4096,1,0,max_hz=32768,max_points=2048,backend='numpy')
    s=d['spectrum_summary']
    assert s['source']=='APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE'
    assert s['n_fft']==4096 and s['summary_last_bin']==1600
    assert s['df_hz']==16
    assert not s['original_delphi_numerical_parity_verified']
    assert d['source']=='APP_DERIVED_FFT_MVKVIEW_CANDIDATE'


def test_mode_two_integrates_original_power_before_peak_summary(tmp_path):
    from mvk_compatible.core import OfflineSession
    from mvk_compatible.tests.test_offline_core import fixture_zip
    s=OfflineSession.open(fixture_zip(tmp_path))
    a=s.spectrum(1,4096,1,0,max_hz=32768,max_points=2048,backend='numpy')
    b=s.spectrum(1,4096,2,0,max_hz=32768,max_points=2048,backend='numpy')
    assert a['spectrum_summary']['spectrum_mode']==1
    assert b['spectrum_summary']['spectrum_mode']==2
    assert a['spectrum_summary']['raw_total_band_power']!=b['spectrum_summary']['raw_total_band_power']


def test_envelope_spectrum_includes_same_source_provenance():
    from mvk_compatible.core.envelope_spectrum_idr_candidate import (
        envelope_spectrum_idr_candidate,required_original_history)
    from mvk_compatible.tests.test_envelope_idr_candidate import fake_profile
    n=1024;p=required_original_history(n,65536,20)
    x=np.arange(p['input_samples'],dtype='f4')
    d=envelope_spectrum_idr_candidate(x,65536,20,fake_profile(),
        n_fft=n,mode=1,backend='numpy')
    s=d['spectrum_summary']
    assert s['output_mean']>=0
    assert s['n_fft']==n
    assert s['spectrum_mode']==1
    assert s['source']=='APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE'
