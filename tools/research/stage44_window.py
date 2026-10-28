#!/usr/bin/env python3
"""Stage 44: reconstruct periodic RMS-normalized Hann window from IDR."""
import math
import struct

def window(n):
    if n <= 0 or n > 262144 or 262144 % n:
        raise ValueError("N must divide 262144")
    m = 262144
    step = m // n
    return [
        struct.unpack("<f", struct.pack("<f",
            (1 - math.cos(2 * math.pi * i * step / m)) / math.sqrt(1.5)
        ))[0]
        for i in range(n)
    ]

if __name__ == "__main__":
    for n in (512, 2048, 8192, 32768, 65536, 262144):
        w = window(n)
        rms = math.sqrt(sum(x*x for x in w)/n)
        mean = sum(w)/n
        assert abs(rms-1) < 5e-7, (n, rms)
        assert abs(mean-math.sqrt(2/3)) < 5e-7, (n,mean)
        assert abs(w[0]) < 1e-9
        print(f"N={n} RMS={rms:.9f} mean={mean:.9f}")
    print("PASS 6/6")
