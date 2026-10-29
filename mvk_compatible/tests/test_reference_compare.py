"""Stage111F local original reference comparison QA; synthetic only."""
import json
import hashlib
import numpy as np
import pytest
from mvk_compatible.reference_compare import (
    read_original_two_column_csv,compare_full_spectrum)


def data(n=16):
    f=(np.arange(n)*16.).tolist()
    y=np.linspace(1,10,n).tolist()
    candidate={'frequency_hz':f,'amplitude':y,'channel':4,
               'code':20,'n_fft':32,'mode':1,'output_sample_rate_hz':512}
    original={'frequency_hz':f,'amplitude':y,'sha256':'abc'}
    return candidate,original


def test_identical_synthetic_curves_only_numeric_match():
    a,b=data()
    p=compare_full_spectrum(a,b)
    assert p['within_supplied_numeric_tolerance']
    assert p['original_app_parity_certified'] is False
    assert p['original_metadata_status']=='NOT_PROVIDED'
    assert p['max_absolute_difference']==0.
    assert p['n_bins_compared']==16
    assert p['out_of_tolerance_bins']==0


def test_shifted_frequency_grid_is_strictly_rejected():
    a,b=data(); b['frequency_hz']=b['frequency_hz'].copy();b['frequency_hz'][4]+=1
    with pytest.raises(ValueError,match='Frequency-grid mismatch'):
        compare_full_spectrum(a,b)
    b['frequency_hz'][4]-=1
    a['frequency_hz']+= [256]
    with pytest.raises(ValueError,match='same full finite'):
        compare_full_spectrum(a,b)


def test_amplitude_difference_is_reported_without_interpolation():
    a,b=data()
    b['amplitude']=b['amplitude'].copy()
    b['amplitude'][3]+=2
    p=compare_full_spectrum(a,b,relative_tolerance=.01,absolute_tolerance=1e-3)
    assert not p['within_supplied_numeric_tolerance']
    assert p['out_of_tolerance_bins']==1
    assert p['max_absolute_difference']==pytest.approx(2)


def test_reference_metadata_is_operator_assertion_not_proof():
    a,b=data()
    meta={'source_app':'MVKView','confirmed_same_signal_and_window':True,
          'channel':4,'envelope_code':20,'n_fft':32,'mode':1,
          'output_sample_rate_hz':512,'original_csv_sha256':'abc'}
    p=compare_full_spectrum(a,b,original_metadata=meta)
    assert p['original_metadata_status']=='OPERATOR_ASSERTED_MATCH'
    assert not p['original_app_parity_certified']
    meta['n_fft']=1024
    assert compare_full_spectrum(a,b,original_metadata=meta)['original_metadata_status']=='MISMATCH_OR_INCOMPLETE'


def test_csv_semicolon_decimal_comma_and_sha(tmp_path):
    f=tmp_path/'source.csv'
    f.write_text('frequency_hz;amplitude\n0,0;1,5\n16,0;2,5\n32,0;3,125\n',encoding='utf-8')
    d=read_original_two_column_csv(f)
    assert d['row_count']==3
    assert d['frequency_hz'].tolist()==[0,16,32]
    assert d['amplitude'].tolist()==[1.5,2.5,3.125]
    assert d['sha256']==hashlib.sha256(f.read_bytes()).hexdigest()


def test_csv_tab_decimal_dot(tmp_path):
    f=tmp_path/'original.tsv'
    f.write_text('frequency_hz\tamplitude\n0\t0\n8.5\t3.1\n')
    d=read_original_two_column_csv(f,delimiter='\t',decimal='.')
    assert d['frequency_hz'].tolist()==[0,8.5]


@pytest.mark.parametrize('text',[
    'Hz;value\n0;1\n10;2\n',
    'frequency_hz;amplitude\n0;1\n0;2\n',
    'frequency_hz;amplitude\n0;nan\n1;2\n',
    'frequency_hz;amplitude\n0;2\n',
    'frequency_hz;amplitude\n0;1;extra\n1;2\n'
])
def test_bad_reference_csv_never_passes_silently(tmp_path,text):
    f=tmp_path/'bad.csv';f.write_text(text,encoding='utf-8')
    with pytest.raises(ValueError):read_original_two_column_csv(f)


def test_refuse_invalid_tol():
    a,b=data()
    for t in (-1.,float('nan'),float('inf')):
        with pytest.raises(ValueError):compare_full_spectrum(a,b,absolute_tolerance=t)


def test_reference_is_local_only_no_network():
    import inspect
    import mvk_compatible.reference_compare as m
    s=inspect.getsource(m)
    for token in ('import socket','import requests','import fastapi','urlopen','http.client'):
        assert token not in s


def test_complete_private_comparator_cli_with_synthetic_reference(tmp_path,monkeypatch,capsys):
    """End-to-end CLI under synthetic test injection; no original IDP is read."""
    from mvk_compatible.core import OfflineSession
    from mvk_compatible.core.envelope_idr_candidate import EnvelopeProfile
    from mvk_compatible.tests.test_envelope_idr_candidate import fake_profile
    from mvk_compatible.tests.test_offline_core import fixture_zip
    from mvk_compatible.reference_compare import main
    archive=fixture_zip(tmp_path)
    profile=fake_profile(i=1.,q=.4)
    monkeypatch.setattr(EnvelopeProfile,'from_original_local_idp',
                        classmethod(lambda cls,path:profile))
    expected=OfflineSession.open(archive).spectrum_envelope(
        1,20,1024,profile,end_s=.0625,mode=1,backend='numpy')
    reference=tmp_path/'synthetic-reference.csv'
    with reference.open('w',encoding='utf-8') as out:
        out.write('frequency_hz;amplitude\n')
        for f,a in zip(expected['frequency_hz'],expected['amplitude']):
            out.write(f'{f!r};{a!r}\n')
    private_report=tmp_path/'local-report.json'
    ret=main(['--archive',str(archive),'--idp',str(tmp_path/'fake.idp'),
        '--reference',str(reference),'--channel','1','--code','20',
        '--n-fft','1024','--mode','1','--end-s','0.0625',
        '--backend','numpy','--decimal','.','--report-json',str(private_report)])
    assert ret==0
    status=json.loads(capsys.readouterr().out)
    assert status['n_bins_compared']==512
    assert status['within_supplied_numeric_tolerance']
    assert not status['original_app_parity_certified']
    assert status['original_metadata_status']=='NOT_PROVIDED'
    assert private_report.is_file()
    assert 'amplitude' not in status and 'frequency_hz' not in status
