# MVKView Capture Agent 0.1.0

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

The x32dbg Stage111Z31R capture scripts already in `MVK-Reader-Web` remain the
correct advanced option for original EIP/register/stack/Power/Y validation. Import
their existing *logs* through this agent after explicit operator approval.

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

- No live x32dbg register capture or automated EIP breakpoints; logs are imported
  after capture. No automatic Frida/DLL injection.
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
- No modification of the original process or Windows settings.
- No screenshot of other applications through whole-desktop fallback.
- ZIP manifest includes size and SHA256 of each evidence file.
- No publishing raw capture into repository; operator decides what to share.
- Successful tests prove the **capture tool's synthetic contract**, not MVKView
  computational equivalence or operation with a connected measurement device.