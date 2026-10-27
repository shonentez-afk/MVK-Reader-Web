# Frozen MVK-LAB-06 v3 on saved BIN and PCAPNG, 2026-10-27

## Execution and provenance
Code `tools/mvk_fixed_band_lab/instrument_reconstructed_v3.py` reuses the empirical weights fitted in user-provided `instrument_reconstruction.py` and `instrument_reconstruction_dev83_20261027.json`; it does not access MVKView targets or fit channel gain gamma. Acceleration input in m/s2. Low edge: Hann periodogram of full input 0.8/2/10–40 Hz. High region: median of nonoverlapping 2 s Hann-periodogram energies from 40 Hz through center-third octave transition. Adjacent bands and edge weights frozen at source values. NOT a fully factory-verified DSP.

Unchanged high-edge coefficients, energies (not amplitudes):
F=150: 0.3901703205/0.8797783660; 300: 0.1752015869/0.1893290471; 1000: 0.03565543195/0.3814628907; 2000: ~0/0.5331568219; 3000: **0.4053022409/0.1048719870**.

## Actual offline tests
Two physical-unit BIN, device 83:
- ADC4 file 11-18-10: 10-3000 = **4.31918246 m/s2**.
- ADC6 file 10-34-14: 10-3000 = **3.45174813 m/s2**.
These are not synchronized to an exact acquisition window of a given MVKView TABLE stamp, and must not be portrayed as paired comparisons.

Four user-supplied PCAPNG on 83/84: reconstructed TCP/10230, VAST_MVK per-channel gain, 1052-byte ADC float frames, 4700-byte calculated frames. The exact frozen v3 model was applied to each ADC per capture, then compared to the **median** 4700 RMS for the same ADC and band, NOT paired windows. **192 rows = 4 sessions x 8 channels x 6 acceleration fixed bands.**

| session | ADC1 | ADC2 | ADC3 | ADC4 | ADC5 | ADC6 | ADC7 | ADC8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| live83 10-3000 error % | +1.08 | -0.12 | +1.42 | +0.33 | -5.01 | -2.81 | +0.24 | -5.04 |
| live84 | -4.64 | +6.53 | +0.94 | -2.04 | -5.96 | **-11.62** | +0.55 | +0.26 |
| recording84 | -4.48 | +6.43 | +1.38 | +0.26 | -6.04 | **-10.09** | +1.13 | +0.06 |
| recording83 | +1.49* | -1.11 | +1.36 | -0.46 | -4.83 | -2.91 | +0.66 | -4.78 |

*Recording83 previously showed 847-byte TCP sequence loss. Its ADC1 and any other affected downstream numerical results are not acceptance evidence.

For the **three captures without this known TCP sequence gap**, median absolute error by band:
- 10-3000: 1.73%; max 11.62%.
- 10-2000: 1.43%; max 65.53%.
- 10-1000: 1.24%; max 12.65%.
- 2-1000: 1.37%; max 12.65%.
- 0.8-300: 2.18%; max 86.02%.
- 0.8-150: 2.80%; max 60.52%.

## Interpretation
The frozen reconstructed weights give promising but **not universally better** external prediction than earlier normative HP3×LP3; notably 84 ADC6 10-3000 is 10–12% low, while normative prior full-record estimate for 84 recording ADC6 was +0.54%. This prevents acceptance or silent replacement of the original normative model. Two sources of uncertainty: refit used 83 historical RunUp dataset, and comparison uses full-record spectral statistics against the median of instrument-reported frames, NOT strictly identical windows. End-to-end reconstruction of manufacturer's specific 42/43 third-octave windows/FIR remains unproven.

Next work: align timestamps/counters and compare identical windows; test fixed weights without gamma; preserve normative model as baseline. No new captures or live connections. Production 0.3.40 unchanged. Proprietary PCAPNG/BIN not committed.
