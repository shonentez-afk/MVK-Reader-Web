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
    assert fmt(0.126,significant_digits=2)=='0.13'


@pytest.mark.parametrize('digit',[0,-1,13,True])
def test_reject_unverified_digit_modes(digit):
    with pytest.raises(ValueError):fmt(1.2,significant_digits=digit)


def test_invalid_locale_rejected_instead_of_guess():
    with pytest.raises(ValueError):fmt(1.2,decimal_separator=';')


def test_float32_source_is_explicit():
    x=np.float32(.125)
    assert fmt(float(x))=='0.125'


def test_stage111k_source_dynamic_mask_007b2090_exact_number_of_digits():
    from mvk_compatible.core.cursor_format_candidate import cursor_decimal_mask_candidate as mask
    assert mask(12.25)['mask']=='0.00'
    assert mask(0.125)['mask']=='0.0000'
    assert mask(1000.25)['mask']=='0.'
    assert mask(.000125)['mask']=='0.0000000'
    assert mask(2.5,significant_digits=3)['mask']=='0.00'
    assert mask(-2.5)['source_single']==float(np.float32(-2.5))
    assert not mask(12.25)['original_delphi_rtl_verified']


def test_stage111k_007b2090_zero_nan_and_smallest_single():
    from mvk_compatible.core.cursor_format_candidate import cursor_decimal_mask_candidate as mask
    assert mask(0.)['special']=='ZERO'
    assert mask(-0.)['special']=='ZERO'
    assert mask(float('nan'))['special']=='NAN'
    smallest=float(np.nextafter(np.float32(0),np.float32(1)))
    d=mask(smallest)
    assert 40<d['decimal_places']<60
    assert d['mask']=='0.'+'0'*d['decimal_places']


def test_stage111k_formatting_and_pattern_are_separate_parity_claims():
    from mvk_compatible.core.cursor_format_candidate import cursor_decimal_mask_candidate as mask
    m=mask(12.25,decimal_separator=',')
    assert m['mask']=='0.00'  # Delphi FormatFloat mask is locale-independent.
    assert fmt(12.25,decimal_separator=',')=='12,25'
    assert m['decimal_separator']==','
    assert m['original_delphi_rtl_verified'] is False
