# Stage 74 — potential false-success indication after config upload

Offline IDR verification: 20/20 static instruction anchors, original `_Unit125.pas` and `_Unit128.pas`. `bConfigUploadClick` waits with `TThread.WaitFor`, hides progress, displays `TMVKThread.Status` then calls `TWindowMan.SpawnError` only if `StatusIsError` is true.

`TMVKThread.Execute` catches EIdConnClosedGracefully, EIdReadTimeout, EIdConnectTimeout, EIdException and Exception and maps their messages to the common helper at 0x008092A4. **At this helper, when `Stage==2`, code jumps past assigning `StatusIsError=1` and error status.** Since Stage=2 is set after transmitting config, flash-save and restart instructions, but before positive ACK 0x10FF0 is received, a timeout/denial/connection-close during Stage=2 can potentially fail to flag an error in the UI. Denial code 0x10FFF raises an exception, but also reaches exception-handling logic.

Static evidence of a **potential UI correctness bug**, not a measured firmware failure. The original executable has not been executed in a mock environment for this case. Do not treat write-complete or normal thread termination as successful device acknowledgement. Suggested read-only decoder metadata: `sent`, `ack_received`, `ack_type`, `timeout`, `error`.

Full local package: MVKVIEW_STAGE74_UPLOAD_ERROR_HANDLING_20261028.zip, containing REPORT_RU.md, verify_stage74.py, TEST_RESULTS.txt. No equipment accessed, stable v0.3.40 unchanged. Next Stage75: inspect 0x008493FC and post-WaitFor UI status presentation.