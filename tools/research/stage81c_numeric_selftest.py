#!/usr/bin/env python3
"""Stage81c synthetic consistency only. Not a real MVKView comparison."""
import math
TABLE=262144
def window(i,n):
    return (1-math.cos(2*math.pi*(i*(TABLE//n))/TABLE))/math.sqrt(1.5)
def convert(power,fs,n,repeats):
    out=list(power)
    for _ in range(repeats):
        out[0]=0.
        for k in range(1,len(out)):
            out[k]*=(1000/(2*math.pi*k*(fs/n)))**2
    return out
for n in (256,1024,8192,TABLE):
    mean=sum(window(i,n)**2 for i in range(n))/n
    assert abs(mean-1)<1e-10
    print("PASS window RMS",n,format(mean,".12f"))
for count in (1,2):
    result=convert([2.]*9,4096,1024,count)
    assert result[0]==0.
    for k in range(1,len(result)):
        expected=2*(1000/(2*math.pi*k*4))**(2*count)
        assert math.isclose(result[k],expected,rel_tol=1e-12)
    print("PASS frequency transform",count)
print("Synthetic tests only; no original BIN/TSXML/spectrum compared")
