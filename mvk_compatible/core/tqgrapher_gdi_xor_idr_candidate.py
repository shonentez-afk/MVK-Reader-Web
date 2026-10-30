"""Stage111P: source-derived GDI XOR raster, independent of the native Qt plot.

PRIVATE _Unit115:007CA793..007CAB03 sets VCL clGreen (0x00008000),
TPen pmXor (ordinal 14), erases prior X and up to two Y lines, draws
new lines and restores pmCopy (ordinal 4). UpdateCursor:007CA75C
returns without work when native integer mouse X does not change.

Windows GDI LineTo excludes its endpoint; R2_XORPEN (GDI code 7)
XORs RGB destination with the pen color. This models only 1-pixel-wide,
axis-aligned *synthetic RGB* rendering; Qt/GDI/Delphi pixel parity is NOT
claimed. No original PAS/DFM/IDP, instrument, HTTP or network access.
"""
from __future__ import annotations

from dataclasses import dataclass
import numbers
import numpy as np

SOURCE = 'APP_DERIVED_TQGRAPHER_GDI_XOR_RASTER_IDR_CANDIDATE'
CROSSHAIR_SOURCE = 'APP_DERIVED_TQGRAPHER_CROSSHAIR_IDR_CANDIDATE'
CANVAS_SOURCE = 'APP_DERIVED_TQGRAPHER_CANVAS_GEOMETRY_IDR_CANDIDATE'
VCL_PEN_PM_XOR = 14
VCL_PEN_PM_COPY = 4
GDI_R2_XORPEN = 7
# VCL TColor stores 0x00BBGGRR, hence clGreen -> RGB(0,128,0).
CL_GREEN_RGB = (0, 128, 0)
MAX_RASTER_PIXELS = 4_000_000


def _int(v: object, field: str) -> int:
    if not isinstance(v, numbers.Integral) or isinstance(v, bool):
        raise ValueError(field + ' must be a native integer')
    return int(v)


@dataclass(frozen=True)
class GdiLineTo:
    """MoveTo/LineTo segment; terminating pixel is excluded."""
    role: str
    series: int | None
    start_xy: tuple[int, int]
    stop_xy_exclusive: tuple[int, int]

    def __post_init__(self):
        if self.role not in ('vertical', 'horizontal'):
            raise ValueError('Unknown original cursor line role')
        if self.role == 'vertical' and self.series is not None:
            raise ValueError('Vertical line cannot have a series index')
        if self.role == 'horizontal' and self.series not in (0, 1):
            raise ValueError('Horizontal series index must be 0 or 1')
        for name, pair in (('start_xy', self.start_xy),
                           ('stop_xy_exclusive', self.stop_xy_exclusive)):
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise ValueError('Invalid native ' + name)
            for v in pair:
                _int(v, name)
        x0, y0 = self.start_xy
        x1, y1 = self.stop_xy_exclusive
        if self.role == 'vertical' and (x0 != x1 or y0 == y1):
            raise ValueError('Invalid native vertical MoveTo/LineTo')
        if self.role == 'horizontal' and (y0 != y1 or x0 == x1):
            raise ValueError('Invalid native horizontal MoveTo/LineTo')


def _validated_bitmap(image: np.ndarray) -> np.ndarray:
    if (not isinstance(image, np.ndarray) or image.ndim != 3
            or image.shape[2] != 3 or image.dtype != np.uint8
            or image.shape[0] < 1 or image.shape[1] < 1
            or image.shape[0] * image.shape[1] > MAX_RASTER_PIXELS):
        raise ValueError('Expected bounded RGB uint8 [H,W,3] raster')
    return image


def xor_gdi_line(image: np.ndarray, line: GdiLineTo) -> np.ndarray:
    """Apply one native axis-aligned R2_XORPEN stroke in-place.

    These coordinates are Win32 logical pixels, NOT Qt device pixels.
    Clipping/diagonal/antialiasing is refused rather than approximated.
    """
    _validated_bitmap(image)
    if not isinstance(line, GdiLineTo):
        raise ValueError('A native GDI cursor segment is required')
    height, width = image.shape[:2]
    x0, y0 = line.start_xy
    x1, y1 = line.stop_xy_exclusive
    if line.role == 'vertical':
        if not 0 <= x0 < width or not 0 <= y0 < height or not 0 <= y1 <= height:
            raise ValueError('Vertical GDI line outside raster, clipping unverified')
        stop = np.arange(y0, y1, 1 if y1 > y0 else -1, dtype=np.intp)
        image[stop, x0, 1] ^= np.uint8(128)
    else:
        if not 0 <= y0 < height or not 0 <= x0 < width or not 0 <= x1 <= width:
            raise ValueError('Horizontal GDI line outside raster, clipping unverified')
        stop = np.arange(x0, x1, 1 if x1 > x0 else -1, dtype=np.intp)
        image[y0, stop, 1] ^= np.uint8(128)
    return image


def _strokes_from_crosshair(value: dict | None) -> tuple[GdiLineTo, ...]:
    if value is None:
        return ()
    if not isinstance(value, dict) or value.get('source') != CROSSHAIR_SOURCE:
        raise ValueError('Source-derived 1/2-series cursor crosshair is required')
    if not isinstance(value.get('drawn'), bool):
        raise ValueError('Invalid original crosshair drawn flag')
    if not value['drawn']:
        if value.get('vertical_line') is not None or value.get('horizontal_lines') != []:
            raise ValueError('Undrawn crosshair cannot retain cursor lines')
        return ()
    vertical = value.get('vertical_line')
    horizontal = value.get('horizontal_lines')
    if not isinstance(vertical, dict) or not isinstance(horizontal, list) or not 1 <= len(horizontal) <= 2:
        raise ValueError('Expected original vertical and 1/2 horizontal lines')

    def as_pair(line: dict, name: str) -> tuple[int, int]:
        p = line.get(name)
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError('Original GDI pixel segment is invalid')
        return _int(p[0], name), _int(p[1], name)

    v = GdiLineTo('vertical', None, as_pair(vertical, 'start_xy'),
                  as_pair(vertical, 'end_xy'))
    strokes = [v]
    used: set[int] = set()
    for item in horizontal:
        if not isinstance(item, dict):
            raise ValueError('Invalid original horizontal series')
        i = _int(item.get('series'), 'series')
        if i not in (0, 1) or i in used:
            raise ValueError('Duplicate or unknown original cursor series')
        used.add(i)
        strokes.append(GdiLineTo('horizontal', i, as_pair(item, 'start_xy'),
                                 as_pair(item, 'end_xy')))
    return tuple(strokes)


class OriginalGdiXorCursorModel:
    """Stateful erase-then-draw sequence on the CURRENT already-painted RGB.

    A background redraw or resize requires a fresh instance: XOR is not
    meaningful when old lines have disappeared from the input image.
    """
    def __init__(self, canvas: dict):
        if not isinstance(canvas, dict) or canvas.get('source') != CANVAS_SOURCE:
            raise ValueError('Original source-derived Canvas candidate required')
        self.rect = tuple(_int(canvas.get(k), k) for k in
                          ('pixel_left', 'pixel_right', 'pixel_top', 'pixel_bottom'))
        left, right, top, bottom = self.rect
        if left < 0 or top < 0 or right <= left or bottom <= top:
            raise ValueError('Invalid original pixel rectangle')
        self._mouse_x: int | None = None
        self._drawn: tuple[GdiLineTo, ...] = ()
        self._surface_size: tuple[int, int] | None = None

    @property
    def active_strokes(self) -> tuple[GdiLineTo, ...]:
        return self._drawn

    def update(self, mouse_x: int, current_rgb: np.ndarray,
               next_crosshair: dict | None) -> tuple[np.ndarray, dict]:
        _int(mouse_x, 'mouse_x')
        frame = _validated_bitmap(current_rgb)
        height, width = frame.shape[:2]
        left, right, top, bottom = self.rect
        if right >= width or bottom >= height:
            raise ValueError('Original Canvas rectangle exceeds raster')
        if self._surface_size is not None and self._surface_size != (height, width):
            raise ValueError('Background resized: create a fresh XOR cursor model')
        if self._mouse_x == mouse_x:
            return frame.copy(), self._report(mouse_x, (), (), True)

        next_strokes = _strokes_from_crosshair(next_crosshair)
        if (mouse_x <= left or mouse_x >= right) and next_strokes:
            raise ValueError('Original out-of-range X must not draw a cursor')
        if next_strokes:
            if not left <= next_strokes[0].start_xy[0] <= right:
                raise ValueError('Original snapped cursor outside source bounds')
            if (next_strokes[0].start_xy[1], next_strokes[0].stop_xy_exclusive[1]) != (top, bottom):
                raise ValueError('Wrong original vertical PixelTop/Bottom')
            for stroke in next_strokes[1:]:
                if (stroke.start_xy[0], stroke.stop_xy_exclusive[0]) != (left, right):
                    raise ValueError('Wrong original horizontal PixelLeft/Right')
                if not top <= stroke.start_xy[1] <= bottom:
                    raise ValueError('Original horizontal line outside PixelRect')
        # Validate both the old and new lines BEFORE mutating input/state.
        for stroke in (*self._drawn, *next_strokes):
            if stroke.role == 'vertical':
                x = stroke.start_xy[0]
                if not 0 <= x < width or not (0 <= stroke.start_xy[1] < height
                        and 0 <= stroke.stop_xy_exclusive[1] <= height):
                    raise ValueError('Original vertical line not in bitmap')
            else:
                y = stroke.start_xy[1]
                if not 0 <= y < height or not (0 <= stroke.start_xy[0] < width
                        and 0 <= stroke.stop_xy_exclusive[0] <= width):
                    raise ValueError('Original horizontal line not in bitmap')
        result = frame.copy()
        for stroke in self._drawn:
            xor_gdi_line(result, stroke)
        for stroke in next_strokes:
            xor_gdi_line(result, stroke)
        old = self._drawn
        self._drawn = next_strokes
        self._mouse_x = int(mouse_x)
        self._surface_size = (height, width)
        return result, self._report(mouse_x, old, next_strokes, False)

    @staticmethod
    def _report(mouse_x: int, erase: tuple[GdiLineTo, ...],
                draw: tuple[GdiLineTo, ...], no_op: bool) -> dict:
        return {
            'source': SOURCE,
            'mouse_x': int(mouse_x),
            'same_integer_x_noop': no_op,
            'erase_roles': [f'{s.role}{"" if s.series is None else s.series}' for s in erase],
            'draw_roles': [f'{s.role}{"" if s.series is None else s.series}' for s in draw],
            'vcl_pen_during_draw': VCL_PEN_PM_XOR if not no_op else None,
            'vcl_pen_after_draw': VCL_PEN_PM_COPY if not no_op else None,
            'win32_rop2_xorpen': GDI_R2_XORPEN if not no_op else None,
            'line_to_terminal_pixel_excluded': True,
            'delphi_original_pixel_parity_verified': False,
            'original_font_dpi_parity_verified': False,
        }
