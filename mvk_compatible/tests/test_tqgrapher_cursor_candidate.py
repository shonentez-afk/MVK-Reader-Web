

def test_stage111n_legacy_pixel_selector_accepts_original_reversed_x_affine():
    import numpy as np
    from mvk_compatible.core.tqgrapher_cursor_candidate import CursorGeometry,pick_tqgrapher_cursor
    geom=CursorGeometry(10.,110.,-.4,40.,0.,1.,
                        itos_m=-2.5,itos_c=110.)
    a=np.arange(60,dtype='f4')
    found=pick_tqgrapher_cursor(a,50.,geom,precise=True)
    assert found['selected_bin']==24
    assert found['pixel_bin_last']<found['pixel_bin_first']
    assert found['snapped_pixel_original_int_candidate']==50
    assert not found['precise_max_search_used']
