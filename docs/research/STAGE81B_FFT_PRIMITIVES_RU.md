# Stage 81b — FFT input, window table and frequency conversion (2026-10-28)

Source: original IDR `_Unit115.pas` extracted locally from `Projects.7z`. Static offline inspection; **16/16 markers confirmed by a locally executed script**. No instrument communication.

## Direct original-code findings
**`sub_007D1FE8` at 0x007D1FE8:** creates `TDSXFastFourier`, calls `SetNumSamples(N)`, computes `step=0x40000/N`, fills complex input with real sample multiplied by `gvar_0096DA48[i*step]` and zero imaginary component, calls `TDSXFastFourier.fft`, writes `re[i]²+im[i]²` for `i=0..N/2-1`. It outputs **power-like unnormalized squared complex magnitudes**, not final RMS amplitudes.

**Window table initialization at 0x008C1064:** builds exactly 262144 entries from trigonometric expression involving `cos(2*pi*i/262144)`, `1-cos`, and `sqrt(2)` (original x87 instructions at 0x008C107F–0x008C10BA). The table is sampled at integer step `262144/N`. This confirms a deterministic periodic cosine-derived window; **exact final expression and scaling must be verified with x87 execution**, and therefore do not call it an ordinary Hann window without qualification.

**`sub_007D2164` at 0x007D2164:** sets bin 0 to zero; for each bin `i>=1`, multiplies the squared-magnitude bin by a squared factor involving `159.154943091895` and the caller's frequency step (`0x007D217C–0x007D218C`). The caller in spectrum mode 2 applies the transform once; in mode 3 twice. This is strongly consistent with one and two integrations in frequency domain (since `159.154943...=1000/(2*pi)`), but exact units and factor orientation must still be numerically checked before claiming restored engineering values.

## Evidence and limits
16/16 structural string/address markers passed **locally** with the original PAS: seven FFT markers, four transform markers, five window markers. Script: `tools/research/stage81b_verify_fft_primitives.py`. The runtime FFT `TDSXFastFourier.fft` internals, amplitude logarithm base and dB reference, window coherent/RMS gain, edge bins, and exact units are still open. Real synchronized BIN+TSXML + MVKView spectrum export is needed for end-to-end numerical validation. Neither Stage81 nor overall reconstruction is complete.

Next Stage81c: examine initialization x87 stack carefully, reverse the FFT library method and dB helper, build deterministic synthetic fixtures for unit checks **separately from** real-measurement validation, and compare genuine archive captures. Do not modify v0.3.40 or publish original industrial data.
