"""Stage111R: synthetic PE file integrity and anti-substitution tests."""
import hashlib
import json
import pytest
from mvk_compatible.verify_windows_preview_artifact import verify_preview, main, EXE_NAME, BRANCH

SHA = '0123456789abcdef0123456789abcdef01234567'


def make(tmp_path, *, sha=SHA, branch=BRANCH):
    folder = tmp_path / 'dist'
    folder.mkdir()
    data = bytearray(1024)
    data[:2] = b'MZ'
    data[0x3c:0x40] = (128).to_bytes(4, 'little')
    data[128:132] = b'PE\0\0'
    data[-5:] = b'hello'
    binary = bytes(data)
    (folder / EXE_NAME).write_bytes(binary)
    (folder / 'SHA256SUMS.txt').write_text(
        hashlib.sha256(binary).hexdigest()+'  '+EXE_NAME+'\n', encoding='ascii')
    (folder / 'BUILD_INFO.txt').write_text('commit='+sha+'\nbranch='+branch+'\n', encoding='ascii')
    return folder


def test_verified_receipt_and_cli_uses_actual_pe_bytes(tmp_path, capsys):
    folder = make(tmp_path)
    receipt = verify_preview(folder, expected_commit=SHA)
    assert receipt['sha256_actual_exe_matches_manifest']
    assert receipt['build_manifest_verified']
    assert receipt['pe_header_verified']
    assert receipt['source_commit'] == SHA
    assert not receipt['separate_download_integrity_verified']
    assert not receipt['original_delphi_compatibility_verified']
    assert main(['--dist',str(folder),'--expected-commit',SHA,
                 '--receipt-json',str(folder / 'BUILD_VERIFICATION.json')]) == 0
    serialized=json.loads(capsys.readouterr().out)
    assert serialized==json.loads((folder/'BUILD_VERIFICATION.json').read_text())


def test_exe_byte_tamper_is_detected(tmp_path):
    folder=make(tmp_path)
    exe=folder/EXE_NAME
    content=bytearray(exe.read_bytes());content[-1]^=3;exe.write_bytes(content)
    with pytest.raises(ValueError,match='does not match'):
        verify_preview(folder,expected_commit=SHA)


@pytest.mark.parametrize('filename,new_value,pattern',[
    ('SHA256SUMS.txt','bad\n','manifest'),
    ('SHA256SUMS.txt','0'*64+'  ../evil.exe\n','manifest'),
    ('BUILD_INFO.txt','commit='+SHA+'\nbranch=main\n','mismatch'),
    ('BUILD_INFO.txt','commit='+SHA+'\nbranch='+BRANCH+'\nbranch=main\n','exact order'),
])
def test_modified_manifest_is_rejected(tmp_path,filename,new_value,pattern):
    folder=make(tmp_path)
    (folder/filename).write_text(new_value)
    with pytest.raises(ValueError,match=pattern):
        verify_preview(folder,expected_commit=SHA)


def test_wrong_expected_commit_and_branch_are_rejected(tmp_path):
    folder=make(tmp_path)
    for commit in ('main','g'*40,'0'*39,True):
        with pytest.raises(ValueError):
            verify_preview(folder,expected_commit=commit)
    with pytest.raises(ValueError,match='mismatch'):
        verify_preview(folder,expected_commit='f'*40)
    with pytest.raises(ValueError,match='isolated'):
        verify_preview(folder,expected_commit=SHA,expected_branch='main')


def test_symlink_and_non_exe_fail_closed(tmp_path):
    folder=make(tmp_path)
    exe=folder/EXE_NAME
    f=folder/'backup.bin';f.write_bytes(exe.read_bytes());exe.unlink()
    try: exe.symlink_to(f)
    except OSError: pytest.skip('Creating Windows symlinks not permitted')
    with pytest.raises(ValueError,match='regular artifact'):
        verify_preview(folder,expected_commit=SHA)


def test_pe_signature_tamper_rejected_before_checksum(tmp_path):
    folder=make(tmp_path)
    exe=folder/EXE_NAME
    data=bytearray(exe.read_bytes());data[128:132]=b'NOPE';exe.write_bytes(data)
    with pytest.raises(ValueError,match='PE signature'):
        verify_preview(folder,expected_commit=SHA)
