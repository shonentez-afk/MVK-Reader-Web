#!/usr/bin/env python3
"""Stage111Z31R: local read-only verifier for two original x32dbg GetSpectrum passes.

Only standard library; private signal, ring, IDP and EXE bytes stay on operator PC.
No bitwise compatibility claim is made without independent original↔BIN pairing.
This verifier deliberately treats x32dbg text logs as supplemental, not truth.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

SCHEMA = 'MVKVIEW_STAGE111Z31R_TWO_MODE_CAPTURE_V1'
MAX_BYTES = 16 * 1024 * 1024
MODES = {0:'LOG',1:'ACCEL',2:'VELOCITY',3:'DISPLACEMENT'}

def u32(blob: bytes, offset: int) -> int:
    return struct.unpack_from('<I',blob,offset)[0]


def f32(blob: bytes, offset: int=0) -> float:
    return struct.unpack_from('<f',blob,offset)[0]


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def read_exact(root: Path, path: Path, size: int, *, optional=False) -> bytes:
    if path.is_symlink() or not path.is_file():
        if optional and not path.exists():
            return b''
        raise ValueError(f'missing/symlinked file {path.relative_to(root)}')
    actual=path.stat().st_size
    if not 0 < actual <= MAX_BYTES or actual != size:
        raise ValueError(f'wrong file length {path.relative_to(root)}: {actual}, expected {size}')
    return path.read_bytes()


def assert_float_array(raw: bytes, name: str, *, nonnegative=False) -> None:
    if len(raw)%4:
        raise ValueError('non Float32 size '+name)
    nonzero=False
    for (value,) in struct.iter_unpack('<f',raw):
        if not math.isfinite(value):
            raise ValueError('nonfinite Float32 in '+name)
        if nonnegative and value < 0:
            raise ValueError('negative power in '+name)
        if value != 0.0:
            nonzero=True
    if not nonzero:
        raise ValueError('all-zero measurement in '+name+' is not an acceptable golden')


def verify_one(root: Path, cfg: dict, label: str, code: int) -> dict:
    p=root/label
    n=cfg['fft_n']; fs=cfg['raw_sample_rate_hz']; mode=cfg['spectrum_mode']
    params={}
    for field in ('pre_dc','after_dc','pre_fft','after_fft','after_y','final'):
        params[field]=read_exact(root,p/('params_'+field+'.bin'),0x3C)
        if u32(params[field],0x08)!=code or u32(params[field],0x18)!=mode:
            raise ValueError(label+' SpectrumType/EnvelopeCode changed at '+field)
    raw_n=u32(params['pre_dc'],0x04)
    if raw_n < n or raw_n > 0x200000:
        raise ValueError(label+' invalid source history size')
    if u32(params['after_dc'],0x04)!=raw_n:
        raise ValueError(label+' source N changed before FIR unexpectedly')
    for field in ('pre_fft','after_fft','after_y','final'):
        if u32(params[field],0x04)!=n:
            raise ValueError(label+' output FFT N mismatch at '+field)
    output_fs=fs if code==0 else 32768
    for field in ('pre_fft','after_fft','after_y','final'):
        if u32(params[field],0x2C)!=output_fs or u32(params[field],0x28)!=n//2:
            raise ValueError(label+' output Fs or half count mismatch at '+field)
    for field in params:
        if params[field][0x20:0x28] != params['pre_dc'][0x20:0x28]:
            raise ValueError(label+' original source position changed within one GetSpectrum')
    if params['final'][0x00:0x30] != params['after_y'][0x00:0x30]:
        raise ValueError(label+' modified non-summary parameters between Y and final')
    summary=read_exact(root,p/'summary_triplet.bin',12)
    if params['final'][0x30:0x3C]!=summary:
        raise ValueError(label+' original summary triplet does not match final parameter bytes')
    storage=read_exact(root,p/'storage.bin',0x38)
    frange=read_exact(root,p/'frange.bin',4)
    if storage[4:8]!=frange:
        raise ValueError(label+' original FRange from storage does not equal saved field')
    # _Unit115:007D0A04..007D0A2F: code 0=Float32 ring; code 2=byte ring.
    # Code 1 was a false assumption in the v1.4 capture validator.
    if u32(storage,0x0C)!=0 or u32(storage,0x18)!=fs:
        raise ValueError(label+' original storage type/RAW Fs mismatch')
    gain=f32(frange)
    if not math.isfinite(gain) or gain<=0:
        raise ValueError(label+' nonfinite/invalid original FRange')
    mask=u32(storage,0x14)
    cap=u32(storage,0x10)
    if cap<4096 or cap>0x800000 or mask+1!=cap or cap&(cap-1):
        raise ValueError(label+' invalid ring buffer geometry')
    start=u32(params['pre_dc'],0x20)-raw_n
    end=u32(params['pre_dc'],0x20)
    if u32(params['pre_dc'],0x24)!=0 or end<raw_n:
        raise ValueError(label+' original 64-bit end outside supported local ring snapshot')
    if u32(storage,0x2C)!=0 or start<u32(storage,0x28) or end>u32(storage,0x20):
        raise ValueError(label+' ring history stale/overwritten')
    if raw_n>cap:
        raise ValueError(label+' requested real samples exceed ring capacity')
    ring_start_index=start&mask
    first_n=min(cap-ring_start_index,raw_n)
    tail_n=raw_n-first_n
    ring_head=read_exact(root,p/'ring_head.bin',first_n*4)
    ring_tail=read_exact(root,p/'ring_tail.bin',tail_n*4,optional=True) if tail_n else b''
    if tail_n==0 and (p/'ring_tail.bin').exists():
        raise ValueError(label+' unexpected stale ring_tail.bin')
    if len(ring_tail)!=tail_n*4:
        raise ValueError(label+' incomplete ring wrap tail')
    ring=ring_head+ring_tail
    raw_pre_dc=read_exact(root,p/'input_normalized_pre_dc.bin',raw_n*4)
    raw_after_dc=read_exact(root,p/'input_after_dc.bin',raw_n*4)
    before_fft=read_exact(root,p/'before_fft.bin',n*4)
    before_mode=read_exact(root,p/'power_before_mode.bin',n//2*4)
    after_mode=read_exact(root,p/'power_after_mode.bin',n//2*4)
    y=read_exact(root,p/'display_y.bin',n//2*4)
    for name,content in (
        ('original raw ring',ring),('normalized pre DC',raw_pre_dc),
        ('after DC',raw_after_dc),('before FFT',before_fft),
        ('power before mode',before_mode),('power after mode',after_mode),('Y',y)):
        assert_float_array(content,label+'/'+name,
                           nonnegative=name.startswith('power '))
    triplet=tuple(f32(summary,i) for i in (0,4,8))
    if not all(math.isfinite(v) for v in triplet):
        raise ValueError(label+' nonfinite RMS or peak summary')
    return {
        'code':code,'fft_n':n,'spectrum_mode':mode,
        'raw_fs_hz':fs,'output_fs_hz':output_fs,'raw_input_count':raw_n,
        'original_raw_end_index':end,'original_raw_first_index':start,
        'original_raw_ring_float32_sha256':sha(ring),
        'original_normalized_pre_dc_float32_sha256':sha(raw_pre_dc),
        'original_after_dc_float32_sha256':sha(raw_after_dc),
        'original_before_fft_float32_sha256':sha(before_fft),
        'original_power_before_mode_float32_sha256':sha(before_mode),
        'original_power_after_mode_float32_sha256':sha(after_mode),
        'original_display_y_float32_sha256':sha(y),
        'summary_triplet_float32_hex':[f'{u32(summary,i):08X}' for i in (0,4,8)],
        'f_range_float32_hex':f'{u32(frange,0):08X}',
        'ring_wrapped':bool(tail_n),'ring_head_float32_count':first_n,
        'ring_tail_float32_count':tail_n,
        'source_ring_type_float32':True, 'source_ring_adc_datatype':0,
        'buffer_snapshot_matches_planned_window':True,
        'source_same_capture_thread_and_frame_verified_by_log':False,
        '_ring':ring, '_normalized':raw_pre_dc,
    }


def verify(root: Path) -> dict:
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Missing/symlinked capture directory')
    cpath=root/'capture_config.json'
    if not cpath.is_file() or cpath.is_symlink() or cpath.stat().st_size>8192:
        raise ValueError('Missing or unsafe configuration')
    cfg=json.loads(cpath.read_text(encoding='utf-8-sig'))
    if not isinstance(cfg,dict) or cfg.get('schema')!=SCHEMA:
        raise ValueError('Wrong capture configuration version')
    for key,lo,hi in (('adc_claim',1,8),('fft_n',1024,262144),
                      ('spectrum_mode',0,3),('raw_sample_rate_hz',65536,65536),
                      ('envelope_code',20,20)):
        v=cfg.get(key)
        if type(v) is not int or not lo<=v<=hi:
            raise ValueError('invalid config '+key)
    if cfg['fft_n']&(cfg['fft_n']-1):
        raise ValueError('FFT N must be power of two')
    if cfg['spectrum_mode'] not in MODES:
        raise ValueError('unsupported SpectrumType')
    a=verify_one(root,cfg,'A',0)
    b=verify_one(root,cfg,'B',cfg['envelope_code'])
    equal_end=a['original_raw_end_index']==b['original_raw_end_index']
    suffix_match=(len(b['_normalized'])>=len(a['_normalized'])
                  and b['_normalized'][-len(a['_normalized']):]==a['_normalized'])
    ring_suffix_match=(len(b['_ring'])>=len(a['_ring'])
                  and b['_ring'][-len(a['_ring']):]==a['_ring'])
    if b['raw_input_count']<=a['raw_input_count']:
        raise ValueError('Envelope must use longer real input history than plain FFT')
    # Evidence should never be 'proven' by reading capture.log alone. It is
    # optional because earlier RedirectLog often wrote just redirect headers.
    # Each pass is resumed from an actual EIP=14AA stop, not held in a
    # long-running x32dbg script while the human selects the next GUI mode.
    # Logs are split to avoid old RedirectLog overwriting plain-mode evidence.
    # Plain and envelope marker files must BOTH be present to claim marker QA.
    def has_marker(filename, needles):
        logfile=root/filename
        if not logfile.is_file() or logfile.is_symlink() or logfile.stat().st_size>1_000_000:
            return False
        raw=logfile.read_bytes()
        for encoding in ('utf-8-sig','utf-16','utf-16-le','cp1251'):
            try:
                text=raw.decode(encoding)
            except UnicodeError:
                continue
            if all(needle in text for needle in needles):
                return True
        return False
    log_verified=(
        has_marker('capture_log_a_snapshot.txt', ('Z31R_A_COMPLETE', 'Z31R_A_SAVED'))
        and has_marker('capture_log_b_snapshot.txt', ('Z31R_B_COMPLETE', 'Z31R_BOTH_COMPLETE'))
    )
    if not log_verified:
        # Legacy single-script v1.2 receipts are supported for data validation.
        log_verified=any(has_marker(name, (
            'Z31R_A_COMPLETE','Z31R_B_COMPLETE','Z31R_BOTH_COMPLETE'))
            for name in ('capture_log_snapshot.txt','capture.log'))
    for x in (a,b):
        x.pop('_ring');x.pop('_normalized')
        x['source_same_capture_thread_and_frame_verified_by_log']=log_verified
    paired=equal_end and suffix_match and ring_suffix_match
    return {
        'schema':'MVKVIEW_STAGE111Z31R_VERIFICATION_REPORT_V1',
        'result': ('TWO_CAPTURE_FILES_VALID_SAME_END_AND_SAMPLES'
                   if paired else 'TWO_CAPTURE_FILES_VALID_BUT_NOT_SAME_WINDOW'),
        'capture_files_and_parameters_verified':True,
        'original_source_end_same_between_modes':equal_end,
        'shared_normalized_raw_tail_float32_bitwise_equal':suffix_match,
        'shared_original_ring_raw_tail_float32_bitwise_equal':ring_suffix_match,
        'operator_claimed_adc':cfg['adc_claim'],
        'operator_claimed_archive_identity_verified_independently':False,
        'original_and_native_bin_same_window_independently_verified':False,
        'original_executable_process_thread_provenance_independently_authenticated':False,
        'x32dbg_marker_text_present':log_verified,
        'f_range_identical_between_modes':a['f_range_float32_hex']==b['f_range_float32_hex'],
        'spectra':{'plain':a,'envelope':b},
        'warnings':([] if paired else [
            'Different original end position or actual RAW samples; do not compare as same-window source.']),
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir',help='locally generated run directory containing A/ and B/')
    parser.add_argument('--report',default=None,help='optional JSON output outside GitHub')
    args=parser.parse_args(argv)
    try:
        data=verify(Path(args.run_dir))
        content=json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)
        if args.report:
            target=Path(args.report)
            if target.exists():
                raise ValueError('refuse to overwrite an existing report')
            target.write_text(content+'\n',encoding='utf8')
        print(content)
        return 0 if data['result']=='TWO_CAPTURE_FILES_VALID_SAME_END_AND_SAMPLES' else 2
    except (ValueError,OSError,KeyError,TypeError,OverflowError,struct.error) as error:
        print('Z31R VERIFY FAIL:',str(error),file=sys.stderr)
        return 3

if __name__=='__main__':
    sys.exit(main())
