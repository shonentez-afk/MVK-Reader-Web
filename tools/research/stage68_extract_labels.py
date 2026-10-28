#!/usr/bin/env python3
"""Read original MVKView eight frequency range labels from PE, offline."""
import struct,sys
b=open(sys.argv[1],'rb').read();pe=struct.unpack_from('<I',b,0x3c)[0]
assert b[pe:pe+4]==b'PE\0\0'
base=struct.unpack_from('<I',b,pe+24+28)[0]
n=struct.unpack_from('<H',b,pe+6)[0]; opt=struct.unpack_from('<H',b,pe+20)[0]
sec=[]
for i in range(n):
 s=b[pe+24+opt+i*40:pe+24+opt+(i+1)*40]
 vs,va,size,ptr=struct.unpack_from('<IIII',s,8);sec.append((va,size,ptr))
def off(v):
 r=v-base
 for va,sz,p in sec:
  if va<=r<va+sz:return p+r-va
 raise ValueError(hex(v))
a=off(0x8D303C); labels=[]
for i in range(8):
 ptr=struct.unpack_from('<I',b,a+4*i)[0];o=off(ptr)
 length=struct.unpack_from('<I',b,o-4)[0]
 labels.append(b[o:o+2*length].decode('utf-16le'))
assert labels==['10..3000 Гц','10..2000 Гц','10..1000 Гц','2..1000 Гц','0,8..300 Гц','0,8..150 Гц','Польз. 1','Польз. 2']
assert len({49+32*m+3*g+q for m in range(3) for g in range(8) for q in range(3)}|set(range(2,45)))==115
print('PASS 8 labels; 115 unique parameter IDs')
for i,x in enumerate(labels):print(i,x)
