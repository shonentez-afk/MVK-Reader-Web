import struct
from collector.decoder import decode_snapshot, decode_channel_status_words

def _words(v): return list(struct.unpack('>HH',struct.pack('>I',v)))

def test_channel_indicators_documented_bits():
    base=0x2000
    snap={'ranges':[{'address':base+0x120,'values':_words((1<<0)|(1<<5)|(1<<10))}]}
    ch=decode_snapshot(snap)['channels'][0]
    assert ch['channel']==1
    assert [e['bit'] for e in ch['channel_status']['active_flags']]==[0,5,10]
    assert ch['channel_status']['unrecognized_bits']==0

def test_channel_indicators_missing_and_unknown_bit():
    assert decode_channel_status_words([],0x2000)['available'] is False
    flag=decode_channel_status_words([{'address':0x2120,'values':_words(1<<15)}],0x2000)
    assert flag['available'] and flag['active_flags']==[] and flag['unrecognized_bits']==1<<15

def test_channel_status_is_bitfield_not_float():
    snap={'ranges':[{'address':0x2120,'values':_words(1)}]}
    assert decode_snapshot(snap)['channels'][0]['channel_status']['raw_u32']==1
