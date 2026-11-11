"""Stage111Z31AY: genuine RGB bitwise XOR, same source bitmap, synthetic."""
import numpy as np
import pytest

from mvk_compatible.core.tqgrapher_canvas_idr_candidate import (
    source_canvas_geometry,
)
from mvk_compatible.core.tqgrapher_bitmap_xor_cursor import (
    source_bitmap_xor_cursor,
    source_bitmap_xor_contract,
)


def _fixture():
    canvas = source_canvas_geometry(
        pixel_width=180, pixel_height=130, margin=10,
        zero_text_width=9, six_decimals_text_width=64,
        zero_text_height=15,
        scr_left=0., scr_width=256., scr_bottom=-150., scr_height=150.,
        series_x_start=0., series_x_scale=0.25)
    image = np.full((130, 180, 4), 255, dtype=np.uint8)
    return image, canvas


def test_original_move_to_line_to_end_exclusion_and_crossing_double_xor():
    base, canvas = _fixture()
    source_bits = base.copy()
    left, right, top, bottom = (
        canvas[k] for k in
        ('pixel_left', 'pixel_right', 'pixel_top', 'pixel_bottom'))
    x, y = left + 19, top + 8
    out = source_bitmap_xor_cursor(
        base, canvas=canvas, cursor_pixel=(x, y))
    # White XOR clGreen(0,128,0) => (255,127,255).
    assert out[top, x, :3].tolist() == [255, 127, 255]
    assert out[y, left, :3].tolist() == [255, 127, 255]
    # Source actually draws BOTH lines, not a painter union. Crossing
    # receives XOR twice, so the underlying colour is unchanged.
    assert out[y, x, :3].tolist() == [255, 255, 255]
    # Win32 GDI LineTo endpoint is exclusive in original.
    assert out[bottom, x, :3].tolist() == [255, 255, 255]
    assert out[y, right, :3].tolist() == [255, 255, 255]
    assert np.all(out[:, :, 3] == 255)
    np.testing.assert_array_equal(base, source_bits)
    c = source_bitmap_xor_contract()
    assert c['source_horizontal_line_end_exclusive'] == 'PixelRight'
    assert not c['original_tcanvas_device_pixel_parity_verified']


def test_black_series_xors_into_green_but_baseline_is_unchanged():
    base, canvas = _fixture()
    x = canvas['pixel_left'] + 20
    y = canvas['pixel_top'] + 20
    base[y - 1, x, :3] = 0
    before = base.copy()
    frame = source_bitmap_xor_cursor(
        base, canvas=canvas, cursor_pixel=(x, y))
    assert frame[y - 1, x, :3].tolist() == [0, 128, 0]
    np.testing.assert_array_equal(base, before)


def test_no_ghost_cursor_on_reposition_zoom_or_clear():
    base, canvas = _fixture()
    x, y = canvas['pixel_left'] + 7, canvas['pixel_top'] + 12
    one = source_bitmap_xor_cursor(
        base, canvas=canvas, cursor_pixel=(x, y))
    two = source_bitmap_xor_cursor(
        base, canvas=canvas, cursor_pixel=(x + 8, y))
    again = source_bitmap_xor_cursor(
        base, canvas=canvas, cursor_pixel=(x, y))
    np.testing.assert_array_equal(one, again)
    # The FIRST cursor never pollutes the second frame.
    assert two[y + 1, x, :3].tolist() == base[y + 1, x, :3].tolist()
    restored = source_bitmap_xor_cursor(base, canvas=canvas)
    np.testing.assert_array_equal(restored, base)
    assert not np.shares_memory(restored, base)


@pytest.mark.parametrize('invalid', [
    (lambda a, c: (a[:, :, :3], c)),
    (lambda a, c: (a.astype(np.float32), c)),
    (lambda a, c: (np.zeros_like(a), c)),
    (lambda a, c: (a, {**c, 'source': 'not_original'})),
    (lambda a, c: (a, {**c, 'canvas_width': 181})),
    (lambda a, c: (a, {**c, 'pixel_right': True})),
])
def test_source_bitmap_rejects_untrusted_or_nonopaque_frame(invalid):
    base, canvas = _fixture()
    bad_base, bad_canvas = invalid(base, canvas)
    with pytest.raises(ValueError):
        source_bitmap_xor_cursor(bad_base, canvas=bad_canvas)


@pytest.mark.parametrize('bad_position', [
    (0, 0), (1.5, 20), (True, 40), (40, None),
    [40, 40], (2, 2, 2),
])
def test_source_cursor_rejects_invalid_point(bad_position):
    base, canvas = _fixture()
    with pytest.raises(ValueError):
        source_bitmap_xor_cursor(
            base, canvas=canvas, cursor_pixel=bad_position)
