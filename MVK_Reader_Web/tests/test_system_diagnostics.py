import struct
from collector.decoder import decode_snapshot,decode_system,THIRD_OCTAVE_HZ

def u32(v):return [(v>>16)&0xffff,v&0xffff]

def test_system_decode_flags_and_serial():
    words=list(struct.unpack('>4H',b'MVK00044'))
    snap={'ranges':[{'address':0x1000,'values':words+u32(0x01071400)+u32((1<<0)|(1<<6))+u32(123456)+u32(8192)}, {'address':0x1020,'values':[0b10000101]}]}
    x=decode_system(snap)
    assert x['serial_number']=='MVK00044'
    assert x['firmware_version']=='1.7.20.0'
    assert x['uptime_seconds']==123456
    assert [e['bit'] for e in x['system_error_flags']]==[0,6]
    assert x['dsp_overload_channels']==[1,3,8]

def test_missing_diagnostics_not_reported_healthy():
    x=decode_snapshot({'ranges':[]})['system']
    assert x['system_errors_raw'] is None
    assert x['system_error_flags'] is None
    assert x['dsp_overload_channels'] is None

def test_octave_mapping_43_from_manual():
    assert len(THIRD_OCTAVE_HZ)==43
    assert THIRD_OCTAVE_HZ[0]==0.63 and THIRD_OCTAVE_HZ[-1]==10000
