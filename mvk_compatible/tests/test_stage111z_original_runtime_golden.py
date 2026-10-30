"""Stage111Z regression on the four operator-reported original x32dbg observations.

Measurements are exact 32-bit hex words reported from the user's original Windows
process; they have not been independently re-captured. This test certifies only
the four observed samples, not Delphi x87 equivalence at discontinuities.
"""
from __future__ import annotations

import struct
import unittest

from mvk_compatible.core.spectrum_graph_default_vscale_idr_candidate import (
    MODE_MULTIPLIERS,
    spectrum_graph_default_vscale,
)


def _float32_from_hex(bits: str) -> float:
    return struct.unpack(">f", bytes.fromhex(bits))[0]


def _hex_from_float32(number: float) -> str:
    return struct.pack(">f", number).hex().upper()


class Stage111ZRuntimeGoldenRegression(unittest.TestCase):
    """Same source channel FRange; mode 0/1/2/3 original snapshots."""

    F_RANGE_HEX = "43FF4853"
    CASES = (
        # tag, pre-log10 stored Single bits, result stored Single bits
        (0, "43FF4853", "447A0000"),
        (1, "43FF4853", "447A0000"),
        (2, "459F8D34", "461C4000"),
        (3, "47477081", "47C35000"),
    )

    def test_original_input_and_result_exact_bits(self) -> None:
        original_f_range = _float32_from_hex(self.F_RANGE_HEX)
        self.assertEqual(MODE_MULTIPLIERS, (1, 1, 10, 100))
        for tag, expected_pre_hex, expected_post_hex in self.CASES:
            with self.subTest(tag=tag):
                data = spectrum_graph_default_vscale(original_f_range, tag)
                self.assertEqual(
                    _hex_from_float32(data["mode_scaled_f_range_single"]),
                    expected_pre_hex,
                )
                self.assertEqual(
                    _hex_from_float32(data["candidate_graph_default_vscale_single"]),
                    expected_post_hex,
                )
                self.assertFalse(data["original_delphi_graph_default_vscale_numeric_parity_verified"])

    def test_x87_boundary_not_implicitly_certified(self) -> None:
        for tag, _, _ in self.CASES:
            data = spectrum_graph_default_vscale(_float32_from_hex(self.F_RANGE_HEX), tag)
            self.assertFalse(data["original_math_helpers_x87_rounding_verified"])
            self.assertFalse(data["original_qt_y_canvas_parity_verified"])


if __name__ == "__main__":
    unittest.main()
