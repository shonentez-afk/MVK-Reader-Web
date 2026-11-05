"""Stage111Z31K independent x87 source Hann full-table replay regression.

The SHA256 below was independently generated with source-derived
x87 long-double FCoS/FSQRT and the original mathematical 2*pi 80-bit
constant, see tools/research/hann_x87_reference_stage111z31k.c.

Four private original Win32 debugger samples were previously checked.
The other 262140 entries are compared with the INDEPENDENT x87 source
model here, not directly with an in-process original table capture.
"""
import hashlib
import numpy as np
import pytest

from mvk_compatible.core.fft_idr_candidate import idr_hann_rms

X87_HANN_SOURCE_CANDIDATE_SHA256=(
    "df10f6ab747656aefaeb17dee2764dd552e80cb738a5390108b8943615398069"
)
ORIGINAL_OPERATOR_MEASURED_SINGLE_BITS={
    1:0x2F80EF9C,
    5:0x31C97664,
    262139:0x31C97664,
    262143:0x2F80EF9C,
}


def test_complete_hann_table_is_bitwise_equal_to_independent_x87_replay():
    w=idr_hann_rms(262144)
    assert w.shape==(262144,)
    assert w.dtype==np.dtype("<f4")
    assert np.isfinite(w).all()
    assert hashlib.sha256(w.astype("<f4").tobytes()).hexdigest()==(
        X87_HANN_SOURCE_CANDIDATE_SHA256)
    for index,original_word in ORIGINAL_OPERATOR_MEASURED_SINGLE_BITS.items():
        assert int(w.view("<u4")[index])==original_word
    assert w[0]==np.float32(0.0)
    assert w[131072]==np.float32(2/np.sqrt(1.5))


@pytest.mark.parametrize("n",[1024,2048,4096,8192,65536,262144])
def test_hann_smaller_fft_sizes_use_exact_source_stride(n):
    full=idr_hann_rms(262144)
    actual=idr_hann_rms(n)
    step=262144//n
    np.testing.assert_array_equal(
        actual.view("<u4"),full[::step].view("<u4"))
    assert len(actual)==n


def test_cached_hann_table_not_poisoned_by_modifying_caller_copy():
    original=idr_hann_rms(1024)
    mutable=idr_hann_rms(1024)
    mutable[0]=np.float32(1234.)
    np.testing.assert_array_equal(
        idr_hann_rms(1024).view("<u4"),original.view("<u4"))
