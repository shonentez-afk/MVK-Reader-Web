#!/usr/bin/env python3
"""Stage63 documented address mapper: control config to control measurement."""
import struct
ZONES={0x00:"inactive_or_pending",0x11:"green",0x12:"sensor_fault",0x13:"invalid_config",0x14:"yellow",0x15:"red"}
def config_addresses(channel,slot):
    if not (1<=channel<=8 and 1<=slot<=8):raise ValueError()
    base=0x100+(channel-1)*0x100+0x60+(slot-1)*0x10
    return dict(parameter_number=base,yellow_threshold=base+2,red_threshold=base+4,
      up_delay=base+6,down_delay=base+8,yellow_hysteresis=base+10,
      red_hysteresis=base+12,display_maximum=base+14)
def measurement_addresses(channel,slot):
    if not (1<=channel<=8 and 1<=slot<=8):raise ValueError()
    base=0x2000+(channel-1)*0x200+0x130+(slot-1)*0x08
    return dict(value=base,state=base+2,at_transition=base+4,reserved=base+6)
def decode_control128(payload):
    if len(payload)!=128:raise ValueError("expected exactly 128 bytes")
    return [struct.unpack_from("<fIfI",payload,i*16) for i in range(8)]
if __name__=="__main__":
    assert config_addresses(1,1)["parameter_number"]==0x160
    assert config_addresses(8,8)["parameter_number"]==0x8D0
    assert measurement_addresses(1,1)["value"]==0x2130
    assert measurement_addresses(8,8)["value"]==0x2F68
    assert len({measurement_addresses(n,j)["value"] for n in range(1,9) for j in range(1,9)})==64
    print("PASS: 64 distinct slot-to-status mappings")
