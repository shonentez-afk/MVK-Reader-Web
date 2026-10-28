#!/usr/bin/env python3
"""Stage 53 offline verification of TSXML/FC03 mapping. No network or writes."""
fc03={
"83": [511.1202698,508.3706360,508.5932922,509.9058228,512.0080566,508.0881042,511.0447388,507.0070496],
"84": [510.5650330,512.0983276,509.7116089,510.2197571,513.7924194,509.6076355,509.3231201,508.7424011]
}
samples=[("00000043",1,510.6,"84"),("00000043",3,509.7,"84"),("00000043",6,509.6,"84"),("00000050",4,509.9,"83"),("00000050",6,508.1,"83")]
for serial,ch,tsxml,ip in samples:
    difference=abs(tsxml-fc03[ip][ch-1])
    assert difference <= 0.05, (serial,ch,ip,difference)
    other="83" if ip=="84" else "84"
    assert difference < abs(tsxml-fc03[other][ch-1])
    print(serial,ch,tsxml,ip,round(difference,8))
print("PASS 5/5 rounded matches; independent serial/IP confirmation still required")
