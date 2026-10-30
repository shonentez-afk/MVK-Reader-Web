"""Stage111U: synthetic original branch tests, FRange provenance remains false."""
import math
import pytest
from mvk_compatible.core.spectrum_graph_default_vscale_idr_candidate import (
    SOURCE, MODE_MULTIPLIERS, spectrum_graph_default_vscale)


def test_source_uses_selected_channel_f_range_and_mode_multipliers():
    assert MODE_MULTIPLIERS == (1, 1, 10, 100)
    assert [spectrum_graph_default_vscale(1., i)['source_mode_multiplier']
            for i in range(4)] == [1, 1, 10, 100]
    for mode, expected in ((0, 1.), (1, 1.), (2, 10.), (3, 100.)):
        info = spectrum_graph_default_vscale(1., mode)
        assert info['candidate_graph_default_vscale_single'] == pytest.approx(expected)
        assert info['mode_scaled_f_range_single'] == pytest.approx(expected)
        assert info['source'] == SOURCE
        assert info['source_multiply_mode_and_125_branch_verified']
        assert not info['local_f_range_is_original_channel_frange_verified']
        assert not info['original_math_helpers_x87_rounding_verified']
        assert not info['original_delphi_graph_default_vscale_numeric_parity_verified']
        assert not info['original_qt_y_canvas_parity_verified']


@pytest.mark.parametrize('f_range, expected', [
    (.031, .05),(.081,.1),(.31,.5),(.81,1.),(1.1,2.),(3.1,5.),
    (7.1,10.),(12.1,20.),(31.,50.),(51.,100.),
])
def test_nice_125_decade_step_on_non_boundary_values(f_range,expected):
    result=spectrum_graph_default_vscale(f_range,1)
    assert result['candidate_graph_default_vscale_single'] == pytest.approx(expected, rel=1e-6)
    assert result['independent_exact_125_ceiling']==pytest.approx(expected)


def test_float32_stores_and_original_exact_thresholds_are_not_falsely_accepted():
    for raw in (0.2, 0.5, 2., 5., 10., 20.):
        x=spectrum_graph_default_vscale(raw,1)
        assert math.isfinite(x['candidate_graph_default_vscale_single'])
        assert x['candidate_graph_default_vscale_single']>0
        assert not x['original_math_helpers_x87_rounding_verified']
        assert not x['original_delphi_graph_default_vscale_numeric_parity_verified']


def test_modes_2_and_3_precede_decimal_rounding():
    assert spectrum_graph_default_vscale(.31,2)['candidate_graph_default_vscale_single']==pytest.approx(5.)
    assert spectrum_graph_default_vscale(.31,3)['candidate_graph_default_vscale_single']==pytest.approx(50.)


@pytest.mark.parametrize('bad,mode', [
    (0.,1),(-1.,1),(float('nan'),1),(float('inf'),1),
    (1.,-1),(1.,4),(1.,True),(1.,'1'),(True,1),
    (1e40,1),(3e38,3),(1e-48,1)
])
def test_bad_inputs_or_float32_overflow_fail_closed(bad,mode):
    with pytest.raises(ValueError): spectrum_graph_default_vscale(bad,mode)

@pytest.mark.parametrize('input_range,candidate,ideal',[(2.,5.,2.),(5.,10.,5.),(20.,50.,20.)])
def test_single_precision_log_threshold_differences_must_be_disclosed(input_range,candidate,ideal):
    """Candidate-only artefact: source x87 exact thresholds are NOT measured."""
    report=spectrum_graph_default_vscale(input_range,1)
    assert report['candidate_graph_default_vscale_single']==pytest.approx(candidate)
    assert report['independent_exact_125_ceiling']==pytest.approx(ideal)
    assert report['ideal_matches_reconstructed_single'] is False
    assert report['original_math_helpers_x87_rounding_verified'] is False
