# Butterworth edge test (offline)
No network, no device access, no modification of original files. Requires Python, numpy, scipy.

Windows CMD:
```cmd
python tools/adc_filter_edge_audit/check.py "C:\\private\\ADC4.bin"
python tools/adc_filter_edge_audit/check.py "C:\\private\\ADC6.bin"
```
Input: exported BIN float32 little-endian, **already in m/s²**, sample rate 65536 Hz. This uses frequency-domain single-pass Butterworth |H|² weighting of periodogram PSD, not sosfiltfilt. Do not confuse matching output with identification of MVKView's undocumented algorithm. Details in docs/STAGE13_BUTTERWORTH_EDGE_CHECK_20261027_RU.md.
