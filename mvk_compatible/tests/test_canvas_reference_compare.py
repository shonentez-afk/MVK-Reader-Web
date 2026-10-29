"""Stage111K private original Canvas comparison, synthetic fixtures only."""
import json
import pytest
from mvk_compatible.core.tqgrapher_canvas_idr_candidate import source_canvas_geometry
from mvk_compatible.canvas_reference_compare import main,reference_geometry_comparison


def synthetic_metrics():
    return dict(pixel_width=800,pixel_height=500,margin=10,
        zero_text_width=8,six_decimals_text_width=64,zero_text_height=14,
        x_name_present=True,y_name_present=True,scr_left=0.,scr_width=200.,
        scr_bottom=-1.,scr_height=2.,series_x_start=0.,series_x_scale=2.)


def test_original_geometry_model_comparison_never_certifies_delphi():
    model=source_canvas_geometry(**synthetic_metrics())
    r=reference_geometry_comparison(model,dict(pixel_left=82,pixel_right=790,
        pixel_top=10,pixel_bottom=446,itos_m=model['itos_m']))
    assert r['within_supplied_tolerances']
    assert not r['original_delphi_pixel_parity_verified']
    assert not r['original_font_metrics_parity_verified']
    assert not r['original_x87_numeric_parity_verified']
    assert r['compared_fields']==[
        'pixel_left','pixel_right','pixel_top','pixel_bottom','itos_m']


def test_unequal_pixel_and_operator_assertion_do_not_certify_parity():
    model=source_canvas_geometry(**synthetic_metrics())
    r=reference_geometry_comparison(model,{'pixel_left':84},pixel_tolerance=0,
                                    operator_confirmed_same_canvas=True)
    assert r['absolute_errors']['pixel_left']==2
    assert not r['within_supplied_tolerances']
    assert r['operator_confirmed_same_canvas_and_font']
    assert not r['original_delphi_pixel_parity_verified']


@pytest.mark.parametrize('original',[{}, {'unknown':1}, {'pixel_left':float('nan')},
                                    {'pixel_left':True},{'pixel_right':'4'}])
def test_invalid_original_geometry_refused(original):
    with pytest.raises(ValueError):
        reference_geometry_comparison(source_canvas_geometry(**synthetic_metrics()),
                                      original)


def test_complete_local_geometry_cli_reports_only_error_and_sha(tmp_path,capsys):
    metrics=tmp_path/'canvas-private.json'
    original=tmp_path/'original-private.json'
    out=tmp_path/'comparison-private.json'
    metrics.write_text(json.dumps(synthetic_metrics()),encoding='utf-8')
    original.write_text(json.dumps({'pixel_left':82,'pixel_right':790,
            'pixel_top':10,'pixel_bottom':446}),encoding='utf-8')
    code=main(['--metrics',str(metrics),'--reference',str(original),
        '--report-json',str(out),'--confirm-same-canvas'])
    assert code==0
    report=json.loads(capsys.readouterr().out)
    assert report['within_supplied_tolerances']
    assert report['metrics_sha256'] and report['reference_sha256']
    assert report['operator_confirmed_same_canvas_and_font']
    assert not report['original_delphi_pixel_parity_verified']
    assert 'pixel_left' in report['absolute_errors']
    assert 'reference_values' not in report
    assert out.is_file()


def test_cli_strict_pixel_mismatch_returns_one(tmp_path,capsys):
    metrics=tmp_path/'canvas-private.json'
    original=tmp_path/'original-private.json'
    metrics.write_text(json.dumps(synthetic_metrics()),encoding='utf-8')
    original.write_text(json.dumps({'pixel_left':99}),encoding='utf-8')
    code=main(['--metrics',str(metrics),'--reference',str(original)])
    assert code==1
    report=json.loads(capsys.readouterr().out)
    assert not report['within_supplied_tolerances']
    assert not report['original_delphi_pixel_parity_verified']


def test_cli_refuses_incomplete_metrics(tmp_path):
    metrics=tmp_path/'canvas-private.json'
    original=tmp_path/'original-private.json'
    metrics.write_text(json.dumps({'pixel_width':800}),encoding='utf-8')
    original.write_text(json.dumps({'pixel_left':82}),encoding='utf-8')
    with pytest.raises(SystemExit) as exc:
        main(['--metrics',str(metrics),'--reference',str(original)])
    assert exc.value.code==2
