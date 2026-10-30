"""Stage111T source vertical popup, first-class FFT history fail-closed tests."""
import pytest
from mvk_compatible.core.mvk_spectrum_menu_runtime_idr_candidate import (
    SOURCE,DB_FULL,PHYSICAL_FULL,RESEARCH_FFT_SIZES,source_default_vertical_tag,
    source_vertical_page,source_vertical_selection,fft_source_archive_gate)
from mvk_compatible.core.mvk_original_scale_tables_idr_candidate import (
    FFT_WINDOW_SAMPLES,DB_Y_RANGES,PHYSICAL_Y_DIVISORS)


def test_original_mode_change_selects_right_source_vertical_tag():
    assert source_default_vertical_tag(0)==0
    for mode in (1,2,3):
        assert source_default_vertical_tag(mode)==3
    for invalid in (-1,4,True,'1'):
        with pytest.raises(ValueError):
            source_default_vertical_tag(invalid)


def test_original_db_vertical_six_pages_and_full_range():
    assert DB_FULL==150
    for tag,page in enumerate(DB_Y_RANGES):
        s=source_vertical_selection(0,tag)
        assert s['source_runtime']==SOURCE
        assert s['full']==150 and s['page']==page
        assert s['delphi_max']==149
        assert s['delphi_page_size']==page
        assert s['qt_maximum']==150-page
        assert s['source_menu_tag']==tag
        assert s['db_range']==page
        assert s['physical_divisor'] is None
        assert not s['original_canvas_runtime_parity_verified']
        assert not s['source_original_graph_default_vscale_verified']


def test_original_physical_six_divisors_produce_integer_page():
    assert PHYSICAL_FULL==100000
    for tag,divisor in enumerate(PHYSICAL_Y_DIVISORS):
        for mode in (1,2,3):
            s=source_vertical_selection(mode,tag)
            assert s['full']==100000
            assert s['page']==100000//divisor
            assert s['physical_divisor']==divisor
            assert s['qt_maximum']==100000-s['page']
            assert s['delphi_max']==99999
            assert s['original_qt_y_registration_verified'] is False


def test_source_vertical_bottom_anchoring_and_mode_reset():
    start=source_vertical_selection(0,0)
    assert start['delphi_position']==0 and not start['delphi_visible']
    zoom=source_vertical_selection(0,2,old_tag=0,old_position=0)
    assert zoom['page']==75
    assert zoom['delphi_position']==75
    next_level=source_vertical_selection(0,3,old_tag=2,old_position=75)
    assert next_level['page']==50
    assert next_level['delphi_position']==100
    full=source_vertical_selection(0,0,old_tag=3,old_position=100)
    assert full['delphi_position']==0
    physical=source_vertical_selection(1,3)
    assert physical['page']==100 and physical['delphi_position']==0
    assert physical['delphi_visible']


def test_fourier_original_six_sizes_and_short_archive_never_padded():
    assert len(FFT_WINDOW_SAMPLES)==6
    assert RESEARCH_FFT_SIZES==(1024,4096)
    for n in FFT_WINDOW_SAMPLES:
        invalid=fft_source_archive_gate(n,4096)
        assert not invalid['can_compute_without_padding']
        assert invalid['reason']=='INSUFFICIENT_REAL_BIN_HISTORY'
        assert invalid['original_fft_menu_preset'] and not invalid['research_fft_preset']
        ok=fft_source_archive_gate(n,n)
        assert ok['can_compute_without_padding']
        assert ok['original_fft_menu_preset']
        assert not ok['original_fft_numeric_parity_verified']
    research=fft_source_archive_gate(4096,4096)
    assert research['research_fft_preset'] and not research['original_fft_menu_preset']


def test_explicit_source_endpoint_and_full_fir_history_enforced():
    assert fft_source_archive_gate(8192,20000,end_sample=8100)['reason']=='INSUFFICIENT_REAL_BIN_HISTORY'
    assert fft_source_archive_gate(8192,20000,end_sample=8200)['can_compute_without_padding']
    assert not fft_source_archive_gate(8192,20000,required_input_samples=25000)['can_compute_without_padding']
    assert fft_source_archive_gate(8192,30000,end_sample=20000,required_input_samples=20000)['can_compute_without_padding']


@pytest.mark.parametrize('n,total,end,required',[
    (7000,10000,None,None),(True,10000,None,None),
    (4096,-1,None,None),(8192,False,None,None),
    (8192,10000,12000,None),(8192,10000,True,None),
    (8192,10000,None,4095),(8192,10000,None,True),
    (8192,10000,None,100_000_001),
])
def test_fft_invalid_requests_fail_closed(n,total,end,required):
    with pytest.raises(ValueError):
        fft_source_archive_gate(n,total,end_sample=end,required_input_samples=required)


def test_wrong_vertical_tags_and_overflow_rejected():
    for mode,tag in ((0,6),(1,-1),(True,0),(4,2),(0,'2')):
        with pytest.raises(ValueError):
            source_vertical_page(mode,tag)
    with pytest.raises(ValueError):
        source_vertical_selection(0,2,old_tag=3,old_position=149)
