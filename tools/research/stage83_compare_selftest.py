#!/usr/bin/env python3
"""Synthetic-only regression test; no device, no industrial data."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location("m",Path(__file__).with_name("stage83_compare_spectra.py"))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
c=[(0.,0.),(1.,1.),(2.,4.),(3.,2.)]
r=list(c)
z=m.compare(c,r)
assert z["bins"]==4 and z["max_abs_error"]==0 and z["relative_error_bins"]==3
r=[(0.,0.),(1.,1.),(2.,3.),(3.,2.)]
z=m.compare(c,r)
assert z["max_abs_error"]==1 and z["max_abs_relative_error_percent"]>33
try: m.compare(c,r[1:])
except ValueError: pass
else: raise AssertionError("frequency grids must match")
print("PASS synthetic comparator: exact match, mismatched values, grid refusal")
