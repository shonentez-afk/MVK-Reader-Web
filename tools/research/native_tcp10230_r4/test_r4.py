"""Synthetic offline tests for read-only session + rate-command encoding."""
import math
import struct
import unittest

from protocol import (ADC, TACH, PARAM, ID, ACK, DENIED, Frame, Framer,
                      ProtocolError)
from session_r4 import NativeSession, Phase, Mode
from wire_preview import rate_message_preview,parse_rate_message

def param_frame(blocks):
    words=[struct.pack('<II5I',PARAM,0,0,0,0,0,len(blocks))]
    for addr,data in blocks:
        if len(data)%4:raise ValueError('even register count required')
        words.append(struct.pack('<I',((len(data)//2)<<16)|addr))
        words.append(data)
    raw=b''.join(words)
    raw=raw[:4]+struct.pack('<I',len(raw))+raw[8:]
    return Frame(PARAM,len(raw),raw)

def samples_frame(channel=0,rate=65536,kind=ADC):
    n=256 if kind==ADC else 64
    raw=struct.pack('<7I',kind,28+4*n,0,0,0,channel,rate)+struct.pack('<%df'%n,*([0.125]*n))
    return Frame(kind,len(raw),raw)

def id_frame():return Frame(ID,264,struct.pack('<II',ID,264)+bytes(256))

def aux4700_frame():
    blocks=[]
    for ch in range(8):
        arr=[float(i+ch*10)/10 for i in range(144)]
        # Status bits 4 and 5 prove low-frequency readiness exposure.
        status=(1<<4|1<<5) if ch==0 else 0
        blocks.append((0x2000+ch*0x200,struct.pack('<144fI',*arr,status)))
    x=param_frame(blocks)
    assert x.length==4700
    return x

class NativeR4Tests(unittest.TestCase):
    def test_rate_command_exact_36_bytes(self):
        expected=bytes.fromhex('0d0c80ff24000000'+'00000000'*4+'01000000'+'0e000200'+'00000100')
        self.assertEqual(rate_message_preview(65536),expected)
        self.assertEqual(parse_rate_message(expected),65536)

    def test_rate_command_bad_value(self):
        with self.assertRaises(ValueError):rate_message_preview(1200)
        with self.assertRaises(ValueError):parse_rate_message(b'\x00'*36)

    def test_live_session_identity_and_ready(self):
        s=NativeSession(expected_rate=65536);s.begin()
        self.assertEqual(s.phase,Phase.WAITING)
        s.ingest(id_frame())
        self.assertTrue(s.identity_observed)
        s.ingest(param_frame([(0x1000,struct.pack('<2I',123,456))]))
        self.assertEqual(s.phase,Phase.ACTIVE)
        self.assertEqual(s.registers.u32(0x1000),123)

    def test_one_shot_config_read_complete(self):
        s=NativeSession(Mode.READ_CONFIGURATION);s.begin()
        ev=s.ingest(param_frame([(0,bytes(0x4000*2))]))
        self.assertEqual(ev.event,'configuration_read_complete')
        self.assertTrue(s.full_snapshot_observed)
        self.assertEqual(s.phase,Phase.SNAPSHOT_DONE)
        with self.assertRaises(RuntimeError):s.ingest(id_frame())

    def test_replay_begins_midstream_without_identity(self):
        s=NativeSession(capture_midstream=True,expected_rate=65536);s.begin()
        s.ingest(samples_frame())
        self.assertFalse(s.initialization_observed)
        self.assertEqual(s.phase,Phase.WAITING)
        s.ingest(param_frame([(0x3100,struct.pack('<2I',0,1))]))
        self.assertEqual(s.phase,Phase.ACTIVE)
        self.assertFalse(s.identity_observed)
        self.assertIn('unknown phase',s.warnings[0])

    def test_full_calculated_update_eight_channels(self):
        s=NativeSession(expected_rate=65536);s.begin()
        e=s.ingest(aux4700_frame())
        self.assertEqual(e.event,'calculated')
        self.assertEqual(s.phase,Phase.ACTIVE)
        self.assertEqual(s.calculation_updates,1)
        self.assertEqual(len(s.last_calculated),8)
        self.assertTrue(s.last_calculated[0]['not_ready']['fs16'])
        self.assertTrue(s.last_calculated[0]['not_ready']['fs64'])
        self.assertAlmostEqual(s.last_calculated[3]['band_rms'][0],7.8,places=5)

    def test_ack_is_not_proof_of_our_write(self):
        s=NativeSession();s.begin()
        e=s.ingest(Frame(ACK,8,struct.pack('<II',ACK,8)))
        self.assertEqual(e.event,'ack_observed')
        self.assertFalse(e.detail['command_executed_by_this_module'])

    def test_denial_fails_closed(self):
        s=NativeSession();s.begin()
        with self.assertRaises(ProtocolError):s.ingest(Frame(DENIED,8,struct.pack('<II',DENIED,8)))
        self.assertEqual(s.phase,Phase.FAILED)

    def test_reject_wrong_rate_and_clear_registers(self):
        s=NativeSession(expected_rate=65536);s.begin()
        s.ingest(param_frame([(0x2000,struct.pack('<2I',111,222))]))
        with self.assertRaises(ProtocolError):s.ingest(samples_frame(rate=32768))
        self.assertEqual(s.phase,Phase.FAILED)
        with self.assertRaises(ProtocolError):s.registers.read(0x2000,2)

    def test_bad_aux_layout_does_not_corrupt_image(self):
        s=NativeSession();s.begin()
        bad=param_frame([(0x3000+ch*0x10,bytes(580)) for ch in range(8)])
        self.assertEqual(bad.length,4700)
        with self.assertRaises(ProtocolError):s.ingest(bad)
        self.assertEqual(s.phase,Phase.FAILED)
        with self.assertRaises(ProtocolError):s.registers.read(0x3000,2)

    def test_values_tick_on_address_3100(self):
        s=NativeSession();s.begin()
        e=s.ingest(param_frame([(0x3100,bytes(44))]))
        self.assertEqual(e.event,'values_tick')
        self.assertEqual(s.events['values_row_trigger'],1)

    def test_recording_ends_with_partial_frame_marked(self):
        s=NativeSession();s.begin()
        result=s.end(988)
        self.assertEqual(result['truncated_end_bytes'],988)
        self.assertEqual(s.phase,Phase.CLOSED)
        self.assertEqual(s.events['unfinished_app_frame'],1)

    def test_transport_break_invalidates_calculations(self):
        s=NativeSession();s.begin();s.ingest(aux4700_frame())
        self.assertIsNotNone(s.last_calculated)
        s.transport_break('offline test')
        self.assertEqual(s.phase,Phase.FAILED)
        self.assertIsNone(s.last_calculated)
        with self.assertRaises(ProtocolError):s.registers.read(0x2000,2)

    def test_fragmented_framer(self):
        raw=aux4700_frame().raw
        f=Framer();self.assertEqual(f.feed(raw[:11]),[])
        self.assertEqual(f.feed(raw[11:4095]),[])
        frames=f.feed(raw[4095:]);self.assertEqual(len(frames),1)
        s=NativeSession();s.begin();s.ingest(frames[0]);self.assertEqual(s.calculation_updates,1)

    def test_two_separate_session_epochs_do_not_share_registers(self):
        a=NativeSession();a.begin();a.ingest(aux4700_frame());a.end()
        b=NativeSession();b.begin()
        with self.assertRaises(ProtocolError):b.registers.read(0x2000,2)

    def test_sample_channels_and_count(self):
        s=NativeSession(expected_rate=65536);s.begin()
        s.ingest(samples_frame(0));s.ingest(samples_frame(9,kind=TACH))
        self.assertEqual(s.sample_counts[0],256)
        self.assertEqual(s.sample_counts[9],64)

if __name__=='__main__':unittest.main(verbosity=2)
