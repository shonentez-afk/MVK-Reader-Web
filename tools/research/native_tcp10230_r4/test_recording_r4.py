import unittest, tempfile, struct
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
from protocol import ADC,Frame,ProtocolError
from recording_r4 import (AdcMetadata,CalibratedBinSink,calibrated_adc_bytes,
                          generate_tsxml)

def adc_frame(ch=0,index=0,rate=65536,value=.125):
    raw=struct.pack('<7I',ADC,1052,0,index,0,ch,rate)+struct.pack('<256f',*([value]*256))
    return Frame(ADC,1052,raw)

class RecordingTests(unittest.TestCase):
    def test_raw_times_gain(self):
        p=struct.pack('<256f',*([.125]*256))
        out=calibrated_adc_bytes(p,510.6)
        self.assertAlmostEqual(struct.unpack_from('<f',out)[0],63.825,places=4)

    def test_reject_invalid_gain(self):
        p=bytes(1024)
        for gain in (0,-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):calibrated_adc_bytes(p,gain)

    def test_tsxml_same_schema_as_real_original(self):
        m=AdcMetadata('MVKTEST-ADC1',0,65536,510.6)
        data=generate_tsxml(m,'MVKTEST-ADC1.bin',2124800,datetime(2026,10,28,10,12,5))
        root=ET.fromstring(data)
        self.assertEqual(root.findtext('DateTime'),'10/28/2026 10:12:05 AM')
        self.assertEqual(root.findtext('To'),'32421.88')
        self.assertEqual(root.findtext('FrequencyPerChannel'),'65536')
        self.assertEqual(root.findtext('./Channels/Channel/DataLength'),'8499200')
        self.assertEqual(root.findtext('./Channels/Channel/InternalChannelGain'),'510.6')
        self.assertEqual(root.findtext('./Channels/Channel/Units'),'м/с2')

    def test_atomic_calibrated_bin(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ADC1.bin'
            s=CalibratedBinSink(p,AdcMetadata('MVKTEST-ADC1',0,65536,510.6),
                                datetime(2026,10,28,10,12,5))
            s.append(adc_frame(index=1000));s.append(adc_frame(index=1256))
            result=s.finalize()
            self.assertEqual(result['samples'],512)
            self.assertEqual(p.stat().st_size,2048)
            self.assertTrue(Path(str(p)+'.tsxml').exists())
            self.assertFalse(Path(str(p)+'.partial').exists())

    def test_adc_gap_does_not_produce_valid_bin(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ADC1.bin'
            s=CalibratedBinSink(p,AdcMetadata('MVKTEST-ADC1',0,65536,510.6))
            s.append(adc_frame(index=0))
            with self.assertRaises(ProtocolError):s.append(adc_frame(index=999))
            with self.assertRaises(RuntimeError):s.finalize()
            self.assertFalse(p.exists())
            self.assertTrue(Path(str(p)+'.partial').exists())

    def test_missing_gain_rejected_before_file_create(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ADC1.bin'
            with self.assertRaises(ValueError):CalibratedBinSink(p,AdcMetadata('M',0,65536,0))
            self.assertFalse(p.exists())

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ADC1.bin';p.write_bytes(b'old')
            with self.assertRaises(FileExistsError):CalibratedBinSink(p,AdcMetadata('M',0,65536,500))
            self.assertEqual(p.read_bytes(),b'old')

if __name__=='__main__':unittest.main(verbosity=2)
