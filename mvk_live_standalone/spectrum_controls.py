"""Simple vibration spectrum controls for original-MVKView style operation.

One operator selection for four physical view modes, a separate filter,
X range 50..25600 Hz and Y width labelled in the correct physical unit.
All options are display or local-signal-processing only: no MVK01 commands.
"""
from __future__ import annotations
import math
from .octave_filters import FAMILIES, FAMILY_LABELS, nominal_centres, preset_band, preset_description

# Four quick views refer to physical quantities/units, not the frequency axis.
VIEW_MODES = (
    ("ВУ · уровень в дБ", "log_vu", "acceleration", "db"),
    ("ВУ · м/с²", "linear_vu", "acceleration", "linear"),
    ("ВС · мм/с", "linear_vs", "velocity", "linear"),
    ("ВП · мкм", "linear_vp", "displacement", "linear"),
)
X_LIMITS_HZ=(50,100,200,500,1000,2000,4000,8000,10000,12800,16000,25600)
# Amplitude span for each of the four operator modes. These are real
# physical plotting units, NOT interchangeable dimensionless Y limits.
Y_WIDTH_CHOICES={
    "log_vu":(20,40,60,80,100,120,160),       # dB span, top tracks peak
    "linear_vu":(.01,.05,.1,.5,1,2,5,10,20,50,100,500,1000),  # m/s²
    "linear_vs":(.1,.2,.5,1,2,5,10,20,50,100,200,500),       # mm/s
    "linear_vp":(.5,1,2,5,10,20,50,100,200,500,1000,5000,10000), # µm
}
FILTER_CHOICES=(
    ("Без фильтра","none"),
    ("Как в MVKView · оригинальное меню 32 полос","original_preset"),
    ("ФВЧ — высоких частот","highpass"),
    ("ФНЧ — низких частот","lowpass"),
    ("Полосовой","bandpass"),
    ("Режектор 50 Гц","notch50"),
    ("Режектор 60 Гц","notch60"),
    ("1/1 октавы · выбрать полосу","octave"),
    ("1/3 октавы · выбрать полосу","third_octave"),
    ("2 октавы · выбрать полосу","double_octave"),
)

def view_settings(view: str) -> tuple[str,str]:
    for _,key,kind,scale in VIEW_MODES:
        if key==view:
            return kind,scale
    raise ValueError("Неизвестный вид спектра вибрации")

def x_limit_hz(selected: int, rate_hz: int|None) -> tuple[float,bool]:
    """Never display an unmeasured range above the selected ADC's Nyquist."""
    if type(selected) is not int or selected not in X_LIMITS_HZ:
        raise ValueError("X must be one of 50..25600 Hz operator limits")
    if rate_hz is None:
        return float(selected),False
    if type(rate_hz) is not int or rate_hz<=0:
        raise ValueError("Unknown real ADC sampling frequency")
    actual=min(float(selected),rate_hz/2)
    return actual,actual<float(selected)

def y_height_options(view: str) -> list[tuple[str,float|None]]:
    if view not in Y_WIDTH_CHOICES:
        raise ValueError("Unknown physical Y view")
    suffix={"log_vu":"дБ","linear_vu":"м/с²","linear_vs":"мм/с",
            "linear_vp":"мкм"}[view]
    return [("Авто",None)]+[(f"{v:g} {suffix}",float(v))
                           for v in Y_WIDTH_CHOICES[view]]

def visible_y_range(values,scale: str, chosen_height: float|None) -> tuple[float,float]:
    """Linear Y: [0, physical amplitude]; dB: width below real peak."""
    if scale not in ("linear","db"):
        raise ValueError("Unknown vibration Y scale")
    if chosen_height is not None and (
            type(chosen_height) not in (int,float) or
            not math.isfinite(chosen_height) or chosen_height<=0):
        raise ValueError("Invalid positive Y width")
    finite=[float(v) for v in values if math.isfinite(float(v))]
    if scale=="db":
        top=max(finite,default=0.0)
        upper=math.ceil(top/10.0)*10.0+10.0
        return upper-float(chosen_height if chosen_height is not None else 80.0),upper
    positive=max((v for v in finite if v>0),default=0.0)
    top=float(chosen_height) if chosen_height is not None else (
        positive*1.15 if positive>0 else 1.0)
    return 0.0,top
