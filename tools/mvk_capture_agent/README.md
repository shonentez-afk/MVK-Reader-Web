## 0.3.0 — Popup capture repair from real MVKView evidence (2026-11-16)

Validated against user-supplied MVK_CAPTURE_20261116T074819Z_12c686.zip (private; NOT committed):
1269 events, 23 UI snapshots, 19 PNGs. Seven native button invocations opened
Delphi popup windows, but only the first popup was imaged. Polls observed the
other popups with screenshot=False and consumed the changed UI fingerprints;
following WinEvent snapshots saw no new state and produced no PNG.

**Fixes**:
- Capture visible PID-validated top-level popup windows on poll even when the
  ordinary poll is configured not to save screenshots. One image per distinct
  UI state; no mouse movement polling screenshots.
- Exclude `SysShadow` and known invisible/infrastructure windows (the capture
  previously contained an all-black SysShadow PNG).
- Filter `OBJECT_LOCATIONCHANGE` with `OBJID_CURSOR=-9` at WinEvent callback;
  this caused 999 spurious events in the real capture.
- Enrich WinEvents with the known Win32 control caption/class from the target's
  most recent snapshot (no extra UI actions, no other process inspection).
- Add offline tests for popup-poll screenshots, shadow rejection, cursor-event
  filtering and HWND caption correlation.

Frida opt-in, PID pinning, no device commands, memory bounds and original EXE
protection are unchanged. This patch improves visual evidence capture; it does
**not** claim that it interprets all popup menu items as structured text, nor
that it independently navigates original UI. Real Windows v0.3 requires live
operator validation after synthetic CI.

---

# MVKView Capture Agent 0.3.0

A **local, target-restricted Windows observer** for the operator's original
`mvkview.exe` / Delphi `Tmvkform` window. Its purpose is to create a
reproducible evidence record for MVKView Compatible development.

## Current capabilities

- Operator-controlled Tkinter GUI: discover original window, Start, Capture Now,
  Stop, import existing x32dbg log and Export ZIP.
- Read-only Win32 tree and optional `pywinauto` UI Automation tree, including
  screen coordinates, visible/enabled status, other windows owned by the PID.
- WinEvent out-of-context observer (show/hide/focus/select/invoke/value changes).
  Hooks are PID-filtered and do **not** inject code into the original process.
- Window-specific PNG screenshots, including separately owned popup windows
  when Windows exposes them; no whole-screen fallback that could capture other apps.
- Manually enabled, bounded `ReadProcessMemory` watches: up to 16 named
  addresses, 1 MiB per watch, 2 MiB in total, read-only, little-endian deterministic
  decoding. Memory capture is **OFF by default**. No registers are obtained through
  this mechanism.
- Import existing x32dbg `.jsonl` register events or sanitized `.log/.txt`
  Stage111Z31R markers; this does NOT drive x32dbg.
- Local JSONL event log and SHA256-protected evidence ZIP. No cloud upload.
- Local MCP (stdio) interface usable by a compatible agent host. All operations
  require explicit operator approval before recording starts.

## Install and run (Windows 10/11)

1. Extract the ZIP to a **local folder**, for example `C:\MVK_TOOLS\CaptureAgent`.
2. Install official CPython **3.11 or 3.12** (with tkinter and `py` launcher).
3. In PowerShell or Command Prompt, run:
   `py -3 -m pip install -r requirements-windows.txt`
4. Open original `mvkview.exe` in your Windows desktop (with or without a
   previously saved measurement; you control the original application).
5. Double-click `run_windows.cmd`.
6. Click **Refresh MVKView windows**, choose the `Tmvkform` window, check the
   explicit authorization checkbox, then **Start capture**.
7. Interact with the original MVKView as you normally would. Use **Capture now**
   to capture a precise checkpoint; drop-down menus and changing tabs will also
   generate WinEvent events and UI captures where the OS exposes them.
8. Click **Stop**, then **Export ZIP**. The ZIP remains in your Documents folder.

By default output is written to:
`%USERPROFILE%\Documents\MVK_Research\captures\MVK_CAPTURE_<UTC>_<random>\`

The original executable, archives, `Projects.7z`, `mvkview.idp`, credentials,
private images and raw samples are NOT bundled in the distributed code.
The operator's own recordings may contain sensitive data; do not commit them
into a public GitHub repository.

## Optional, deeper read-only memory sample

Create a local `config.json` based on `config.example.json`. To enable a
4-byte floating-point watch for an *address you have verified in the current
running instance*, set:

```json
{
  "screenshot": true,
  "ui_automation": true,
  "memory_read": true,
  "save_raw_memory": false,
  "watches": [{
    "name": "verified_f32_value",
    "address": "0x02000000",
    "size": 4,
    "encoding": "f32"
  }]
}
```

`0x02000000` is an **illustrative placeholder**, NOT a valid MVKView address.
Never copy fixed data addresses from another x32dbg session: original
allocation addresses may change. Direct address watches cannot follow pointers,
and a running process might mutate the memory between reads. The read-only
capture has no snapshot atomicity guarantee and does not provide x87 registers.
Use **Capture now** after enabling the GUI check box for manual memory watches,
or `mvk_capture_snapshot(include_memory=true)` from a local MCP host.

For legacy evidence, x32dbg Z31R log import remains available. Optional
Frida tracing captures selected x86 calculation checkpoints without x32dbg.

## MCP connection (local-only)

For hosts that support MCP stdio, register the following command:

- Command: `cmd.exe`
- Args: `/d /c C:\MVK_TOOLS\CaptureAgent\run_mcp_windows.cmd`

From the host, invoke:

1. `mvk_capture_discover`
2. `mvk_capture_start` with `acknowledge_local_capture: true` and optionally
   `pid` and `config_path`.
3. `mvk_capture_snapshot` with `include_memory: false` for regular checkpoints.
4. `mvk_capture_import_debugger` for a pre-existing x32dbg log, if needed.
5. `mvk_capture_stop`, then `mvk_capture_export`.

The MCP server **does not offer click, send keys, set breakpoint, attach debugger,
write memory, connect to a physical device or upload commands**.

## Diagnostics / offline tests

```
py -3 -m capture_agent probe
py -3 -m unittest discover -v -s tests -p test_*.py
```

`probe` only identifies eligible original process windows. It does not start
recording. The synthetic tests do not require original software or hardware.

## Limitations: intentionally NOT yet implemented

- No x32dbg automation. Optional Frida hooks collect six verified checkpoints
  when separately authorized; this is NOT a complete execution trace.
- UIA may expose only a small fraction of Delphi VCL controls. Some popup menus
  may not be own-process Windows HWNDs and may be missed by target-only imaging.
- Screenshots are best-effort on the current interactive desktop; minimize/secure
  desktop, elevated process or inaccessible windows can prevent captures.
- WinEvent callbacks are observations, not a complete trace of every CPU
  instruction, registry access, file operation or network packet.
- No live Windows Original MVKView or x32dbg hardware test performed in CI;
  Windows validation must be performed by the operator.

## Security and evidence provenance

- Process name is fixed to `mvkview.exe` and root Win32 class to `Tmvkform`.
  The selected PID/HWND are rechecked continuously. On loss, recording stops.
- Default UI-only mode does not modify the original process. Optional Frida
  instrumentation temporarily changes original process RAM but not its disk image.
- No screenshot of other applications through whole-desktop fallback.
- ZIP manifest includes size and SHA256 of each evidence file.
- No publishing raw capture into repository; operator decides what to share.
- Successful tests prove the **capture tool's synthetic contract**, not MVKView
  computational equivalence or operation with a connected measurement device.

## Version 0.2 - automatic original GetSpectrum trace without x32dbg

The new **opt-in Frida mode** observes six source-verified x86 execution
checkpoints in the already-running original `mvkview.exe`, automatically.
No x32dbg, manual breakpoints, F9, register screenshots, or script execution
in a debugger are necessary.

1. Start the original MVKView **outside x32dbg** and **open a saved measurement manually**.
   Do not connect to a physical device.
2. Launch the new `MVKCaptureAgent.exe` and select its original window.
3. Tick **Automatically trace original GetSpectrum with Frida** and the
   separate **I understand Frida ...** acknowledgement. Optional:
   **Also record bounded pre-FFT/Y array candidates** (local up to 16 MiB).
4. Tick the ordinary capture consent, click **Start capture**, and check
   `frida_ready=True`. If the six original opcode signatures do not match,
   tracing fails before any inline interception is installed.
5. Open the original Spectrum tab; switch safe display modes in the original.
   The observer will automatically record checkpoint hits, x86 general-purpose
   registers, sampled 60-byte parameters, stack/storage contexts, and (if
   explicitly enabled) candidate pre-FFT / Y Float32 arrays.
6. Click **Stop** and **Export ZIP**. Keep the ZIP local and share only data
   you explicitly intend to share.

**Frida changes executable instructions in process MEMORY temporarily.** It
never modifies the original PE on disk, but instrumentation can slow down or
crash the target. Test on a saved offline measurement, and stop immediately
if the original app misbehaves. This is not a pure read-only mode.

The current six checkpoints were previously investigated using source-derived
x32dbg Z31R signatures (VA 007D14AA, 007D14B8, 007D153D, 007D154B,
007D17E7, 007D1900). The agent computes module-relative addresses and
checks all opcode signatures before installing any hook. It also validates
that the selected local original executable is PE32 x86 with ImageBase
0x00400000. The executable SHA256 is logged locally for evidence provenance.

Instrumentation is OFF by default. It is never activated by a normal UI
capture, nor by MCP without a separate explicit acknowledgement. All internal
buffers are bounded and labelled **candidate; parity unverified** until linked
to exactly the same original window, BIN, channel, mode and FFT settings.

From MCP, use `mvk_capture_start` with `acknowledge_local_capture=true`,
`auto_trace=true` and `acknowledge_instrumentation=true`; optionally use
`trace_arrays=true`. Then `mvk_capture_status`, `mvk_capture_stop`,
`mvk_capture_export`.

This release does NOT claim to capture every Delphi function or every CPU
instruction. It does not autonomously click all controls: automated, hardware-
safe UI traversal remains a separate engineering task. No device control,
no full x87 register state, and no original-Win32 1:1 parity are claimed.

The default non-intrusive mode from v0.1 remains available. The old x32dbg
import feature is optional for legacy captures and is not needed for this mode.