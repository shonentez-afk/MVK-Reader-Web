# Offline audit of captured MVK01 RAW files

This tool never opens sockets or contacts devices. It scans block markers, checks the 1052-byte block length, counts ADC 1–8 frames and calculates the deltas of the per-channel sample counter. A normal next counter delta is **256**, not 1.

Run from Windows CMD:

```cmd
py -3 audit_raw.py "C:\private\capture.raw" --out "C:\private\audit.json"
```

The capture stays on the local PC; **do not commit industrial RAW, PCAPNG or report containing internal paths/IPs**. Checksum is used to identify the source without uploading it.

**Interpretation limits:** a valid 1052-byte block contains 256 float32 samples starting at frame offset +28, channel ID at +20, counter at +12. Intermediate non-1052-byte spaces can be other frame types. The scan is not a full decoder of auxiliary messages and does not prove sample plausibility, timestamps, calibration or physical signal quality. A normal per-channel counter only establishes no detected missing sample indices in the observed stream.

Network transport is not exercised, nor is Reader Web started.
