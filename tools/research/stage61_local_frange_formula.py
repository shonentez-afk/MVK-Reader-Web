#!/usr/bin/env python3
"""Static scientific check of archive scaling formula; not a live device test."""
from math import isfinite

def fallback_gain(adc_calibration,sensor_sensitivity):
    if not isfinite(adc_calibration) or not isfinite(sensor_sensitivity): raise ValueError("nonfinite")
    if sensor_sensitivity<=0: raise ValueError("invalid sensor sensitivity")
    return adc_calibration/sensor_sensitivity

if __name__=="__main__":
    value=fallback_gain(5.2191,0.010194)
    assert abs(value-511.97763390229545)<0.001
    print("PASS example fallback",value)
