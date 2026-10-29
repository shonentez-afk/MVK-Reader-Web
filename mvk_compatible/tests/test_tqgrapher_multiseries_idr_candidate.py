

def test_stage111n_reversed_x_preserves_original_pixel_plus_one_order():
    from mvk_compatible.core.tqgrapher_canvas_idr_candidate import source_canvas_geometry
    c=source_canvas_geometry(
        pixel_width=300,pixel_height=200,margin=10,zero_text_width=8,
        six_decimals_text_width=20,zero_text_height=12,
        x_name_present=True,y_name_present=True,
        scr_left=50.,scr_width=-40.,scr_bottom=0.,scr_height=10.,
        series_x_start=0.,series_x_scale=1.)
    a=np.arange(60,dtype='f4')
    pixel=100
    result=original_multiseries_cursor(a,pixel=pixel,canvas=c,
                                      precise=True,averaging=1)
    assert result['first_pixel_bin']>result['last_pixel_bin']
    assert result['selected_primary_bin']==result['first_pixel_bin']
    assert result['snapped_vertical_pixel']>=c['pixel_left']
    assert result['snapped_vertical_pixel']<=c['pixel_right']
    assert result['series_results'][0]['raw_at_peak']==float(
        a[result['selected_primary_bin']])
    assert not result['original_delphi_cursor_parity_verified']


def test_stage111n_reversed_x_carries_one_vertical_and_two_raw_y_lines():
    from mvk_compatible.core.tqgrapher_canvas_idr_candidate import source_canvas_geometry
    from mvk_compatible.core.tqgrapher_crosshair_idr_candidate import original_cursor_crosshair
    c=source_canvas_geometry(
        pixel_width=300,pixel_height=200,margin=10,zero_text_width=8,
        six_decimals_text_width=20,zero_text_height=12,
        x_name_present=True,y_name_present=True,
        scr_left=50.,scr_width=-40.,scr_bottom=0.,scr_height=10.,
        series_x_start=0.,series_x_scale=1.)
    a=np.arange(60,dtype='f4')
    b=-a
    sel=original_multiseries_cursor(a,pixel=100,canvas=c,series1=b,
                                   averaging=1)
    cross=original_cursor_crosshair(sel,c)
    assert cross['drawn'] and len(cross['horizontal_lines'])==2
    assert len(cross['horizontal_pixels'])==2
    assert cross['vertical_line']['start_xy'][0]==sel['snapped_vertical_pixel']
    assert cross['horizontal_lines'][0]['label_display_y']!=(
        cross['horizontal_lines'][1]['label_display_y'])
