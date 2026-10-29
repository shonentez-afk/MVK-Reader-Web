"""Stage111H: private original Copy triplet comparator, synthetic only."""
import json
import numpy as np
import pytest

from mvk_compatible.triplet_reference_compare import (
    parse_operator_triplet, read_operator_triplet_file, compare_operator_triplet,
    LABELS, main
)
from mvk_compatible.core.spectrum_summary_export_candidate import spectrum_triplet_text

SOURCE='APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE'


def summary():
    return {'source':SOURCE,'output_mean':1.2345,
            'output_peak_frequency_hz':1234.456,
            'output_peak_y':0.03456}


def reference(*values):
    return {'source':'OPERATOR_SUPPLIED_ORIGINAL_TRIPLET',
            'sha256':'abc','values':values}


def test_tab_copy_triplet_with_decimal_comma():
    assert parse_operator_triplet('1,23\t1234,5\t0,03456\r\n')==(1.23,1234.5,.03456)


def test_pipe_original_triplet_with_dot():
    assert parse_operator_triplet('1.23|1234.5|0.03456',separator='|',
                                  decimal_separator='.')==(1.23,1234.5,.03456)


@pytest.mark.parametrize('bad',[
    '1,2\t3,4', '1,2\t3,4\t5,6\t7,8', '1,2\t3,4\tNaN',
    '1,2\t3,4\tInfinity', '1,2\t3,4\t5,6\n1,2\t3,4\t5,6',
    '1.2\t3,4\t5,6', '1,2;3,4;5,6', '1,2\t3,4\t'])
def test_invalid_triplets_refused_without_auto_guessing(bad):
    with pytest.raises(ValueError):parse_operator_triplet(bad)


def test_reader_file_cp1251_local_sha(tmp_path):
    path=tmp_path/'original-local.txt'
    path.write_bytes('1,23\t4,567\t8,90\r\n'.encode('cp1251'))
    d=read_operator_triplet_file(path,encoding='cp1251')
    assert d['field_count']==3
    assert d['values']==(1.23,4.567,8.9)
    assert len(d['sha256'])==64


def test_reader_refuses_symlink(tmp_path):
    original=tmp_path/'original.txt'
    original.write_text('1\t2\t3')
    symlink=tmp_path/'copy.txt'
    symlink.symlink_to(original)
    with pytest.raises(ValueError):read_operator_triplet_file(symlink)


def test_numerical_match_never_claims_delphi_parity():
    result=compare_operator_triplet(summary(),reference(1.2345,1234.456,.03456))
    assert result['within_supplied_tolerances']
    assert not result['original_delphi_parity_verified']
    assert not result['original_display_text_parity_verified']
    assert not result['operator_confirmed_same_signal_and_window']
    assert result['field_count']==3
    assert set(result['absolute_errors'])==set(LABELS)


def test_errors_are_per_field_and_window_claim_is_not_certification():
    x=compare_operator_triplet(summary(),reference(1.2345,1400.,.0456),
                               abs_tolerance=.00001,rel_tolerance=.001,
                               operator_confirmed_same_window=True)
    assert x['within_tolerance_per_field']['output_mean']
    assert not x['within_tolerance_per_field']['output_peak_frequency_hz']
    assert not x['within_tolerance_per_field']['output_peak_y']
    assert x['operator_confirmed_same_signal_and_window']
    assert not x['original_delphi_parity_verified']


def test_reject_instrument_dsp_as_getspectrum_candidate():
    s=summary();s['source']='MVK_DSP_AUX4700'
    with pytest.raises(ValueError):compare_operator_triplet(s,reference(1.,2.,3.))


@pytest.mark.parametrize('bad',[-1,float('inf'),float('nan')])
def test_invalid_comparison_tolerance_rejected(bad):
    with pytest.raises(ValueError):
        compare_operator_triplet(summary(),reference(1.,2.,3.),
                                 rel_tolerance=bad)


def test_complete_offline_candidate_vs_operator_text_cli(tmp_path,capsys):
    from mvk_compatible.core import OfflineSession
    from mvk_compatible.tests.test_offline_core import fixture_zip
    zip_path=fixture_zip(tmp_path)
    summary_data=OfflineSession.open(zip_path).spectrum(
        1,4096,1,start_s=0,max_hz=32768,max_points=2048,
        backend='numpy')['spectrum_summary']
    copied=spectrum_triplet_text(summary_data,separator='\t',decimal_separator=',')
    reference_path=tmp_path/'operator-synthetic.txt'
    reference_path.write_text(copied,encoding='utf-8')
    report_path=tmp_path/'private-report.json'
    code=main(['--archive',str(zip_path),'--reference',str(reference_path),
               '--channel','1','--n-fft','4096','--mode','1',
               '--start-s','0','--backend','numpy',
               '--report-json',str(report_path)])
    assert code==0
    report=json.loads(capsys.readouterr().out)
    assert report['within_supplied_tolerances']
    assert report['field_count']==3
    assert report['reference_sha256']
    assert report['candidate_display_text_equal'] is True
    assert not report['original_delphi_parity_verified']
    assert 'original_samples' not in report
    assert 'frequency_hz' not in report
    assert report_path.is_file()


def test_stage111i_text_comparison_is_distinct_from_numeric_match():
    candidate={'source':SOURCE,'output_mean':1.,'output_peak_frequency_hz':2.,
               'output_peak_y':3.}
    original={'source':'OPERATOR_SUPPLIED_ORIGINAL_TRIPLET',
              'values':(1.,2.,3.),'sha256':'synthetic',
              'original_text_local_only':'1,0\t2,0\t3,0',
              'delimiter':'\t','decimal_separator':','}
    result=compare_operator_triplet(candidate,original)
    assert result['within_supplied_tolerances'] is True
    assert result['candidate_display_text_equal'] is False
    assert result['candidate_display_text_comparison']=='EXACT_CHARACTERS_NOT_DELPHI_RTL_PARITY'
    assert not result['original_display_text_parity_verified']
    assert 'original_text_local_only' not in result


def test_stage111i_exact_copy_text_only_when_all_three_fields_match():
    s=summary()
    from mvk_compatible.core.spectrum_summary_export_candidate import spectrum_triplet_text
    candidate_text=spectrum_triplet_text(s,decimal_separator=',')
    orig={'source':'OPERATOR_SUPPLIED_ORIGINAL_TRIPLET',
          'values':parse_operator_triplet(candidate_text),
          'sha256':'synthetic',
          'original_text_local_only':candidate_text,
          'delimiter':'\t','decimal_separator':','}
    matched=compare_operator_triplet(s,orig)
    assert matched['candidate_display_text_equal'] is True
    assert matched['within_supplied_tolerances']
    assert not matched['original_delphi_parity_verified']
    orig['original_text_local_only']=candidate_text+' '
    # Original parser rejects malformed space only when used as number; directly
    # supplied in-memory fixture tests exact formatting independently.
    mismatch=compare_operator_triplet(s,orig)
    assert mismatch['candidate_display_text_equal'] is False


def test_stage111i_cli_strict_text_match_rejects_redundant_zero(tmp_path,capsys):
    from mvk_compatible.core import OfflineSession
    from mvk_compatible.tests.test_offline_core import fixture_zip
    from mvk_compatible.core.spectrum_summary_export_candidate import spectrum_triplet_text
    archive=fixture_zip(tmp_path)
    data=OfflineSession.open(archive).spectrum(
        1,4096,1,start_s=0,max_hz=32768,max_points=2048,backend='numpy')
    text=spectrum_triplet_text(data['spectrum_summary'],decimal_separator=',')
    fields=text.split('\t')
    fields[0]+= '0' if ',' in fields[0] else ',0'
    ref=tmp_path/'synthetic-original.txt'
    ref.write_text('\t'.join(fields),encoding='utf-8')
    arg=['--archive',str(archive),'--reference',str(ref),
         '--channel','1','--n-fft','4096','--mode','1',
         '--start-s','0','--backend','numpy']
    assert main(arg)==0  # Numeric tolerance passes.
    out=json.loads(capsys.readouterr().out)
    assert out['within_supplied_tolerances']
    assert out['candidate_display_text_equal'] is False
    assert main(arg+['--require-display-text'])==1
    strict=json.loads(capsys.readouterr().out)
    assert strict['display_text_match_required']
    assert strict['candidate_display_text_equal'] is False
    assert not strict['original_delphi_parity_verified']


def test_stage111j_original_ring_triplet_reference_cli(tmp_path,capsys):
    from mvk_compatible.core import OfflineSession
    from mvk_compatible.tests.test_offline_core import fixture_zip
    archive=fixture_zip(tmp_path)
    session=OfflineSession.open(archive)
    summ=session.spectrum(1,4096,1,start_s=0,max_hz=32768,
          max_points=2048,backend='numpy',f_range=4.,
          input_domain='original_float_storage')['spectrum_summary']
    copied=spectrum_triplet_text(summ,decimal_separator=',')
    file=tmp_path/'candidate-storage-triplet.txt'
    file.write_text(copied,encoding='utf-8')
    assert main(['--archive',str(archive),'--reference',str(file),
        '--channel','1','--n-fft','4096','--mode','1',
        '--start-s','0','--backend','numpy','--f-range','4',
        '--input-domain','original_float_storage','--require-display-text'])==0
    d=json.loads(capsys.readouterr().out)
    assert d['candidate_input_domain']=='original_float_storage'
    assert d['candidate_original_float_storage_verified'] is False
    assert d['candidate_display_text_equal'] is True
    assert not d['original_delphi_parity_verified']
