"""Stage111N private geometry sweep QA: all references are synthetic."""
import json
import numpy as np
import pytest

from mvk_compatible.canvas_sweep_reference_compare import (
    compare_canvas_sweep,main)
from mvk_compatible.core.tqgrapher_canvas_idr_candidate import source_canvas_geometry


def metrics(scr_width=200.,scr_height=2.):
    return dict(pixel_width=800,pixel_height=500,margin=10,
        zero_text_width=8,six_decimals_text_width=64,zero_text_height=14,
        x_name_present=True,y_name_present=True,scr_left=80.,
        scr_width=scr_width,scr_bottom=-1.,scr_height=scr_height,
        series_x_start=0.,series_x_scale=2.)


def synthetic_cases():
    cases=[]
    for width,height,dpi in [(200.,2.,96),(-40.,2.,144),(0.,0.,192)]:
        inp=metrics(width,height)
        model=source_canvas_geometry(**inp)
        reference={k:model[k] for k in
            ('pixel_left','pixel_right','pixel_top','pixel_bottom',
             'itos_m','stoi_m','ytos_m')}
        cases.append({'metrics':inp,'original':reference,'dpi':dpi})
    return {'cases':cases}


def test_source_batch_compares_each_case_without_revealing_metrics():
    cases=synthetic_cases()
    summary=compare_canvas_sweep(cases,
        operator_confirmed_same_canvas=True)
    assert summary['case_count']==3
    assert summary['passing_case_count']==3
    assert summary['all_cases_within_supplied_tolerances']
    assert summary['case_results'][1]['x_reversed'] is True
    assert summary['case_results'][2]['source_scr_width_clamped']
    assert summary['case_results'][2]['source_scr_height_clamped']
    assert summary['case_results'][0]['operator_dpi_declared']
    assert summary['delphi_pixel_font_dpi_parity_verified'] is False
    assert summary['delphi_x87_numerical_parity_verified'] is False
    assert 'metrics' not in summary
    assert 'original' not in summary


def test_source_batch_requires_all_cases_match_and_does_not_autofit():
    cases=synthetic_cases()
    cases['cases'][1]['original']['pixel_left']+=1
    diff=compare_canvas_sweep(cases)
    assert diff['passing_case_count']==2
    assert not diff['all_cases_within_supplied_tolerances']
    assert diff['case_results'][1]['absolute_errors']['pixel_left']==1
    assert diff['max_absolute_errors_by_field']['pixel_left']==1


def test_private_sweep_cli_exit_codes_and_sha(tmp_path,capsys):
    source=tmp_path/'canvas-private.json'
    doc=synthetic_cases()
    source.write_text(json.dumps(doc),encoding='utf-8')
    target=tmp_path/'summary-private.json'
    assert main(['--cases',str(source),'--report-json',str(target)])==0
    summary=json.loads(capsys.readouterr().out)
    assert len(summary['cases_file_sha256'])==64
    assert target.exists()
    assert not summary['delphi_pixel_font_dpi_parity_verified']
    doc['cases'][0]['original']['pixel_bottom']+=4
    source.write_text(json.dumps(doc),encoding='utf-8')
    assert main(['--cases',str(source)])==1
    err=json.loads(capsys.readouterr().out)
    assert err['case_results'][0]['absolute_errors']['pixel_bottom']==4


@pytest.mark.parametrize('bad',[
    {}, {'cases':[]}, {'cases':'fake'}, {'cases':[{}]},
    {'cases':[{'metrics':{},'original':{}}]},
    {'cases':[{'metrics':metrics(),'original':{'unknown':1}}]},
    {'cases':[{'metrics':metrics(),'original':{'pixel_left':True}}]},
    {'cases':[{'metrics':metrics(),'original':{'pixel_left':1},'dpi':0}]},
    {'cases':[{'metrics':metrics(),'original':{'pixel_left':1},'dpi':'96'}]},
])
def test_strict_measurement_contract_rejects_unverified_reference(bad):
    with pytest.raises(ValueError):
        compare_canvas_sweep(bad)


def test_invalid_tolerances_rejected_without_guess():
    with pytest.raises(ValueError):
        compare_canvas_sweep(synthetic_cases(),pixel_tolerance=-.1)
    with pytest.raises(ValueError):
        compare_canvas_sweep(synthetic_cases(),coefficient_tolerance=float('nan'))


def test_private_input_symlink_rejected(tmp_path):
    target=tmp_path/'source.json'
    target.write_text(json.dumps(synthetic_cases()),encoding='utf-8')
    link=tmp_path/'alias.json'
    link.symlink_to(target)
    with pytest.raises(SystemExit) as error:
        main(['--cases',str(link)])
    assert error.value.code==2
