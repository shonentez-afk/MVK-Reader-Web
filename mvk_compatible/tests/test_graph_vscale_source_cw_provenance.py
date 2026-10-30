"""Stage111W: tested static IDR word must not become runtime CW certification."""
import pytest
from mvk_compatible.core.spectrum_graph_default_vscale_idr_candidate import (
    SOURCE_STATIC_X87_CW, spectrum_graph_default_vscale,
)


def test_verified_on_disk_1332_is_pc64_nearest_but_not_live_delphi():
    assert SOURCE_STATIC_X87_CW == 0x1332
    assert (SOURCE_STATIC_X87_CW & 0x0300) == 0x0300
    assert (SOURCE_STATIC_X87_CW & 0x0C00) == 0
    assert (SOURCE_STATIC_X87_CW & 0x003F) == 0x32
    report = spectrum_graph_default_vscale(1., 1)
    assert report['original_idr_static_initial_cw_verified']
    assert report['original_idr_static_initial_x87_cw_hex'] == '0x1332'
    assert report['original_idr_static_initial_pc'] == '64_bit'
    assert report['original_idr_static_initial_rounding'] == 'nearest'
    assert report['original_process_cw_at_spectrum_verified'] is False
    assert report['original_delphi_graph_default_vscale_numeric_parity_verified'] is False


@pytest.mark.parametrize('f_range,mode,expected_scaled', [
    (10., 3, 1000.),(1., 3, 100.),(10., 2, 100.),
    (1., 1, 1.),(2., 1, 2.),(5., 1, 5.),
])
def test_original_pc64_x87_fyl2x_sensitive_boundaries_are_flagged(f_range,mode,expected_scaled):
    result=spectrum_graph_default_vscale(f_range,mode)
    assert result['mode_scaled_f_range_single']==expected_scaled
    assert result['original_x87_boundary_requires_runtime_reference']
    assert not result['original_process_cw_at_spectrum_verified']


def test_python_float64_log10_1000_is_not_equivalent_to_x87_ext():
    report=spectrum_graph_default_vscale(10.,3)
    # x87 FLDLG2/FYL2X under 0x1332 gave 2000 in synthetic native test;
    # Python math.log10 returned exactly 3 and selected 1000. Do not
    # silently substitute either as original Delphi golden output.
    assert report['candidate_graph_default_vscale_single']==1000.
    assert report['native_x87_extended_log10_integer_decade_risk']
    assert report['original_x87_boundary_requires_runtime_reference']
    assert not report['original_math_helpers_x87_rounding_verified']


def test_uncontroversial_non_boundary_inputs_remain_diagnostic():
    report=spectrum_graph_default_vscale(.31,2)
    assert report['candidate_graph_default_vscale_single']==pytest.approx(5.)
    assert report['original_x87_boundary_requires_runtime_reference'] is False
    assert report['original_delphi_graph_default_vscale_numeric_parity_verified'] is False
