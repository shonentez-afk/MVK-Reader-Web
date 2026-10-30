"""Stage111R: EXPLICIT research bridge between Qt scene and Delphi PaintBox.

SceneBoundingRect, Qt logical/device pixels and original TPaintBox coordinates
are distinct coordinate systems. This mapping is a *hypothesis* anchored by
source-derived PixelRect; without matching original runtime Canvas/Font/DPI
and independent measured landmarks it MUST NOT drive an accepted native cursor.
No real instrument data, protected source or implicit DPI multiplication.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numbers

from .tqgrapher_paintbox_registration_idr_candidate import SOURCE as PAINTBOX_SOURCE

SOURCE='APP_DERIVED_QT_TO_TPAINTBOX_SCENE_AFFINE_CANDIDATE'


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(float(value)):
        raise ValueError(name + ' must be a finite numeric coordinate')
    return float(value)


@dataclass(frozen=True)
class QtPaintBoxBridge:
    source_canvas: dict
    qt_scene_left: float
    qt_scene_right: float
    qt_scene_top: float
    qt_scene_bottom: float
    qt_device_pixel_ratio: float

    def __post_init__(self):
        c=self.source_canvas
        if not isinstance(c,dict) or c.get('paintbox_registration_source')!=PAINTBOX_SOURCE:
            raise ValueError('Source-derived original TPaintBox registration is required')
        for key in ('qt_scene_left','qt_scene_right','qt_scene_top','qt_scene_bottom',
                    'qt_device_pixel_ratio'):
            _finite(getattr(self,key),key)
        if (self.qt_scene_right<=self.qt_scene_left or self.qt_scene_bottom<=self.qt_scene_top
                or not 0.25<=self.qt_device_pixel_ratio<=8.):
            raise ValueError('Qt scene rectangle or DPR is invalid')
        for axis in ('pixel_left','pixel_right','pixel_top','pixel_bottom'):
            if type(c.get(axis)) is not int:
                raise ValueError('Native Canvas pixel rectangles must be Integer')
        if c['pixel_left']>=c['pixel_right'] or c['pixel_top']>=c['pixel_bottom']:
            raise ValueError('Native source PixelRect must be positive')
        if (c.get('original_canvas_font_metrics_verified') or
            c.get('original_pixel_rectangle_verified')):
            raise ValueError('Do not supply a fabricated verified original Canvas')

    @property
    def x_scale(self)->float:
        c=self.source_canvas
        return (c['pixel_right']-c['pixel_left'])/(self.qt_scene_right-self.qt_scene_left)

    @property
    def y_scale(self)->float:
        c=self.source_canvas
        return (c['pixel_bottom']-c['pixel_top'])/(self.qt_scene_bottom-self.qt_scene_top)

    def scene_to_paintbox(self, x:float,y:float)->tuple[float,float]:
        x=_finite(x,'Qt scene X');y=_finite(y,'Qt scene Y')
        c=self.source_canvas
        return (c['pixel_left']+(x-self.qt_scene_left)*self.x_scale,
                c['pixel_top']+(y-self.qt_scene_top)*self.y_scale)

    def paintbox_to_scene(self,x:float,y:float)->tuple[float,float]:
        x=_finite(x,'PaintBox X');y=_finite(y,'PaintBox Y')
        c=self.source_canvas
        return (self.qt_scene_left+(x-c['pixel_left'])/self.x_scale,
                self.qt_scene_top+(y-c['pixel_top'])/self.y_scale)

    def native_mouse_integer_candidate(self,qt_scene_x:float)->int:
        """Truncation hypothesis for event integer X, NOT original raster proof."""
        native_x,_=self.scene_to_paintbox(qt_scene_x,self.qt_scene_top)
        return math.trunc(native_x)

    def describe(self)->dict:
        return {
            'source':SOURCE,
            'qt_scene_x_to_native_x_scale':self.x_scale,
            'qt_scene_y_to_native_y_scale':self.y_scale,
            'qt_device_pixel_ratio_observed':self.qt_device_pixel_ratio,
            'native_scene_mapping_uses_qt_logical_coordinates':True,
            'device_pixel_ratio_not_applied_to_native_transform':True,
            'original_paintbox_runtime_landmarks_verified':False,
            'original_delphi_pixel_parity_verified':False,
            'native_mouse_integer_rounding_parity_verified':False,
            'warning':('Only a candidate mapping between Qt ViewBox and original PixelRect; '
                       'obtain independent original TPaintBox/Font/DPI landmarks'),
        }


def compare_measured_landmarks(bridge:QtPaintBoxBridge,landmarks:list[dict],*,
                               tolerance_native_px:float=0.5)->dict:
    """Compare independently measured matching points, return errors only.

    Input remains PRIVATE. A successful synthetic match never authenticates
    original Windows GDI/Delphi or exact cursor semantics.
    """
    tol=_finite(tolerance_native_px,'landmark tolerance')
    if tol<0 or tol>20:
        raise ValueError('Invalid native landmark pixel tolerance')
    if not isinstance(bridge,QtPaintBoxBridge) or not isinstance(landmarks,list) or not 1<=len(landmarks)<=32:
        raise ValueError('Expected bridge and 1..32 independently measured landmark pairs')
    errors=[]
    for point in landmarks:
        if not isinstance(point,dict) or set(point)!={'qt_scene_x','qt_scene_y','native_x','native_y'}:
            raise ValueError('Expected exactly Qt and native x/y landmark coordinates')
        pred=bridge.scene_to_paintbox(point['qt_scene_x'],point['qt_scene_y'])
        err_x=abs(pred[0]-_finite(point['native_x'],'native_x'))
        err_y=abs(pred[1]-_finite(point['native_y'],'native_y'))
        errors.append({'error_x_native_px':err_x,'error_y_native_px':err_y,
                       'within_tolerance':max(err_x,err_y)<=tol})
    return {'source':'LOCAL_QT_ORIGINAL_PAINTBOX_LANDMARK_DIAGNOSTIC',
            'landmark_count':len(errors),'absolute_errors':errors,
            'all_landmarks_within_tolerance':all(x['within_tolerance'] for x in errors),
            'original_runtime_canvas_parity_verified':False,
            'delphi_x87_numeric_parity_verified':False}
