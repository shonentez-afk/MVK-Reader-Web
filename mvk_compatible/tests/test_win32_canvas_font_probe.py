"""Stage111Q independent GDI memory HFONT metrics; no original MVKView."""
import json
import sys
import pytest
from mvk_compatible.win32_canvas_font_probe import (
    SOURCE,measure_win32_font_metrics,main)


@pytest.mark.parametrize('family,height,weight,italic',[
    ('',-13,400,False),('A'*32,-13,400,False),
    ('Tahoma\x00hack',-13,400,False),('Tahoma',0,400,False),
    ('Tahoma',513,400,False),('Tahoma',-513,400,False),
    ('Tahoma',-13,0,False),('Tahoma',-13,1001,False),
    ('Tahoma',-13,400,1),('Tahoma',True,400,False)])
def test_font_requires_explicit_safe_windows_spec(family,height,weight,italic):
    with pytest.raises(ValueError):
        measure_win32_font_metrics(family,height,weight=weight,italic=italic)


def test_real_windows_font_measurements_or_unavailable_platform():
    if sys.platform!='win32':
        with pytest.raises(RuntimeError,match='native Windows'):
            measure_win32_font_metrics('Arial',-14)
        return
    r=measure_win32_font_metrics('Arial',-14)
    assert r['source']==SOURCE
    assert r['text_width_six_decimals']>r['text_width_zero']>0
    assert r['text_height_zero']>0
    assert r['gdi_dpi_x']>0 and r['gdi_dpi_y']>0
    assert r['font_actual_selected']
    assert r['all_three_metrics_same_selected_gdi_font']
    assert r['original_delphi_tcanvas_font_verified'] is False
    assert r['original_tpaintbox_dpi_verified'] is False
    assert r['qt_font_metrics_equivalent_verified'] is False


def test_native_font_probe_cli_is_local_only(tmp_path,capsys):
    if sys.platform!='win32':
        with pytest.raises(SystemExit) as exc:
            main(['--font-family','Arial','--font-height-px','-14'])
        assert exc.value.code==2
        return
    out=tmp_path/'font-gdi-candidate.json'
    assert main(['--font-family','Arial','--font-height-px','-14',
                 '--report-json',str(out)])==0
    report=json.loads(capsys.readouterr().out)
    assert report==json.loads(out.read_text(encoding='utf-8'))
    assert report['font_actual_selected']
    assert report['original_delphi_tcanvas_font_verified'] is False
