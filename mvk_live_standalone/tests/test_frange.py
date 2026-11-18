"""Calibration must be done exactly once by native Go, not by Qt FFT."""
from __future__ import annotations

import numpy as np
import pytest

from mvk_live_standalone.frange import original_applied_frange
from mvk_live_standalone.spectrum import calculate_spectrum


def status(gain: float=510.5650329589844) -> dict:
    return {
        "phase":"RECORDING",
        "full_register_snapshots":1,
        "adc_frange_from_config":[gain]+[float(i) for i in range(2,9)],
    }


def test_native_frange_is_known_by_channel_but_never_applied_again_in_fft():
    body=status()
    assert original_applied_frange(body,1)==pytest.approx(510.565033)
    assert original_applied_frange(body,8)==8
    fs=8192
    t=np.arange(8192)/fs
    raw=np.sqrt(2)*np.sin(2*np.pi*256*t).astype(np.float32)
    # The Go IPC already contains this once-scaled Float32.
    calibrated=(raw.astype(np.float64)*original_applied_frange(body,1)).astype("<f4")
    view=calculate_spectrum(calibrated,fs,kind="acceleration",
                            nfft=8192,band_hz=(0.,None))
    f,y=view.peak
    assert f==pytest.approx(256.,abs=.1)
    assert y==pytest.approx(510.565033,rel=.002)
    # An accidental second multiplication would produce ~260,676 m/s².
    assert y<1000.


@pytest.mark.parametrize("bad",[
    [1.,2.],                               # incomplete
    [1.]*9,                               # extra channels
    [0.]+[1.]*7,                          # zero factor
    [-2.]+[1.]*7,                         # negative factor
    [float("nan")]+[1.]*7,                 # nonfinite
    [float("inf")]+[1.]*7,
    [None]+[1.]*7,
    [True]+[1.]*7,                         # bool is NOT a real calibration
    ["510.5"]+[1.]*7,                      # UI text is NOT device evidence
])
def test_reject_malformed_frange_without_unity_fallback(bad):
    body=status()
    body["adc_frange_from_config"]=bad
    with pytest.raises(ValueError):
        original_applied_frange(body,1)


def test_frange_missing_until_initial_full_config_is_not_one():
    assert original_applied_frange(None,1) is None
    assert original_applied_frange({"phase":"CONNECTING"},1) is None
    s=status()
    del s["adc_frange_from_config"]
    assert original_applied_frange(s,1) is None
    s=status()
    s["full_register_snapshots"]=0
    with pytest.raises(ValueError,match="full instrument"):
        original_applied_frange(s,1)
    with pytest.raises(ValueError):
        original_applied_frange(status(),9)
