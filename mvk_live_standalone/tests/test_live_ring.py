"""CortexTrace-inspired display ring: real MVK counters, 8 independent ADCs."""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import numpy as np
import pytest

from mvk_live_standalone.live_ring import VerifiedLiveRing, DOMAIN


def preview(*, session="RUN-A", number=1, end=6, first=0, rate=8192,
            values=None, next_index=None):
    if values is None:
        values=np.arange(first,end,dtype="<f4")
    data=np.asarray(values,dtype="<f4")
    if next_index is None:
        next_index=end
    digest=hashlib.sha256(data.tobytes()).hexdigest()
    ch=SimpleNamespace(number=number, captured_samples=end,
                       samples=data, rate_hz=rate, next_index=next_index,
                       sha256=digest)
    return SimpleNamespace(session_id=session,input_domain=DOMAIN,
                           provisional=True,channels={number:ch})


def test_incremental_append_reuses_existing_real_history_once():
    ring=VerifiedLiveRing(capacity=8)
    assert ring.ingest_preview(preview(end=6))=={1}
    assert ring.channel(1).available==6
    np.testing.assert_array_equal(ring.channel(1).latest(6),np.arange(6))
    assert ring.ingest_preview(preview(end=6))==set()
    assert ring.channel(1).end==6
    # Second preview contains overlap: append only four new samples.
    assert ring.ingest_preview(preview(end=10, first=2))=={1}
    ch=ring.channel(1)
    assert ch.end==10
    assert ch.available==8
    assert ch.resets==0
    np.testing.assert_array_equal(ch.latest(8),np.arange(2,10))
    assert ring.ingest_preview(preview(end=10, first=2))==set()


def test_undocumented_missing_gap_discards_old_samples_instead_of_fabrication():
    ring=VerifiedLiveRing(capacity=8)
    ring.ingest_preview(preview(end=6))
    ring.ingest_preview(preview(end=100,values=np.arange(92,100,dtype="<f4")))
    ch=ring.channel(1)
    assert ch.resets==1
    assert ch.lost_samples==100-6-8
    assert ch.available==8
    np.testing.assert_array_equal(ch.latest(8),np.arange(92,100))


def test_uint32_device_rollover_independent_of_uint64_capture_counter():
    ring=VerifiedLiveRing(capacity=8)
    ring.ingest_preview(preview(end=6,values=np.arange(6),next_index=(1<<32)-2))
    ring.ingest_preview(preview(end=10,values=np.arange(2,10),next_index=2))
    ch=ring.channel(1)
    assert ch.end==10
    assert ch.resets==0
    np.testing.assert_array_equal(ch.latest(8),np.arange(2,10))


def test_new_session_or_rate_change_does_not_merge_heterogeneous_data():
    ring=VerifiedLiveRing(capacity=8)
    ring.ingest_preview(preview(end=6,rate=8192))
    ring.ingest_preview(preview(end=10,first=2,rate=32768))
    assert ring.channel(1).resets==1
    assert ring.channel(1).rate_hz==32768
    ring.ingest_preview(preview(session="RUN-B",end=4))
    assert ring.session_id=="RUN-B"
    assert ring.channel(1).end==4
    assert ring.channel(1).resets==0


def test_counter_rollback_and_mutated_duplicate_are_rejected():
    ring=VerifiedLiveRing(capacity=8)
    ring.ingest_preview(preview(end=6))
    with pytest.raises(ValueError,match="regressed"):
        ring.ingest_preview(preview(end=5))
    with pytest.raises(ValueError,match="Same Native counter"):
        ring.ingest_preview(preview(end=6,values=np.arange(10,16)))


def test_channel_specific_cursors_and_immutable_fft_copy():
    ring=VerifiedLiveRing(capacity=8)
    ring.ingest_preview(preview(end=6))
    ring.ingest_preview(preview(number=2,end=3,values=np.array([2,4,6])))
    assert ring.channel(1).end==6
    assert ring.channel(2).end==3
    copied=ring.channel(1).latest(6)
    copied[:] = -3000
    np.testing.assert_array_equal(ring.channel(1).latest(6),np.arange(6))
    assert ring.channel(2).rate_hz==8192


def test_unverified_source_domain_and_missing_uint64_are_rejected():
    ring=VerifiedLiveRing(capacity=8)
    source=preview(end=6)
    source.input_domain="RAW_UNCALIBRATED"
    with pytest.raises(ValueError,match="provenance-verified"):
        ring.ingest_preview(source)
    source=preview(end=6)
    source.channels[1].captured_samples=None
    with pytest.raises(ValueError,match="Unverified"):
        ring.ingest_preview(source)
    assert ring.channel(1).available==0 if ring.channel(1) else True


def test_invalid_read_length_is_not_zero_padded():
    ring=VerifiedLiveRing(capacity=8)
    ring.ingest_preview(preview(end=3))
    with pytest.raises(ValueError,match="Not enough"):
        ring.channel(1).latest(8192)
    with pytest.raises(ValueError,match="Not enough"):
        ring.channel(1).latest(0)


def test_rate_one_preview_length_cap_is_enforced():
    with pytest.raises(ValueError,match="capacity"):
        VerifiedLiveRing(capacity=0)
    ring=VerifiedLiveRing(capacity=8)
    with pytest.raises(ValueError,match="Unverified"):
        ring.ingest_preview(preview(end=9))
