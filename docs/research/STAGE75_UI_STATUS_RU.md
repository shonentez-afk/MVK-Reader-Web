# Stage 75 — UI status after configuration upload

2026-10-28; static inspection of original IDR `_Unit128.pas`, `_Unit125.pas`. Offline test: **19/19 static instruction anchors PASS**.

After `TThread.WaitFor` at 0x0084A7E6 and `HideWait`, the UI takes `TMVKThread.Status` and calls `0x008493FC` (0x0084A80B). This routine sets `lbConfigResult` text, changes the label font to system color `0xFF000008`, resets label `Tag=0`, makes the label visible and enables `tmConfigResult`. It does **not** evaluate success/failure.

`tmConfigResultTimer` at 0x00849440 increments Tag and hides the label/disables the timer when Tag reaches 32. In between it interpolates label font color toward the background of `pnConfig`. Timer interval is not known from this routine; 32 ticks **must not** be described as 32 seconds.

After showing the label, UI tests `TMVKThread.StatusIsError` at 0x0084A819; if true, `errConfigUploadError` is localized, concatenated with Status, and passed to `SpawnError` at 0x0084A868.

Potential bug from Stage74: common worker exception handler `0x008092A4` suppresses StatusIsError/Status updates at Stage=2 (after send, before positive ACK). Thus the UI can fail to flag some post-send failures, but **this has not been dynamically reproduced**. The `bConfigUploadClick` GUI additionally has an exception handler that calls SpawnError independently, so it is incorrect to claim that ALL failures are hidden.

Original local evidence: `MVKVIEW_STAGE75_UI_STATUS_20261028.zip` with `REPORT_RU.md`, `verify_stage75.py`, `TEST_RESULTS.txt`. No network/device interactions; stable v0.3.40 unchanged.

Next Stage76: identify initial Status strings, success message assignment and precise worker outcomes in task 3–5.
