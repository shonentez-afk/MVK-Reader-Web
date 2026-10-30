"""Stage111Z.1: synthetic Float32 boundary characterization, NOT Delphi golden.

For each exact 2/5 power-of-ten boundary the Python float64 candidate
currently advances one rung past the exact ideal ceiling. These are recorded
known differences, NOT auto-corrected without original x87 observations.
"""
from __future__ import annotations
import struct
import unittest
from decimal import Decimal
from mvk_compatible.core.spectrum_graph_default_vscale_idr_candidate import spectrum_graph_default_vscale

def f32(x):
    return struct.unpack("<f",struct.pack("<f",float(x)))[0]

def bits(x):
    return struct.unpack("<I",struct.pack("<f",float(x)))[0]

def exact_125_ceiling(x):
    d=Decimal.from_float(x)
    p=Decimal(10)**d.adjusted()
    for n in (1,2,5,10):
        v=p*n
        if v >= d:
            return f32(float(v))
    raise AssertionError("Unreachable")

class Stage111ZBoundaryCharacterization(unittest.TestCase):
    def test_known_python_candidate_overshoots_exact_two_and_five(self):
        # Characterize known discrepancies; these are NOT expected Delphi results.
        for x, expected_candidate in ((2,5),(5,10),(2000,5000),(5000,10000)):
            with self.subTest(input=x):
                report=spectrum_graph_default_vscale(float(x),0)
                self.assertEqual(bits(report["candidate_graph_default_vscale_single"]),
                                 bits(f32(expected_candidate)))
                self.assertEqual(bits(exact_125_ceiling(f32(x))),bits(f32(x)))
                self.assertTrue(report["original_x87_boundary_requires_runtime_reference"])
                self.assertFalse(report["original_delphi_graph_default_vscale_numeric_parity_verified"])

    def test_float32_neighbors_keep_source_risk_metadata(self):
        # Purely synthetic tests: no assumption of Delphi equivalence.
        for x in (2.,5.,10.,1000.,2000.,5000.):
            b=bits(f32(x))
            for delta in (-1,0,1):
                with self.subTest(input=x,delta=delta):
                    neighbor=struct.unpack("<f",struct.pack("<I",b+delta))[0]
                    report=spectrum_graph_default_vscale(neighbor,0)
                    self.assertGreater(report["candidate_graph_default_vscale_single"],0)
                    self.assertFalse(report["original_delphi_graph_default_vscale_numeric_parity_verified"])

if __name__=="__main__":
    unittest.main()
