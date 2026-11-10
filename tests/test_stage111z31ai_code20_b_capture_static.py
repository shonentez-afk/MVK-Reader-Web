"""Offline structural guards for original Stage111Z31AI Code20 B-only capture.

No x32dbg, proprietary signals, EXE, BIN or IDP are touched here.
"""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'tools/research/stage111z31ai_envelope20_b'

def test_correct_source_and_fft_n_at_different_stages():
    script=(FOLDER/'RESUME_B_CODE20_Z31AI_REVIEWED.txt').read_text(encoding='utf-8')
    assert 'cmp $z31r_ctx_raw_n,0x00040033\njne Z31R_FAIL_LENGTH' in script
    assert 'cmp dword:[ebx+4], 0x00020000\njne Z31R_FAIL_LENGTH' in script
    assert 'mov $z31r_fft_bytes,0x00020000' in script
    assert 'cmp dword:[ebx+0x28],0x00010000' in script
    assert '__OUT__' not in script
    assert script.count('run 0x007D') == 5
    for path in ('input_normalized_pre_dc.bin','input_after_dc.bin',
                 'before_fft.bin','power_before_mode.bin','power_after_mode.bin',
                 'display_y.bin','summary_triplet.bin'):
        assert '\\B\\'+path in script

def test_explicit_context_and_directory_before_run():
    script=(FOLDER/'RESUME_B_CODE20_Z31AI_REVIEWED.txt').read_text(encoding='utf-8')
    for marker in ('cmp eip,0x007D14AA','cmp $z31r_ctx_end,0x00088033',
                   'cmp dword:[$z31r_ctx_storage+0x28],0x00048000',
                   'cmp dword:[$z31r_ctx_storage+0x10],0x00200000',
                   'cmp dword:[$z31r_ctx_storage+0x04],0x43FF4853'):
        assert marker in script
    assert 'C:\\MVK_LOG\\STAGE111Z31AI_B_CAPTURE' in script

def test_b_only_config_contract():
    cfg=json.loads((FOLDER/'capture_config.json').read_text(encoding='utf-8'))
    assert cfg['schema']=='MVKVIEW_STAGE111Z31AI_B_ONLY_V1'
    assert cfg['adc_claim']==1 and cfg['envelope_code']==20
    assert cfg['spectrum_mode']==0
    assert cfg['raw_n']==262195
    assert cfg['fft_n']==131072 and cfg['y_bins']==65536
    assert cfg['raw_n']==cfg['fft_n']*2+51
    assert cfg['source_end']-cfg['raw_n']==cfg['storage_oldest']==294912
    assert cfg['frange_u32']=='0x43FF4853'
    assert cfg['expected_pre_dc_sha256']=='86856251ab33201aec2ccbf43f0e33ea0bf658cd3f1112183071d13b665949c5'

def test_validator_uses_b_only_and_failure_is_not_parity_pass():
    ver=(FOLDER/'Verify-Capture-Code20-BOnly.py').read_text(encoding='utf-8')
    assert 'def verify_b_only(' in ver
    assert "verify_one(root, {'fft_n':_B_FFT_N,'spectrum_mode':0,'raw_sample_rate_hz':65536},'B',20)" in ver
    assert "original_FIR_FFT_LOG_Y_match_clone':False" in ver
    assert 'B_CAPTURE_FILES_VALID_NOT_NUMERIC_PARITY' in ver
