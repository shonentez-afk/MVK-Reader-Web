# Stage13 fixed-band lab (offline)

Experimental, NOT vendor-verified DSP. Implements Hann PSD and the
documented three-zone fixed-band energy sum with mandatory edge weights.
Missing proprietary numeric window coefficients are NOT guessed.

Requires Python, NumPy and SciPy. Run from repository root:

Windows CMD:
```cmd
set PYTHONPATH=tools\mvk_fixed_band_lab
python -m unittest discover -s tools\mvk_fixed_band_lab\tests -v
```

Linux:
```sh
PYTHONPATH=tools/mvk_fixed_band_lab python -m unittest discover -s tools/mvk_fixed_band_lab/tests -v
```

No network, no device connection, no production code modification.
FIR decimation, exact third-octave weight functions, instrument windows,
and live metadata are NOT reconstructed yet.
