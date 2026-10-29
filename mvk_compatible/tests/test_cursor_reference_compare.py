"""Stage111L local original CursorString and pixel reference, synthetic-only."""
import json
import numpy as np
import pytest
from mvk_compatible.cursor_reference_compare import main,compare_cursor_candidate
from mvk_compatible.core.tqgrapher_multiseries_idr_candidate import original_multiseries_cursor
from mvk_compatible.core.tqgrapher_canvas_idr_candidate import source_canvas_geometry


def metrics():
    return dict(pixel_width=200,pixel_height=150,margin=10,zero_text_width=8,
        six_decimals_text_width=12,zero_text_height=10,x_name_present=False,
        y_name_present=False,scr_left=0.,scr_width=3200.,
        scr_bottom=0.,scr_height=1.,series_x_start=0.,series_x_scale=32.)


def synth(tmp_path):
    met=tmp_path/'original-canvas.private.json'
    met.write_text(json.dumps(metrics()),encoding='utf-8')
    arr=np.zeros(100,dtype='f4');arr[18]=3
    sig=tmp_path/'full-series0.private.npy';np.save(sig,arr)
    canvas=source_canvas_geometry(**metrics())
    # 008482... display source originally uses its own absolute pixel coords.
    pixel=canvas['pixel_left']+int(round(18*canvas['itos_m']))
    result=original_multiseries_cursor(arr,pixel=pixel,canvas=canvas,averaging=1)
    reference=tmp_path/'operator-copy.private.txt'
    reference.write_bytes(result['cursor_string'].encode('utf-8'))
    return met,sig,reference,pixel,result


def test_private_reference_without_printing_contents(tmp_path,capsys):
    met,sig,txt,pixel,result=synth(tmp_path)
    report=tmp_path/'diff.private.json'
    exit_code=main(['--metrics',str(met),'--series0',str(sig),
        '--reference',str(txt),'--pixel',str(pixel),
        '--line-pixel',str(result['snapped_vertical_pixel']),
        '--report-json',str(report),'--confirm-same-canvas'])
    assert exit_code==0
    output=capsys.readouterr().out
    d=json.loads(output)
    assert d['exact_cursor_string_equal']
    assert d['line_pixel_absolute_error']==0
    assert d['per_line_equal']==[True,True]
    assert d['operator_confirmed_same_canvas_and_archive']
    assert not d['original_pixel_parity_verified']
    assert not d['original_delphi_rtl_parity_verified']
    assert result['cursor_string'] not in output
    assert report.is_file()


def test_reference_detects_text_formatting_difference_without_original_content(tmp_path,capsys):
    met,sig,txt,pixel,result=synth(tmp_path)
    txt.write_bytes(result['cursor_string'].replace('\r\n','\n').encode('utf-8'))
    assert main(['--metrics',str(met),'--series0',str(sig),
                 '--reference',str(txt),'--pixel',str(pixel)])==1
    d=json.loads(capsys.readouterr().out)
    assert d['exact_cursor_string_equal'] is False
    assert d['first_different_character_index'] is not None
    assert d['original_line_count']==1
    assert not d['original_delphi_rtl_parity_verified']


def test_wrong_line_pixel_keeps_text_match_but_rejects(tmp_path,capsys):
    met,sig,txt,pixel,result=synth(tmp_path)
    assert main(['--metrics',str(met),'--series0',str(sig),
        '--reference',str(txt),'--pixel',str(pixel),
        '--line-pixel',str(result['snapped_vertical_pixel']+1)])==1
    d=json.loads(capsys.readouterr().out)
    assert d['exact_cursor_string_equal']
    assert d['line_pixel_absolute_error']==1


def test_symlink_reference_is_rejected(tmp_path):
    met,sig,txt,pixel,result=synth(tmp_path)
    link=tmp_path/'link.txt';link.symlink_to(txt)
    with pytest.raises(SystemExit) as e:
        main(['--metrics',str(met),'--series0',str(sig),
              '--reference',str(link),'--pixel',str(pixel)])
    assert e.value.code==2


def test_nonfinite_or_pickle_array_is_rejected(tmp_path):
    met,sig,txt,pixel,result=synth(tmp_path)
    np.save(sig,np.array([{'bad':'object'}],dtype=object),allow_pickle=True)
    with pytest.raises(SystemExit) as e:
        main(['--metrics',str(met),'--series0',str(sig),
              '--reference',str(txt),'--pixel',str(pixel)])
    assert e.value.code==2


def test_invalid_original_number_of_metrics_rejected(tmp_path):
    met,sig,txt,pixel,result=synth(tmp_path)
    met.write_text(json.dumps({'pixel_width':200}),encoding='utf-8')
    with pytest.raises(SystemExit) as e:
        main(['--metrics',str(met),'--series0',str(sig),
              '--reference',str(txt),'--pixel',str(pixel)])
    assert e.value.code==2


def test_reference_summary_does_not_include_sensitive_values():
    c={'drawn':True,'cursor_string':'123 Гц\r\n0,125 м/с²',
       'snapped_vertical_pixel':25}
    d=compare_cursor_candidate(c,c['cursor_string'])
    assert d['exact_cursor_string_equal']
    assert '123 Гц' not in json.dumps(d)
    assert 'cursor_string' not in d
    assert not d['original_source_sample_parity_verified']


def test_exact_text_does_not_silently_strip_terminal_crlf():
    candidate={'drawn':True,'cursor_string':'12 Гц\r\n5 мм/с',
               'snapped_vertical_pixel':24}
    result=compare_cursor_candidate(candidate,candidate['cursor_string']+'\r\n')
    assert result['exact_cursor_string_equal'] is False
    assert result['original_line_count']==3
    assert result['first_different_character_index']==len(candidate['cursor_string'])


def test_stage111m_private_horizontal_crosshair_cli_exact_pixel(tmp_path,capsys):
    from mvk_compatible.core.tqgrapher_crosshair_idr_candidate import original_cursor_crosshair
    met,sig,txt,pixel,selection=synth(tmp_path)
    native_canvas=source_canvas_geometry(**metrics())
    crosshair=original_cursor_crosshair(selection,native_canvas)
    assert len(crosshair['horizontal_pixels'])==1
    expected=crosshair['horizontal_pixels'][0]
    args=['--metrics',str(met),'--series0',str(sig),
          '--reference',str(txt),'--pixel',str(pixel),
          '--horizontal-pixels',str(expected),
          '--line-pixel',str(selection['snapped_vertical_pixel'])]
    assert main(args)==0
    result=json.loads(capsys.readouterr().out)
    assert result['horizontal_pixel_absolute_errors']==[0]
    assert result['horizontal_pixel_exact_match'] is True
    assert result['horizontal_line_count_match'] is True
    assert result['exact_cursor_string_equal']
    assert not result['original_pixel_parity_verified']
    assert selection['cursor_string'] not in json.dumps(result)


def test_stage111m_original_horizontal_error_is_not_auto_corrected(tmp_path,capsys):
    from mvk_compatible.core.tqgrapher_crosshair_idr_candidate import original_cursor_crosshair
    met,sig,txt,pixel,selection=synth(tmp_path)
    crosshair=original_cursor_crosshair(selection,source_canvas_geometry(**metrics()))
    expected=crosshair['horizontal_pixels'][0]
    args=['--metrics',str(met),'--series0',str(sig),
          '--reference',str(txt),'--pixel',str(pixel),
          '--horizontal-pixels',str(expected+1)]
    assert main(args)==1
    result=json.loads(capsys.readouterr().out)
    assert result['horizontal_pixel_absolute_errors']==[1]
    assert result['horizontal_pixel_exact_match'] is False
    assert result['exact_cursor_string_equal'] is True


def test_stage111m_horizontal_count_mismatch_is_rejected(tmp_path,capsys):
    from mvk_compatible.core.tqgrapher_crosshair_idr_candidate import original_cursor_crosshair
    met,sig,txt,pixel,selection=synth(tmp_path)
    horizontal=original_cursor_crosshair(selection,source_canvas_geometry(**metrics()))
    one=horizontal['horizontal_pixels'][0]
    args=['--metrics',str(met),'--series0',str(sig),
          '--reference',str(txt),'--pixel',str(pixel),
          '--horizontal-pixels',f'{one},{one}']
    assert main(args)==1
    result=json.loads(capsys.readouterr().out)
    assert result['horizontal_line_count_match'] is False
    assert result['horizontal_pixel_absolute_errors'] is None


@pytest.mark.parametrize('bad',['',',','1,2,3','nan','1,inf','10.5','-','true'])
def test_stage111m_invalid_horizontal_operator_reference_fails_closed(tmp_path,bad):
    met,sig,txt,pixel,_=synth(tmp_path)
    with pytest.raises(SystemExit) as result:
        main(['--metrics',str(met),'--series0',str(sig),
              '--reference',str(txt),'--pixel',str(pixel),
              '--horizontal-pixels',bad])
    assert result.value.code==2


def test_stage111m_direct_comparison_does_not_leak_horizontal_coordinates():
    data={'drawn':True,'cursor_string':'12 Гц\r\n8 м/с²',
          'snapped_vertical_pixel':45,'horizontal_pixels':[72,84]}
    from mvk_compatible.cursor_reference_compare import compare_cursor_candidate
    d=compare_cursor_candidate(data,data['cursor_string'],
                               original_horizontal_pixels=[72,84],
                               original_line_pixel=45)
    assert d['horizontal_pixel_absolute_errors']==[0,0]
    assert d['horizontal_pixel_exact_match']
    assert 'horizontal_pixels' not in d
    assert not d['original_pixel_parity_verified']
