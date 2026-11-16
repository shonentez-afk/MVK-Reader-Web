# Stage111Z31CU — Original MVKView 1.0.47 Mode2, end-to-end source examination

Date: 2026-11-16. Branch: research/stage111-mvkview-desktop-20261029.

## Scope and provenance

Examined PRIVATE operator-provided Projects.7z (decompiled Delphi units _Unit128.pas and _Unit125.pas, mvkform.dfm) and mvkview.idp offline. The original files, raw code bodies, vendor bitmap assets, device addresses, and captures remain **local**. This public document contains only a derived, limited structural map, not proprietary material. No original EXE, x32dbg, device or TCP connection was run.

This is NOT a claim of fully restored original TMVKThread or full source numerical equivalence. Qt Native R6.1 is a separately tested read-only receiver, not the writable original thread.

## Full first-click control path (source-confirmed)

1. Original bTaskConnectClick at 00848E78 invokes common mode dispatcher 00846AD4 with integer Mode=2.
2. The dispatcher first handles calibration-in-progress and prior mode teardown. Pressing the same Mode2 command again invokes the mode reset at 00847040; no second device session is created.
3. Mode2 creates TEN TMvkChannelStorage instances, each using logical capacity 0x200000: eight ADC (indices 0..7) and two tachometer channels (8..9). It initializes two sets of storage/calculation parameters for each.
4. It prepares the IP field and recording directory; makes PageStatus, PageAdc, PageSpectrum, PageFile visible along with PageStart. PageCalib visibility depends on FactoryMode. It makes pnMeasure visible BEFORE making a socket connection.
5. It calls the source UI initialization 00845EE4; constructs TMVKThread at 00846DCC/00846DD1 with Task=2, language, storage path and device IP. This is not just a page switch.
6. It invokes mRate1Click for the initial source rate item, selects PageStatus, changes the main Measurement caption to the disconnect label and enables tmInterfaceUpdate.
7. The source timer has 20ms interval (tmInterfaceUpdateTimer 0084F7C8 -> 00847248). The dispatcher refreshes only the currently selected PageConfig, PageStatus, PageAdc, PageSpectrum, PageFile or PageCalib, plus the global pnMeasure controls. Another timer tmConfigResult has 200ms interval (not a replacement for the main update).
8. On explicit stop/reset, 00847040 disables the timer; for Mode2 terminates, waits for and frees the source thread, hides the four live-only pages and the bottom panel, resets to PageStart and disposes original storages. A compatible Native receiver instead uses its existing graceful stop protocol and does not kill a process.

Original clicked Mode2 visible tabs=5 does NOT mean physical TCP connected. Source 00846D24..00846D84 precedes TMVKThread.Create.

## Thread/protocol path

- TMVKThread constructor 008060B0: allocates two memory streams and a command queue, stores IP/output path, initializes Source Status/StatusIsError, sample-rate field, FreezeUpdate, WriteData, WriteValues flags and file stages. Its default sample-rate member is source code 0x309; this is NOT verified sample Hertz. The source menu constructs FIVE items from a separate static rate array. Do not invent the item Hz values.
- Execute at 00807A98: uses Indy TIdTCPClient with port 10230, connect timeout 1000ms and read timeout 5000ms. It sets source thrConnecting and thrConnected statuses and processes a continuous framed stream while not terminated.
- Framing path 00807F74 onward reads a two-word header and validates length/word alignment. Source branches handle ADC/tacho blocks (ten indexed channels), parameter/control/status frames, command replies and unknown packets. There is bounded channel allocation, rate matching, display freeze handling, storage ProcessBufferChunk and selected channel-file writes.
- A separate background processing thread at _Unit128 0084FA6C dispatches TMvkChannelStorage.GetSignal and GetSpectrum and synchronizes finished UI updates; these are not just draw calls.
- QueueCommand at 00809330 stores the original pending (command, address, data); SetRate at 00809400 changes the source rate and queues a command on change. The original Mode2 path can therefore send application-level WRITE bytes. The Native R6.1 read-only transport MUST NOT emulate them without an explicit verified wire contract and safety gate.
- The Source PageAdc/Spectrum/Status/File/Calib and bottom controls are refreshed by their original handlers on the main 20ms timer. The local 900ms Go status JSON polling in the compatible dialog is deliberately separate from the original GUI repaint timer.

## Bottom command behavior

| Original control | Source event | What original does | Current compatible bound |
|---|---|---|---|
| bFreezeUpdate | 0084DEA4 | Toggle TMVKThread.FreezeUpdate; affects processing of received blocks | Compatible Go only freezes PREVIEW rendering. RAW continues; **not source-equivalent** |
| bSampleRate and five-item menu | 0084DEC4 | Select source Tag; invoke TMVKThread.SetRate (queued command) | Display independently verified Fs; hardware SetRate disabled |
| bWriteTable | 0084E020 | Produce source TABLE output | Local validated offline VALUES CSV, not byte-identical source |
| bWriteAdc | 0084E914 | Set capture timestamp, collect 10 channel-check flags and toggle WriteData | Native's separate full capture; original per-channel write flag is not implemented |
| bWriteValues | 0084E988 | Set timestamp, collect spec/value checklists and toggle WriteValues | Offline validated exports only; source flag not implemented |
| bTaskConnect second click | 00846B48..00846B5C | Stop/reset Mode2 | Compatible graceful Native stop and source-tab reset |

Source flags are independent. The FreezeUpdate path can skip processing of incoming blocks; it must not be represented as exactly the same as presentation-only freeze. Neither original SetRate nor original hardware WriteData/WriteValues is proven safe for the public compatible build.

## Error handling discovered in source

TMVKThread.Execute has typed exception branches: EIdConnClosedGracefully at 008088A2, EIdReadTimeout at 008088CE, EIdConnectTimeout at 008088FA, EIdException at 00808923, generic Exception, malformed packet, command-denied reply, and source system-status error. The thread updates status/error fields, disconnects/frees the TCP client, and, in Task2, applies an internal wait/retry loop while not terminated. Source synchronization and rate/status truth must not be inferred from mere presence of visible tabs.

CURRENT limits: Native Go reports read-only transport and verified frame/channel status; it does not reproduce Delphi-specific StatusIsError transitions, automatic retry timing, writable commands or original exact error text. Unverified firmware/serial/Modbus/MD5/system cells remain unknown, never zero-filled.

## Core+Qt changes in this stage

A new pure Core source contract centralizes entry addresses, stage timings, 8+2 channel count, original error taxonomy and per-control semantics. Both operator and tests now consume the same runtime policy for panel visibility, PREVIEW pause, observed rate and permitted LOCAL offline exports. Qt remains a native operator-facing shell; no forensic panels, device commands or automatic live TCP connection were added.

## Still open for a full functional restoration

P0: obtain a byte-validated and permissioned account of original Mode2 command sequencing and reconnection behavior, without sending any command to the device during analysis. Differentially check command replies and live fields against existing local evidence only. 
P1: rebuild original source PageStatus controls/system fields and live PageAdc/PageSpectrum/PageFile behavior together with the per-channel Core processing. Same-window and same-data parity remains unproven.
P2: full source-equivalent FreezeUpdate, 5 verified rate values and SetRate, WriteData/WriteValues selection and file output, stopped/partial data handling, all 10 channel stores, failure/retry tests. Any device writes require separately verified command contract and operator authorization.
P3: same-session hardware acceptance for the integrated Qt+Native implementation, only in an operator-approved maintenance window. Do not claim GO Live R6.1 tests prove original MVKView byte-exact equivalence.
