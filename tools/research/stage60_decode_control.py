#!/usr/bin/env python3
"""Stage60 manufacturer-compatible 16-byte control record decoder (read-only)."""
import struct

ZONE_CODES={0:"inactive_or_pending",0x11:"green",0x12:"sensor_fault",0x13:"config_fault",0x14:"yellow",0x15:"red"}

def decode_control_records(payload: bytes):
    if len(payload)!=128: raise ValueError("expected 128 bytes")
    records=[]
    for i in range(8):
        current,status,at_change,reserved=struct.unpack_from("<fIfI",payload,16*i)
        records.append({"slot":i+1,"value":current,"status_raw":status,
          "zone_code":status&0xff,"zone":ZONE_CODES.get(status&0xff,"unknown"),
          "sensor_fault_event":bool(status&(1<<9)),
          "yellow_event":bool(status&(1<<10)),
          "red_event":bool(status&(1<<11)),
          "value_at_change":at_change,"reserved_raw":reserved})
    return records

if __name__=="__main__":
    sample=bytearray(128)
    struct.pack_into("<fIfI",sample,0,5.25,0xC15,4.1,0xABCD)
    v=decode_control_records(sample)
    assert v[0]["zone"]=="red" and v[0]["red_event"] and v[0]["yellow_event"]
    assert v[0]["reserved_raw"]==0xABCD
    print("PASS synthetic 16-byte control record")
