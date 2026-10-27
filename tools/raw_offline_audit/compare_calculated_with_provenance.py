"""Read-only Stage13 calculated-value comparison with strict provenance checks.

Input JSON lists of {device,adc,kind,band,unit,value,window_start_s,window_end_s}.
Times must be same timeline and correspond to a defined acquisition window.
No time bounds -> NOT_COMPARABLE, never fake exact agreement.
"""
import argparse
import json
from pathlib import Path

FIELDS=("device","adc","kind","band","unit")
def compare(a,b,tolerance_s=0.0):
    different=[k for k in FIELDS if a.get(k)!=b.get(k)]
    if different:
        return {"verdict":"NOT_COMPARABLE","reason":"different_"+",".join(different)}
    try:
        ta=(float(a["window_start_s"]),float(a["window_end_s"]))
        tb=(float(b["window_start_s"]),float(b["window_end_s"]))
    except (KeyError,TypeError,ValueError):
        return {"verdict":"NOT_COMPARABLE","reason":"missing_valid_window_bounds"}
    if ta[1]<=ta[0] or tb[1]<=tb[0]:
        return {"verdict":"NOT_COMPARABLE","reason":"invalid_window_bounds"}
    if max(abs(ta[0]-tb[0]),abs(ta[1]-tb[1]))>tolerance_s:
        return {"verdict":"NOT_COMPARABLE","reason":"windows_not_aligned"}
    try:
        import math
        va,vb=float(a["value"]),float(b["value"])
        if not math.isfinite(va) or not math.isfinite(vb):
            raise ValueError()
    except (KeyError,TypeError,ValueError):
        return {"verdict":"NOT_COMPARABLE","reason":"invalid_values"}
    return {"verdict":"COMPARED","absolute_error":abs(va-vb),
            "relative_error":abs(va-vb)/abs(vb) if vb!=0 else None,
            "instrument":va,"reference":vb,
            "note":"comparison only, no automatic PASS without approved tolerance"}
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("instrument_json");ap.add_argument("reference_json")
    ap.add_argument("--max-time-error-s",type=float,default=0)
    q=ap.parse_args()
    if q.max_time_error_s<0:ap.error("negative time error")
    a=json.loads(Path(q.instrument_json).read_text(encoding="utf8"))
    b=json.loads(Path(q.reference_json).read_text(encoding="utf8"))
    print(json.dumps(compare(a,b,q.max_time_error_s),ensure_ascii=False,indent=2))
