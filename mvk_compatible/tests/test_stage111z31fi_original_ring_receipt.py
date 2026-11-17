"""Offline integrity tests for original ten-channel Float32/byte ring."""
import pytest
from mvk_compatible.core.original_source_ring_receipt import (
    validate_original_storage_receipt,BUFFER_ELEMENTS,SCHEMA,
    ADC_DOMAIN,TACH_DOMAIN,
)


def ring_fixture():
    channels=[]
    rows=[]
    for i in range(10):
        adc=i<8
        samples=4096 if adc else 1024
        channels.append({
            "channel":i+1,"samples":samples,"sample_rates_hz":[65536],
            "sequence_discontinuities":0,"nonfinite_samples":0,
            "next_sample_index":100000+samples,
        })
        rows.append({
            "channel":i+1,"sample_width_bytes":4 if adc else 1,
            "rx_pos_64":samples if adc else samples*4,
            "valid_pos_64":0,"first_readable_pos_64":0,
            "available_elements":samples if adc else samples*4,
            "last_sample_rate_hz":65536,
            "next_device_sample_index":100000+samples,
            "input_domain":"RAW_DEVICE_FLOAT32_NOT_YET_CALIBRATED"
                if adc else TACH_DOMAIN,
            "sequence_gaps":0,"rate_changes":0,
            "rejected_nonfinite_frames":0,
        })
    return {"schema":SCHEMA,"buffer_elements_per_channel":BUFFER_ELEMENTS,
            "channels":rows},channels


def test_original_source_ring_widths_and_accounting():
    receipt,status=ring_fixture()
    valid=validate_original_storage_receipt(receipt,status)
    assert valid["verified_only_source_go_accounting"]
    assert not valid["original_delphi_memory_parity_verified"]
    assert [x["sample_width_bytes"] for x in valid["channels"]]==[4]*8+[1]*2
    assert valid["channels"][9]["rx_pos_64"]==4096
    assert validate_original_storage_receipt(None,status) is None


def test_original_2m_ring_wrap_and_invalidate_on_rate():
    receipt,status=ring_fixture()
    latest=BUFFER_ELEMENTS+8192
    r=receipt["channels"][0]
    status[0]["samples"]=latest
    r.update(rx_pos_64=latest,valid_pos_64=0,first_readable_pos_64=8192,
             available_elements=BUFFER_ELEMENTS)
    assert validate_original_storage_receipt(receipt,status)["channels"][0][
        "first_readable_pos_64"]==8192
    r.update(valid_pos_64=latest-1024,first_readable_pos_64=latest-1024,
             available_elements=1024)
    assert validate_original_storage_receipt(receipt,status)["channels"][0][
        "available_elements"]==1024


@pytest.mark.parametrize("change",[
    lambda r,c:r.update(buffer_elements_per_channel=262144),
    lambda r,c:r["channels"].pop(),
    lambda r,c:r["channels"][8].update(sample_width_bytes=4),
    lambda r,c:r["channels"][0].update(rx_pos_64=True),
    lambda r,c:r["channels"][0].update(valid_pos_64=10000),
    lambda r,c:r["channels"][0].update(first_readable_pos_64=1),
    lambda r,c:r["channels"][0].update(available_elements=5000),
    lambda r,c:r["channels"][0].update(input_domain="UNKNOWN"),
    lambda r,c:r["channels"][0].update(next_device_sample_index=100001),
    lambda r,c:r["channels"][0].update(rx_pos_64=5000),
    lambda r,c:r["channels"][0].update(last_sample_rate_hz=8192),
    lambda r,c:r["channels"][0].update(rejected_nonfinite_frames=1),
    lambda r,c:r["channels"][1].update(sequence_gaps=3),
])
def test_invalid_source_ring_metadata_rejected(change):
    receipt,status=ring_fixture()
    change(receipt,status)
    with pytest.raises(ValueError):
        validate_original_storage_receipt(receipt,status)


def test_tach_byte_ring_cannot_be_relabelled_as_float32():
    receipt,status=ring_fixture()
    assert validate_original_storage_receipt(receipt,status)
    status[8]["samples"]=1023
    with pytest.raises(ValueError,match="counters disagree"):
        validate_original_storage_receipt(receipt,status)


def test_no_unobserved_device_index_invented_for_empty_storage():
    receipt,status=ring_fixture()
    receipt["channels"][0].update(
        rx_pos_64=0,available_elements=0,next_device_sample_index=None)
    assert validate_original_storage_receipt(receipt,status)


def test_original_tach_byte_receipt_never_invents_float32_rejection():
    receipt,status=ring_fixture()
    status[8]["nonfinite_samples"]=1  # Go may flag a suspect Float32 TACH
    receipt["channels"][8]["rejected_nonfinite_frames"]=1
    with pytest.raises(ValueError,match="byte TACH"):
        validate_original_storage_receipt(receipt,status)
    receipt["channels"][8]["rejected_nonfinite_frames"]=0
    assert validate_original_storage_receipt(receipt,status)
