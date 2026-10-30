"""Stage111S source integer table and menu provenance tests, no proprietary data."""
import pytest
from mvk_compatible.core.mvk_original_scale_tables_idr_candidate import (
    SOURCE,HORIZONTAL_HZ,DB_Y_RANGES,PHYSICAL_Y_DIVISORS,
    FFT_WINDOW_SAMPLES,PRIVATE_ORIGINAL_ADDRESSES,original_h_scale_options,
    original_v_scale_options,original_fft_size_options,
    validate_source_h_scale,validate_source_v_scale)


def test_exact_original_h_ten_source_values_and_tag_order():
    assert HORIZONTAL_HZ==(25600,12800,6400,3200,1600,800,400,200,100,50)
    menu=original_h_scale_options()
    assert len(menu)==10
    assert [x['hz'] for x in menu]==list(HORIZONTAL_HZ)
    assert [x['tag'] for x in menu]==list(range(10))
    assert all(x['source']==SOURCE and x['source_menu_value_verified'] for x in menu)
    assert all(not x['original_runtime_canvas_parity_verified'] for x in menu)
    for v in HORIZONTAL_HZ:
        assert validate_source_h_scale(v)==v


def test_original_integer_tables_map_to_same_source_memory_addresses():
    assert PRIVATE_ORIGINAL_ADDRESSES['horizontal']==0x008D3428
    assert PRIVATE_ORIGINAL_ADDRESSES['fft_sizes']==0x008D3450
    assert PRIVATE_ORIGINAL_ADDRESSES['vertical_physical']==0x008D3468
    assert PRIVATE_ORIGINAL_ADDRESSES['vertical_db']==0x008D3480
    assert (PRIVATE_ORIGINAL_ADDRESSES['fft_sizes']
            -PRIVATE_ORIGINAL_ADDRESSES['horizontal'])==10*4
    assert (PRIVATE_ORIGINAL_ADDRESSES['vertical_physical']
            -PRIVATE_ORIGINAL_ADDRESSES['fft_sizes'])==6*4
    assert (PRIVATE_ORIGINAL_ADDRESSES['vertical_db']
            -PRIVATE_ORIGINAL_ADDRESSES['vertical_physical'])==6*4


def test_original_db_and_physical_six_preset_values_are_different():
    assert DB_Y_RANGES==(150,100,75,50,25,10)
    assert PHYSICAL_Y_DIVISORS==(1,10,100,1000,10000,100000)
    db=original_v_scale_options(0)
    assert [x['db_range'] for x in db]==list(DB_Y_RANGES)
    assert all(x['physical_divisor'] is None for x in db)
    for mode in (1,2,3):
        phys=original_v_scale_options(mode)
        assert [x['physical_divisor'] for x in phys]==list(PHYSICAL_Y_DIVISORS)
        assert all(x['db_range'] is None for x in phys)
        assert not any(x['actual_channel_derived_units_verified'] for x in phys)
    assert validate_source_v_scale(0,0)['db_range']==150
    assert validate_source_v_scale(2,5)['physical_divisor']==100000


def test_original_fft_menu_six_values_not_our_1024_4096_research_modes():
    assert FFT_WINDOW_SAMPLES==(262144,131072,65536,32768,16384,8192)
    m=original_fft_size_options()
    assert len(m)==6
    assert [x['n_fft'] for x in m]==list(FFT_WINDOW_SAMPLES)
    assert all(x['source_menu_value_verified'] for x in m)
    assert not any(x['actual_archive_history_sufficient'] for x in m)
    assert 4096 not in FFT_WINDOW_SAMPLES and 1024 not in FFT_WINDOW_SAMPLES


@pytest.mark.parametrize('invalid',[0,True,None,6401,25601,1024,'6400',-1,3.2])
def test_h_source_preset_never_guessed(invalid):
    with pytest.raises(ValueError,match='verified Delphi'):
        validate_source_h_scale(invalid)


@pytest.mark.parametrize('mode,tag',[(True,1),(4,0),(-1,0),(0,True),
    (0,6),(0,-1),(2,6),(3,None),('0',0)])
def test_vertical_preset_mode_tag_fails_closed(mode,tag):
    with pytest.raises(ValueError):
        validate_source_v_scale(mode,tag)
