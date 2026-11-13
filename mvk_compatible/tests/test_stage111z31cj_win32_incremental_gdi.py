"""Stage111Z31CJ native Win32 GDI fast per-glyph ROI parity.

The glyphs are reconstructed from DFM Tahoma -13, NOT from a captured
running original process. Check against the accepted own Win32 GDI
full-bitmap renderer, not an imaginary original-exe pixel oracle.
"""
import sys
import numpy as np
import pytest

pytestmark=pytest.mark.skipif(
    sys.platform!="win32",reason="Windows GDI native-only")


@pytest.mark.parametrize("event_order", [
    ("x_tick","y_tick","x_name","y_name"),
    ("y_tick","x_tick","y_name","x_name"),
])
def test_win32_cached_frame_single_event_matches_full_dib_textout(
        event_order):
    from ..desktop.win32_gdi_source_candidate import (
        Win32SourceTextCanvas)
    bg=np.full((88,196,4),255,dtype=np.uint8)
    bg[17,3:181,:3]=192
    bg[8:70,45,:3]=192
    bg[82,2:191,:3]=0
    events_by_kind={
        "x_tick":{"kind":"x_tick","text":"12,345","x":1,"y":12},
        "y_tick":{"kind":"y_tick","text":"-1,50","x":39,"y":4},
        "x_name":{"kind":"x_name","text":"Гц","x":89,"y":59},
        "y_name":{"kind":"y_name","text":"м/с²","x":155,"y":71},
    }
    events=tuple(events_by_kind[k] for k in event_order)
    with Win32SourceTextCanvas(
            font_face="Tahoma",font_height=-13) as dc:
        expected=dc.draw_text(bg,events)
        actual=np.array(bg,order="C",copy=True)
        for event in events:
            returned=dc.draw_incremental_text(actual,(event,))
            assert returned is actual
            assert dc._incremental_size==(196,88)
            assert dc._incremental_frame is not None
        np.testing.assert_array_equal(actual,expected)
        assert np.all(actual[:,:,3]==255)
        previous=dc._incremental_frame
        assert dc.draw_incremental_text(actual,()) is actual
        assert dc._incremental_frame==previous
    assert dc._incremental_frame is None
    assert dc._incremental_pixels is None
    with pytest.raises(RuntimeError):
        dc.draw_incremental_text(actual,events[:1])


def test_native_incremental_glyph_rejects_invalid_or_noncontiguous_inputs():
    from ..desktop.win32_gdi_source_candidate import Win32SourceTextCanvas
    rgba=np.full((64,96,4),255,dtype=np.uint8)
    event={"kind":"x_tick","text":"12","x":3,"y":8}
    with Win32SourceTextCanvas() as dc:
        with pytest.raises(ValueError):
            dc.draw_incremental_text(rgba[:,:,:3],(event,))
        with pytest.raises(ValueError):
            dc.draw_incremental_text(rgba[:,::-1],(event,))
        with pytest.raises(ValueError):
            dc.draw_incremental_text(rgba,(event,event))
        with pytest.raises(ValueError):
            dc.draw_incremental_text(rgba,({"kind":"x_tick","x":3},))
        bad=np.array(rgba,copy=True)
        bad[8,3,3]=0
        with pytest.raises(ValueError):
            dc.draw_incremental_text(bad,(event,))
