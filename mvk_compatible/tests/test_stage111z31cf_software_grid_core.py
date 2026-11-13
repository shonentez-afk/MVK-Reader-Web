"""Source Draw original TCo2Draw blending on the two ordinary graphs."""
from hashlib import sha256
import numpy as np
import pytest

from ..core.original_live_software_grid import (
    source_live_software_grid_bitmap, MAX_SOURCE_SOFTWARE_PIXELS,
)
from ..core.original_live_grid_cursor import source_live_grid_frame
from ..core.tco2draw_raster_candidate import (
    source_grid_segments,source_raster_rgba,
)
from ..core.tco2draw_grid_source import GRID_LINE_RGB, BACKGROUND_RGB


@pytest.mark.parametrize("view_x,view_y,w,h",[
    ((0.,25600.),(-100.,0.),480,240),
    ((0.,20.),(-10.,10.),400,300),
    ((19.98,20.),(-.02,.02),380,260),
    ((-50.,50.),(0.,1.),200,250),
])
def test_actual_tco2draw_source_grid_order_and_copy(view_x,view_y,w,h):
    frame=source_live_grid_frame(view_x=view_x,view_y=view_y)
    grid=source_live_software_grid_bitmap(
        view_x=view_x,view_y=view_y,width=w,height=h)
    assert grid["source_actual_software_grid_raster_not_qt_pen"]
    assert grid["source_scanline_32bit_blending"]
    assert not grid["original_win32_pixel_parity_verified"]
    assert not grid["full_original_paintbox_bitmap_rendered"]
    assert not grid["qt_device_pixel_ratio_inflation_used"]
    assert grid["grid_x_count"]==len(frame["x_ticks"])
    assert grid["grid_y_count"]==len(frame["y_ticks"])
    image=grid["rgba"]
    assert image.shape==(h,w,4)
    assert image.dtype==np.uint8
    assert np.all(image[:,:,3]==255)
    segments=source_grid_segments(
        x_ticks=frame["x_ticks"],y_ticks=frame["y_ticks"],
        view_x=view_x,view_y=view_y,width=w,height=h)
    nx=len(frame["x_ticks"])
    expected=source_raster_rgba(width=w,height=h,
        segments=segments[nx:]+segments[:nx],
        ink=GRID_LINE_RGB,background=BACKGROUND_RGB)
    np.testing.assert_array_equal(image,expected)
    assert grid["rgba_sha256"]==sha256(image.tobytes()).hexdigest()
    # TCo2Draw blends fractional scanline coverage with the white
    # background. Even a correct source grid need not contain exact
    # RGB192 at these synthetic viewport sizes.
    assert np.any(np.all(
        (image[:,:,:3] >= GRID_LINE_RGB) &
        (image[:,:,:3] < BACKGROUND_RGB),axis=2))
    assert np.any(np.all(image[:,:,:3] == BACKGROUND_RGB,axis=2))


@pytest.mark.parametrize("w,h",[(0,400),(400,0),(False,10),
     (10001,50),(1000,3000),(-1,10)])
def test_bad_software_raster_fails_closed(w,h):
    with pytest.raises(ValueError):
        source_live_software_grid_bitmap(
            view_x=(0.,10.),view_y=(0.,1.),width=w,height=h)


def test_tco2draw_software_grid_has_no_data_or_fft_input():
    fields=set(source_live_software_grid_bitmap(
        view_x=(0.,20.),view_y=(-1.,1.),
        width=320,height=240))
    assert "samples" not in fields
    assert "amplitude" not in fields
    assert "fft" not in fields
    assert "bin" not in fields
