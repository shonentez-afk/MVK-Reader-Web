# Stage92 — findings from official exchange protocol v1.0.39

Verified user/project document `протокол обмена МВК ред.1.0.39.doc` (official VAST-ARP exchange protocol). This document specifies **Modbus/TCP default port 502**; prior TCP:10230 stream uses a separate frame format and must not be assumed to share Modbus byte packing.

Section 3.5: measured channel parameter block `A=0x2000+N*0x200` for N=0..7; A+0x02 holds 43 float32 third-octave acceleration RMS values; A+0x60, +0x62, +0x64 are acceleration, velocity, displacement RMS in 10..3000Hz; A+0x120 holds status indicators. These computed floats originate in instrument DSP, distinct from MVKView desktop FFT `GetSpectrum`.

Section 3.7.5: index 15=16Hz, 16=20Hz, 17=25Hz, 18=31.5Hz, 19=40Hz, 27=250Hz, 28=315Hz. This independently confirms corrected band numbering.

Section 3.7.7 channel status: bit4=16Hz buffer not filled; filters with lower frequency under 3.9Hz disabled; bit5=64Hz buffer not filled, filters below 25Hz disabled; bit6=512Hz buffer not filled, all filters disabled. These flags may explain some transient/low-band mismatches, but only if flags were actually set during the MVK43 session; BIN/VALUES alone do not prove that. Do not silently discard values or assume ready flags from unsynchronized PCAP recordings.

Research implications: do not equate low band discrepancies with spectral FFT bug. Verify status bit availability and start time in same-session VALUES; compare frequency boundary tones and filter slopes separately. Document does NOT give exact per-band filter coefficients, filter order, startup settling times, or cycle timestamp semantics. Stable v0.3.40 unchanged, no instrument network actions.
