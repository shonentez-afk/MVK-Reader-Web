"""Source TMVKChannelStorage FRange reconciliation: original live != BIN gain.

Three private originals checked locally; none embedded.
Synthetic in-memory proof only, no Windows original Delphi x87 claim.
"""
from __future__ import annotations

import copy

import numpy as np
import pytest

from mvk_compatible.core.original_source_ring_receipt import (
    SOURCE_LIVE_ADC_DOMAIN,validate_original_storage_receipt,
)
from mvk_compatible.core.original_source_long_window import (
    load_source_long_window,submit_source_fft_window,
)
from mvk_compatible.core.native_r6_live_preview import (
    provisional_spectrum,provisional_waveform,
)
from mvk_compatible.core.storage_f_range_idr_candidate import (
    DOMAIN_ORIGINAL_STORAGE,
)
from .test_stage111z31fj_original_long_window import (
    long_source_status,response_fixture,
)


def test_source_live_ring_receipt_has_real_frange1_not_native_gain(tmp_path):
    run,status=long_source_status(tmp_path)
    assert status["source_original_storage"]["channels"][0]["input_domain"]==(
        SOURCE_LIVE_ADC_DOMAIN)
    # The source-window fixture previously tested only selected IPC
    # fields. Storage receipt QA requires its explicit Go V1 schema.
    status["source_original_storage"]["schema"]="MVK_SOURCE_CHANNEL_STORAGE_V1"
    receipt=validate_original_storage_receipt(
        status["source_original_storage"],status["channels"])
    assert receipt is not None
    row=receipt["channels"][0]
    assert row["original_live_f_range_single"]==1.0
    assert row["input_domain"]==SOURCE_LIVE_ADC_DOMAIN
    for invalid in (None,0,2,510,float('nan'),"1.0"):
        changed=copy.deepcopy(status["source_original_storage"])
        changed["channels"][0]["original_live_f_range_single"]=invalid
        with pytest.raises(ValueError,match="FRange"):
            validate_original_storage_receipt(changed,status["channels"])
    changed=copy.deepcopy(status["source_original_storage"])
    changed["channels"][0]["input_domain"]="CALIBRATED_NATIVE_R6_BIN_SPOOL_FLOAT32"
    with pytest.raises(ValueError,match="FRange"):
        validate_original_storage_receipt(changed,status["channels"])


def test_source_live_fft_consumes_original_f32_not_calibrated_preview(tmp_path):
    root,status=long_source_status(tmp_path)
    request=submit_source_fft_window(root,status,1,1024,
        request_id="0123456789abcdef0123456789abcdef")
    assert request is not None
    response_fixture(root,status,request)
    result=load_source_long_window(root,status,request)
    assert result is not None
    preview=result.preview
    assert preview.source_ring_provenance_verified
    assert preview.input_domain==SOURCE_LIVE_ADC_DOMAIN
    adc=preview.channels[1]
    assert len(adc.samples)==1024
    assert np.array_equal(adc.samples,np.arange(1024,dtype=np.float32))
    spectrum=provisional_spectrum(preview,1,1,n_fft=1024)
    assert spectrum["input_domain"]==DOMAIN_ORIGINAL_STORAGE
    assert spectrum["source_history_uses_original_live_f_range1_float32"]
    assert not spectrum["source_history_uses_exact_calibrated_float32"]
    assert spectrum["f_range_used"]==1.0
    assert spectrum["original_delphi_numerical_parity"] is False


def test_source_long_window_rejects_forged_old_bin_gain_domain(tmp_path):
    root,status=long_source_status(tmp_path)
    status["source_original_storage"]["channels"][0]["input_domain"]=(
        "CALIBRATED_NATIVE_R6_BIN_SPOOL_FLOAT32")
    with pytest.raises(ValueError,match="live FRange1"):
        submit_source_fft_window(root,status,1,1024,
            request_id="0123456789abcdef0123456789abcdef")
