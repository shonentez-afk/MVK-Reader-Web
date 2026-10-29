"""Stage111E synthetic Delphi formatter candidate QA; not exact RTL parity."""
import numpy as np
import pytest
from mvk_compatible.core.cursor_format_candidate import format_cursor_idr_candidate as fmt


@pytest.mark.parametrize('number,expected',[
 (0,'0'),(-0.0,'0'),(2.,'2'),(-2.5,'-2.5'),
 (12.25,'12.25'),(0.125,'0.125'),(1000.25,'1000'),
 (0.000125,'0.000125')])
def test_float32_dynamic_four_digit_format(number,expected):
    assert fmt(number)==expected


def test_original_isnan_007b1cc0_and_nonnumeric_inf():
    assert fmt(float('nan'))=='NAN'
    with pytest.raises(ValueError,match='infinity'):
        fmt(float('inf'))
    with pytest.raises(ValueError,match='infinity'):
        fmt(float('-inf'))


def test_explicit_tformatsettings_decimal_comma():
    assert fmt(12.25,decimal_separator=',')=='12,25'
    assert fmt(1.5,decimal_separator='.')=='1.5'


def test_bigger_significant_argument_changes_places():
    assert fmt(12.25,significant_digits=5)=='12.25'
    assert fmt(0.125,significant_digits=2)=='0.13'


@pytest.mark.parametrize('digit',[0,-1,13,True])
def test_reject_unverified_digit_modes(digit):
    with pytest.raises(ValueError):fmt(1.2,significant_digits=digit)


def test_invalid_locale_rejected_instead_of_guess():
    with pytest.raises(ValueError):fmt(1.2,decimal_separator=';')


def test_float32_source_is_explicit():
    x=np.float32(.125)
    assert fmt(float(x))=='0.125'
