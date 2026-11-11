"""Stage111Z31AZ: local-only spectrum bitmap audit, synthetic frames."""
import copy
import numpy as np
import pytest

from mvk_compatible.core.tqgrapher_canvas_idr_candidate import (
    source_canvas_geometry,
)
from mvk_compatible.core.spectrum_graph_pixel_audit import (
    make_source_pixel_manifest, compare_local_graph_pixel_audit,
)


def _fixture():
    canvas = source_canvas_geometry(
        pixel_width=240,pixel_height=180,margin=10,
        zero_text_width=8,six_decimals_text_width=64,
        zero_text_height=16,
        scr_left=0.,scr_width=5000.,scr_bottom=-150.,
        scr_height=150.,series_x_start=0.,series_x_scale=.25)
    f = np.full((180,240,4),255,dtype=np.uint8)
    f[canvas['pixel_top']+10,canvas['pixel_left']:canvas['pixel_right'],:3]=192
    f[canvas['pixel_top']:canvas['pixel_bottom'],canvas['pixel_left']+30,:3]=0
    f[18:27,18:23,:3]=0  # axis-label ink, outside source PixelRect
    spectrum=dict(mode=0, n_fft=1024,df_hz=0.25,
                  amplitude=np.linspace(-100.,0.,512,dtype='<f4'))
    manifest=make_source_pixel_manifest(
        f,canvas,spectrum=spectrum,
        view_x=(0.,5000.),view_y=(-150.,0.),
        qt_device_pixel_ratio=1.5,
        textout_diagnostics={
            'requested_font_face':'Tahoma','requested_font_height':-13,
            'gdi_width_zero':9,'gdi_width_sixdecimals':72,
            'gdi_height_zero':16,
            'private_original_filename':'NEVER_EXPORT',
        })
    return f,canvas,spectrum,manifest


def test_manifest_whitelisted_source_geometry_fft_signature_and_dpi():
    f,canvas,spectrum,m=_fixture()
    assert m['paintbox_size_logical_wh']==[240,180]
    assert m['source_pixel_rect_ltrb']==[
        canvas['pixel_left'],canvas['pixel_top'],
        canvas['pixel_right'],canvas['pixel_bottom']]
    assert m['qt_device_pixel_ratio_observed']==1.5
    assert m['spectrum_display_bin_count']==len(spectrum['amplitude'])
    assert m['font_metrics_candidate']['gdi_width_zero']==9
    assert 'private_original_filename' not in str(m)
    assert 'amplitude' not in m
    assert not m['original_capture_provenance_independently_authenticated']
    assert not m['real_original_pixel_parity_verified']
    # Export only whitelisted diagnostics, not source path or raw FFT.
    assert all(type(v) in (int,float,str,bool,list,dict) for v in m.values())


def test_perfect_synthetic_crops_are_not_original_attestation():
    f,canvas,spectrum,m=_fixture()
    original=f.copy()
    result=compare_local_graph_pixel_audit(
        original,f,m,operator_declared_same_measurement_and_window=True)
    assert result['exact_rgb_equal_without_alignment']
    assert not result['independent_capture_authentication']
    assert not result['complete_mvkview_pixel_parity_verified']
    assert result['operator_declared_same_measurement_and_window']
    assert result['full_canvas']['pixels_compared']==240*180
    assert result['source_pixel_rect']['informative_ink_pixels']>0
    assert result['axes_text_and_margins']['informative_ink_pixels']>0
    assert result['source_pixel_rect']['mean_abs_rgb_channel_error']==0.
    assert result['axes_text_and_margins']['mean_abs_rgb_channel_error']==0.
    assert 'pixels' not in result


def test_axis_and_trace_are_independently_scored_and_candidate_input_unchanged():
    f,c,s,m=_fixture()
    original=f.copy()
    before=f.copy()
    original[c['pixel_top']+5,c['pixel_left']+6,:3]=[255,0,0]
    original[20,19,:3]=[0,0,0] if np.any(f[20,19,:3]) else [255,255,255]
    report=compare_local_graph_pixel_audit(original,f,m,shift_radius=2)
    assert not report['exact_rgb_equal_without_alignment']
    assert report['source_pixel_rect']['pixels_any_rgb_channel_gt_1']>=1
    assert report['axes_text_and_margins']['pixels_any_rgb_channel_gt_1']>=1
    assert report['best_shift_candidate'] is not None
    assert report['shift_search_is_diagnostic_not_acceptance']
    np.testing.assert_array_equal(f,before)


@pytest.mark.parametrize('tamper',[
    lambda f,m: (f.copy(),{**m,'paintbox_size_logical_wh':[240,181]}),
    lambda f,m: (f.copy(),{**m,'candidate_rgba_sha256':'0'*64}),
    lambda f,m: (f.copy(),{**m,'source_pixel_rect_ltrb':[0,0,1000,1000]}),
    lambda f,m: (f.copy(),{**m,'format':'unexpected'}),
    lambda f,m: (f[:,:-1].copy(),m),
])
def test_original_pixel_compare_fails_closed_on_mismatch(tamper):
    f,c,s,m=_fixture()
    candidate,manifest=tamper(f,m)
    with pytest.raises(ValueError):
        compare_local_graph_pixel_audit(f,candidate,manifest)


def test_blank_screenshot_does_not_pass_and_manifest_guards():
    f,c,s,m=_fixture()
    blank=np.full_like(f,255)
    with pytest.raises(ValueError):
        compare_local_graph_pixel_audit(blank,blank,m)
    with pytest.raises(ValueError):
        make_source_pixel_manifest(
            f,c,spectrum={**s,'mode':5},
            view_x=(0.,5000.),view_y=(-150.,0.),
            qt_device_pixel_ratio=1.5)
    with pytest.raises(ValueError):
        make_source_pixel_manifest(
            f,c,spectrum=s,view_x=(5000.,0.),view_y=(-150.,0.),
            qt_device_pixel_ratio=1.5)
    with pytest.raises(ValueError):
        compare_local_graph_pixel_audit(
            f,f,m,operator_declared_same_measurement_and_window='yes')
    assert m['font_metrics_candidate']['requested_font_height']==-13
