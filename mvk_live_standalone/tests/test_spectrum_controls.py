"""Four vibration spectrum presets: exactly the controls used by an operator."""
import pytest

from mvk_live_standalone.spectrum_controls import (
    VIEW_MODES,FILTER_CHOICES,X_LIMITS_HZ,Y_WIDTH_CHOICES,
    x_limit_hz,y_height_options,visible_y_range,view_settings,
)


def test_four_views_are_not_three_unrelated_selectors():
    assert [(label,key) for label,key,_,_ in VIEW_MODES]==[
        ("Логарифмическая (ВУ, дБ)","log_vu"),
        ("Линейный ВУ","linear_vu"),
        ("Линейный ВС","linear_vs"),
        ("Линейный ВП","linear_vp"),
    ]
    assert view_settings("log_vu")==("acceleration","db")
    assert view_settings("linear_vu")==("acceleration","linear")
    assert view_settings("linear_vs")==("velocity","linear")
    assert view_settings("linear_vp")==("displacement","linear")
    with pytest.raises(ValueError):
        view_settings("audio")


def test_filter_selections_are_explicit_default_is_off():
    assert FILTER_CHOICES[0]==("Без фильтра","none")
    assert {key for _,key in FILTER_CHOICES}=={
        "none","highpass","lowpass","bandpass","notch50","notch60",
        "octave","third_octave","double_octave"}


def test_x_is_50_through_25600_and_never_exceeds_actual_nyquist():
    assert X_LIMITS_HZ[0]==50 and X_LIMITS_HZ[-1]==25600
    assert x_limit_hz(50,65536)==(50,False)
    assert x_limit_hz(25600,65536)==(25600,False)
    assert x_limit_hz(25600,32768)==(16384,True)
    assert x_limit_hz(1000,512)==(256,True)
    assert x_limit_hz(25600,None)==(25600,False)
    with pytest.raises(ValueError):
        x_limit_hz(30000,65536)
    with pytest.raises(ValueError):
        x_limit_hz(1000,0)


def test_y_choices_use_the_exact_physical_vibration_units():
    assert y_height_options("log_vu")[0]==("Авто",None)
    assert all(label.endswith(" дБ") for label,_ in y_height_options("log_vu")[1:])
    assert all(label.endswith(" м/с²") for label,_ in y_height_options("linear_vu")[1:])
    assert all(label.endswith(" мм/с") for label,_ in y_height_options("linear_vs")[1:])
    assert all(label.endswith(" мкм") for label,_ in y_height_options("linear_vp")[1:])
    assert Y_WIDTH_CHOICES["log_vu"][:2]==(20,40)


def test_linear_y_starts_at_zero_and_db_shows_true_db_data():
    assert visible_y_range([.1,2.0,3.0],"linear",10)==(0,10)
    assert visible_y_range([.1,2.0,3.0],"linear",None)[1]==pytest.approx(3.45)
    assert visible_y_range([-82.0,-30.0,-26.0],"db",40)==(-50, -10)
    assert visible_y_range([-82.0,-30.0,-26.0],"db",None)==(-90,-10)
    for bad in (0,-1,float("nan")):
        with pytest.raises(ValueError):
            visible_y_range([0,1],"linear",bad)
