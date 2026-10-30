"""Stage111R synthetic Qt logical scene <-> original TPaintBox diagnostic."""
import pytest
from mvk_compatible.core.tqgrapher_qt_canvas_bridge_candidate import (
    QtPaintBoxBridge,compare_measured_landmarks,SOURCE)
from mvk_compatible.core.tqgrapher_paintbox_registration_idr_candidate import source_paintbox_registration


def canvas(**kw):
    d=dict(pixel_width=800,pixel_height=500,zero_text_width=8,
           six_decimals_text_width=64,zero_text_height=14)
    d.update(kw)
    return source_paintbox_registration(**d)


def bridge(**kw):
    d=dict(source_canvas=canvas(),qt_scene_left=30.,qt_scene_right=730.,
           qt_scene_top=40.,qt_scene_bottom=440.,qt_device_pixel_ratio=1.5)
    d.update(kw)
    return QtPaintBoxBridge(**d)


def test_source_rect_has_independent_qt_to_native_affine_and_dpi_annotation():
    b=bridge()
    assert b.source_canvas['pixel_left']==87
    assert b.source_canvas['pixel_right']==785
    assert b.x_scale == pytest.approx(698/700.)
    assert b.y_scale == pytest.approx(426/400.)
    assert b.scene_to_paintbox(30.,40.)==(87.,15.)
    assert b.scene_to_paintbox(730.,440.)==(785.,441.)
    assert b.paintbox_to_scene(87.,15.)==(30.,40.)
    assert b.paintbox_to_scene(785.,441.)==(730.,440.)
    assert b.native_mouse_integer_candidate(30.)==87
    assert b.native_mouse_integer_candidate(380.)==436
    detail=b.describe()
    assert detail['source']==SOURCE
    assert detail['qt_device_pixel_ratio_observed']==1.5
    assert detail['device_pixel_ratio_not_applied_to_native_transform']
    assert not detail['original_delphi_pixel_parity_verified']
    assert not detail['native_mouse_integer_rounding_parity_verified']


def test_dpr_2_changes_only_provenance_not_native_scene_mapping():
    first=bridge(qt_device_pixel_ratio=1.)
    second=bridge(qt_device_pixel_ratio=2.)
    assert first.scene_to_paintbox(333.,209.)==second.scene_to_paintbox(333.,209.)


def test_measured_landmarks_have_private_error_only_report():
    b=bridge()
    expected=b.scene_to_paintbox(400.,180.)
    info=compare_measured_landmarks(b,[{'qt_scene_x':400.,'qt_scene_y':180.,
                        'native_x':expected[0],'native_y':expected[1]}])
    assert info['all_landmarks_within_tolerance']
    assert not info['original_runtime_canvas_parity_verified']
    assert 'qt_scene_x' not in str(info)
    bad=compare_measured_landmarks(b,[{'qt_scene_x':400.,'qt_scene_y':180.,
                        'native_x':expected[0]+5,'native_y':expected[1]}])
    assert not bad['all_landmarks_within_tolerance']
    assert bad['absolute_errors'][0]['error_x_native_px']==pytest.approx(5.)


@pytest.mark.parametrize('bad',[
    {'qt_scene_right':30.},{'qt_scene_bottom':40.},{'qt_scene_left':float('nan')},
    {'qt_scene_right':float('inf')},{'qt_device_pixel_ratio':0.},
    {'qt_device_pixel_ratio':False},{'qt_device_pixel_ratio':30.},
    {'source_canvas':{}},
])
def test_invalid_calibration_fails_closed(bad):
    with pytest.raises(ValueError):bridge(**bad)


def test_original_falsely_verified_flags_refused():
    d=canvas();d['original_pixel_rectangle_verified']=True
    with pytest.raises(ValueError,match='fabricated'):
        bridge(source_canvas=d)


def test_invalid_landmarks_and_tolerances_refused():
    b=bridge()
    with pytest.raises(ValueError):compare_measured_landmarks(b,[])
    with pytest.raises(ValueError):compare_measured_landmarks(b,[{'qt_scene_x':1}])
    with pytest.raises(ValueError):compare_measured_landmarks(b,[{'qt_scene_x':2,'qt_scene_y':3,
                'native_x':0.,'native_y':0.}],tolerance_native_px=-1.)
