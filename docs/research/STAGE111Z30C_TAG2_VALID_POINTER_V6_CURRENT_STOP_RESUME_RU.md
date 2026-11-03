# Stage111Z30C — Tag2 buffer validated, V5 false reject, V6 RESUME prepared

Date: 2026-11-03. Target: original offline MVKView x32dbg; autonomous Windows Qt MVKView Compatible project; do not edit original measurement/device or Web/main/Native Go R6.1.

## What was actually observed

The operator ran `DIAG_TAG2_CURRENT_154B.txt` while x32dbg remained PAUSED at original GetSpectrum `007D154B`. The log read:

```text
MVK_TAG2_DIAG_START EIP=007D154B EBX=02A70E58 EBP=0019F07C TID=00002CE8
MVK_TAG2_DIAG_META MODE=2 N=262144 HALF=131072 FS=65536 ENV=0
MVK_TAG2_DIAG_PTR POINTER=7E510010 BYTES=524288 LAST=7E59000F
MVK_TAG2_DIAG_PAGES START_VALID=1 END_VALID=1 BASE=7E510000 SIZE=1114112
MVK_TAG2_DIAG_OK BOTH_BUFFER_ENDPOINTS_READABLE
```

V5 had stopped on `V5_START_FAIL_POWER: first byte not valid` at `cmp mem.valid($r4pwr),1`. This is a **FALSE NEGATIVE of the V5 automation check in this observed original state**, not evidence of a corrupt source buffer. Both end addresses are valid and belong to same mapped region (according to x32dbg). We cannot conclusively determine whether the original V5 transient false outcome was due to script variable evaluation, debugger timing, or x32dbg parser state; do not claim a proven exact runtime implementation bug. No Tag2 full Power/Y captured yet.

## V6 packaging (local package made for user)

Package: `MVK_STAGE111Z30C_V6_RESUME_TAG2_TAG3.zip`, exact SHA256 `594411f47832fde3c922be83586b2ed6f277013c58d8e7220830ff35013aee09`, ~10 kB. Source script `RESUME_MODE_FROM_CURRENT_154B.template.txt` SHA256 `17d6ffba27ce28a4c2831a33231828a6f83a3040ffbfd8358d7dc03ca2b451d2`, generator `Prepare-ResumeTag2Tag3.ps1` SHA256 `f47cf819ff86be76da40129a3513dba47086ac855dfa2fed2d92f7d155eb91b6`.

- Starts at CURRENT EIP `007D154B`, does NOT attempt to hit 007D154B again.
- Saves `power_before_mode.bin` from `[EBP-2C]` (N/2 × 4 bytes).
- Uses one-shot `run` to `007D17E7`, verifies original same thread, EBX, EBP, storage, N, mode, Fs, source window and FRange, then saves `power_after_mode.bin` and `display_y.bin` (each N/2 × 4 bytes).
- Uses `run` to `007D1900`, verifies same context and saves `summary_triplet.bin` (12 bytes) and `params_summary.bin` (0x3C bytes), plus `params_before.bin`, `params_after.bin` and `frange.bin`. Log completion not required for physical triplet integrity check.
- Crucial difference from V5: at each Power/Y buffer pointer, explicitly checks `mem.base(pointer)` nonzero and verifies `mem.base(last_byte)==mem.base(pointer)`; `mem.valid` readings are logged diagnostically. It does NOT simply turn off all buffer safety checks. The page check is intentionally conservative and will stop for buffers spanning different mapped regions.
- `Prepare-ResumeTag2Tag3.ps1` generates NEW UNIQUE `C:\MVK_CAPTURE\RUN_Z30C_V6_...` with two scripts, without auto-running the debuggee or overwriting old dumps.
- Offline QA: **6/6 pytest static/synthetic pass**, ZIP CRC integrity pass. Real Windows x32dbg V6 run and PowerShell 5.1 execution are **NOT YET CONFIRMED**. Numeric Tag2/Tag3 original parity remains OPEN.

## Operator instructions

Keep original x32dbg paused at `007D154B` with Tag2. Extract V6 ZIP, open PowerShell in `MVK_X32AUTO_V6_TAG2_TAG3_RESUME` and execute `powershell -NoProfile -ExecutionPolicy Bypass -File .\Prepare-ResumeTag2Tag3.ps1`. Copy generated `scriptexec "...\RESUME_TAG2_FROM_154B.txt"` into x32dbg command bar. **Do not F9 manually.** Report `MVK_CAPTURE_DONE TAG=2` or the first fail line. Check `Verify-Stage30C.py <SESSION> --tags 2`. For Tag3, first use original GUI to select mode3 and stop at `007D154B`, then run generated `RESUME_TAG3_FROM_154B.txt`. Private originals are not committed. Preserve historical Z8/Z10 and Tag1 (131072 power+Y exact; 3/3 summary).

## Repository source persistence

As of this documentation checkpoint, V6 source and package are attached to the current ChatGPT chat and **are not yet in GitHub as files**. GitHub only records SHA, exact package name, diagnosis, procedure and pointer to previous Stage30C research; do not misrepresent docs as source commit.
