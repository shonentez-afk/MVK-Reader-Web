# Stage91 — manual, MVKView IDR and real tonal peaks (2026-10-29)

Evidence: user-provided MVK01 operating manual `ВАРБ.411711.112 РЭ МВК.pdf` located in project Library, original IDR `_Unit115.pas`/`_Unit125.pas`, and real MVK43 ADC1/3/6 BIN (same session as VALUES; PCAPNG is NOT same session).

## Confirmed from original manual
Section 5.2, page marked 22: instrument DSP calculates **third-octave acceleration/velocity/displacement RMS** in 43 bands 0.63..10000 Hz; some fixed band measurements have frequency-dependent conversion per **GOST ISO 2954-2014**, while 0.8..150 and 0.8..300 Hz use nonstandard project-specific conversion. Manual table 3.5.5, page marked 53, numbers individual band indices (16=20Hz, 17=25Hz, 18=31.5Hz, 19=40Hz). The manual text says row based on base 2, while the supplied clone's `0.63*10^((k-1)/10)` approximates base-ten R10: exact band-center/boundary convention is NOT yet settled by this observation alone. Need evaluate both standard formulas, particularly 16/25/31.5/40Hz.

## Original program distinction
Original MVKView `_Unit115.pas` includes `TMvkChannelStorage.GetSpectrum`, `TDSXFastFourier`, Hann-windowed local graphical FFT. The 43 third-octave VALUES entries are supplied as calculation parameters from the instrument DSP; therefore **do not equate the MVKView graphical FFT implementation with the 43 DSP filter bank**. `_Unit125.pas` handles parameter block values and CSV emission, not original DSP coefficient synthesis. Original DSP filter coefficients are not contained in the desktop IDR; proving exact filter transfer functions requires firmware analysis by separate project workflow, or experimental frequency response, not asserting they were extracted from MVKView.

## Real BIN spectral checks
Implemented local offline `stage91_peaks.py`: per-channel one-second Hann-window FFT, periodogram power averaged over complete one-second segments, 1 Hz frequency grid, search near affected bands. Results: ADC1 strong 20Hz and 40Hz tones; ADC6 strong 22Hz narrow tone (21 and 23Hz side bins due to leakage); ADC3 16..40Hz much broader components, notably content near 24, 27..33, 37..39Hz. The **22 Hz tone lies near third-octave 20/25Hz boundary**. Under base-ten center 20Hz, upper border is about 22.44Hz, and 25Hz lower border about 22.28Hz if exact center labels substituted (nominal-rounded labels are not exact centers); small filter differences near 22Hz can redistribute large energy between adjacent bands. This provides a plausible physical cause for large 16/25/31.5Hz errors, NOT proof of specific original filter shape.

## Next
Evaluate actual third-octave edge definitions per manual and compare amplitude over paired bands; test base-2 vs base-10 center alternatives with no fitted gains; avoid confusing different-sessions PCAP with real BIN. All work offline, stable v0.3.40 unchanged. Raw BIN and VALUES not on GitHub.
