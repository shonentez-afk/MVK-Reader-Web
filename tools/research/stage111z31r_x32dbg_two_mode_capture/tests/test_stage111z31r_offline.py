"""Deterministic synthetic tests, no original MVKView, x32dbg or private data."""
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import re
import struct
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('z31r_verify',SOURCE/'Verify-Capture.py')
ver=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ver)


def put32(target,offset,value):
    struct.pack_into('<I',target,offset,value)


def synth_run(root,*,n=4096,end=16999,mode=2,broken_end=False,corrupt_normalized=False):
    cap=16384
    a_len=n
    b_len=n+102
    common=[]
    for i in range(b_len):
        signal=(math.sin(i*.057)+math.cos(i*.071)+.15)*.3
        common.append(struct.pack('<f',signal))
    data=b''.join(common)
    for phase,code,length in [('A',0,a_len),('B',20,b_len)]:
        p=root/phase
        p.mkdir(parents=True)
        e=end+1 if phase=='B' and broken_end else end
        window=data[-length*4:]
        if corrupt_normalized and phase=='B':
            arr=bytearray(window);arr[-32]^=0x08;window=bytes(arr)
        for field in ['pre_dc','after_dc','pre_fft','after_fft','after_y','final']:
            params=bytearray(60)
            put32(params,4,length if field in ('pre_dc','after_dc') else n)
            put32(params,8,code)
            put32(params,0x18,mode)
            put32(params,0x20,e)
            put32(params,0x28,0 if field in ('pre_dc','after_dc') else n//2)
            put32(params,0x2C,0 if field in ('pre_dc','after_dc') else (65536 if not code else 32768))
            if field=='final':
                struct.pack_into('<3f',params,0x30,3.14,20.,1.6)
            (p/('params_'+field+'.bin')).write_bytes(params)
        (p/'summary_triplet.bin').write_bytes((p/'params_final.bin').read_bytes()[0x30:0x3C])
        s=bytearray(0x38)
        put32(s,4,0x3F800000)
        put32(s,0x0C,1)
        put32(s,0x10,cap)
        put32(s,0x14,cap-1)
        put32(s,0x18,65536)
        put32(s,0x20,e)
        put32(s,0x28,0)
        put32(s,0x34,0x70000000)
        (p/'storage.bin').write_bytes(s)
        (p/'frange.bin').write_bytes(struct.pack('<f',1.0))
        first_index=(e-length)%(cap)
        first_count=min(cap-first_index,length)
        (p/'ring_head.bin').write_bytes(window[:first_count*4])
        if first_count<length:
            (p/'ring_tail.bin').write_bytes(window[first_count*4:])
        (p/'input_normalized_pre_dc.bin').write_bytes(window)
        (p/'input_after_dc.bin').write_bytes(window)
        (p/'before_fft.bin').write_bytes((window[-n*4:]))
        vals=[0.1+0.001*i for i in range(n//2)]
        vals[:2]=[0.,0.]
        power=struct.pack('<%df'%(n//2),*vals)
        (p/'power_before_mode.bin').write_bytes(power)
        (p/'power_after_mode.bin').write_bytes(power)
        (p/'display_y.bin').write_bytes(struct.pack('<%df'%(n//2),*[max(0.,x)*.75 for x in vals]))
    cfg={'schema':ver.SCHEMA,'adc_claim':4,'fft_n':n,
        'raw_sample_rate_hz':65536,'spectrum_mode':mode,'envelope_code':20}
    (root/'capture_config.json').write_text(json.dumps(cfg),encoding='utf8')


class TestStaticScript(unittest.TestCase):
    def test_has_complete_two_stage_original_chain(self):
        s=(SOURCE/'CAPTURE_BOTH.template.txt').read_text(encoding='ascii')
        for a in ('0x007D14AA','0x007D14B8','0x007D153D','0x007D154B',
                  '0x007D17E7','0x007D1900'):
            self.assertEqual(s.count('run '+a),2,a)
        for phase in ('A','B'):
            for field in ('params_pre_dc.bin','input_normalized_pre_dc.bin',
                          'ring_head.bin','input_after_dc.bin','before_fft.bin',
                          'power_before_mode.bin','power_after_mode.bin',
                          'display_y.bin','summary_triplet.bin','params_final.bin'):
                self.assertIn('__OUT__\\'+phase+'\\'+field,s)
        for pattern in ('Z31R_FAIL_STOP','Z31R_FAIL_MEMORY',
                        'Z31R_FAIL_HISTORY','Z31R_FAIL_FRAME','Z31R_FAIL_FILTER',
                        'Z31R_FAIL_OPCODE','Z31R_FAIL_PAIR_SOURCE'):
            self.assertIn(pattern,s)
        self.assertIn('cmp mem.base($z31r_chk_address),mem.base($z31r_chk_last)',s)
        self.assertIn('cmp dword:[$z31r_ctx_storage+0x0C],0x1',s)
        self.assertIn('cmp $z31r_ctx_start,dword:[$z31r_ctx_storage+0x28]',s)
        self.assertIn('RedirectLog ',s)
        self.assertIn('SaveLog ',s)
        self.assertIn('Z31R_BOTH_COMPLETE',s)
        self.assertEqual(s.count('run 0x007D14AA'),2)
        self.assertNotRegex(s, r'(?m)^\s*F9\b')
        self.assertNotIn('mem.valid($z31r_ctx_work)',s)
        self.assertTrue(s.isascii())
        source_lines=s.splitlines()
        labels={x[:-1] for x in source_lines if x.endswith(':') and x.startswith('Z31R_')}
        for line in source_lines:
            m=re.match(r'^(?:j[a-z]+|call) (Z31R_[A-Z_]+)$',line)
            if m:
                self.assertIn(m.group(1),labels,'unresolved script label '+m.group(1))
    def test_all_original_signatures_verified_before_first_run(self):
        s=(SOURCE/'CAPTURE_BOTH.template.txt').read_text('ascii')
        pre=s.split('run 0x007D14AA')[0]
        for addr,signature in [('007D14AA',['8B','4B','04']),('007D14B8',['8B','43','08']),
                               ('007D153D',['8B','4B','04']),('007D154B',['8B','43','28']),
                               ('007D17E7',['33','C0']),('007D1900',['33','C0'])]:
            a=int(addr,16)
            for i,byte in enumerate(signature):
                self.assertIn(f'cmp byte:[0x{a+i:08X}], 0x{byte}',pre)
    def test_readonly_preflight_no_run_or_savedata(self):
        s=(SOURCE/'CHECK_READY.template.txt').read_text('ascii')
        self.assertNotIn('run 0x',s)
        self.assertNotIn('savedata ',s)
        self.assertIn('Z31R_READY_OK',s)
    def test_ps5_generator_contains_unique_path_guards(self):
        s=(SOURCE/'Prepare-Capture.ps1').read_text('utf8')
        for k in ('NewGuid','New-Item -ItemType Directory','__HALF_N_HEX__',
                  'ConvertTo-Json','-Encoding UTF8','Get-FileHash','ArchiveBin'):
            self.assertIn(k,s)


class TestSyntheticReceipt(unittest.TestCase):
    def test_real_ring_wrap_and_normalized_overlap_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            report=ver.verify(root)
            self.assertTrue(report['capture_files_and_parameters_verified'])
            self.assertEqual(report['result'],'TWO_CAPTURE_FILES_VALID_SAME_END_AND_SAMPLES')
            self.assertTrue(report['shared_original_ring_raw_tail_float32_bitwise_equal'])
            self.assertTrue(report['spectra']['plain']['ring_wrapped'])
            self.assertTrue(report['spectra']['envelope']['ring_wrapped'])
            self.assertFalse(report['original_and_native_bin_same_window_independently_verified'])
            self.assertFalse(report['x32dbg_marker_text_present'])
    def test_wrong_end_is_valid_single_capture_but_not_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root,broken_end=True)
            r=ver.verify(root)
            self.assertEqual(r['result'],'TWO_CAPTURE_FILES_VALID_BUT_NOT_SAME_WINDOW')
            self.assertFalse(r['original_source_end_same_between_modes'])
    def test_same_end_changed_samples_not_same_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root,corrupt_normalized=True)
            r=ver.verify(root)
            self.assertEqual(r['result'],'TWO_CAPTURE_FILES_VALID_BUT_NOT_SAME_WINDOW')
            self.assertFalse(r['shared_normalized_raw_tail_float32_bitwise_equal'])
    def test_original_summary_must_be_physical_12_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            f=root/'B'/'summary_triplet.bin';f.write_bytes(b'badbadbadbad')
            with self.assertRaisesRegex(ValueError,'triplet'):
                ver.verify(root)
    def test_truncated_y_refuses_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            f=root/'A'/'display_y.bin';f.write_bytes(f.read_bytes()[:-4])
            with self.assertRaisesRegex(ValueError,'wrong file length'):
                ver.verify(root)
    def test_wrong_channel_claim_bool_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            p=root/'capture_config.json';c=json.loads(p.read_text());c['adc_claim']=True;p.write_text(json.dumps(c))
            with self.assertRaisesRegex(ValueError,'adc_claim'):
                ver.verify(root)
    def test_nonfinite_source_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            p=root/'B'/'before_fft.bin';b=bytearray(p.read_bytes());struct.pack_into('<f',b,16,float('nan'));p.write_bytes(b)
            with self.assertRaisesRegex(ValueError,'nonfinite'):
                ver.verify(root)
    def test_unknown_schema_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            p=root/'capture_config.json';cfg=json.loads(p.read_text());cfg['schema']='BOGUS';p.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError,'version'):
                ver.verify(root)
    def test_missing_ring_tail_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            (root/'A'/'ring_tail.bin').unlink()
            with self.assertRaisesRegex(ValueError,'incomplete ring wrap tail'):
                ver.verify(root)
    def test_mismatched_f_range_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            (root/'A'/'frange.bin').write_bytes(struct.pack('<f',510.))
            with self.assertRaisesRegex(ValueError,'FRange'):
                ver.verify(root)

if __name__=='__main__':
    unittest.main()
