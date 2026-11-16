# Stage111Z31CV — Original IDP/DFM-to-Core/Qt Mode2 acceptance

Date: 2026-11-16. Source evidence examined **locally**:
- \`mvkview.idp\` (IDR project v3, original program 1.0.47);
- \`Projects.7z\` with 133 source-derived files, notably \`_Unit128.pas\`, \`_Unit125.pas\`, \`mvkform.dfm\`.
No vendor source, bitmap, original binary or user capture is committed.

## Original windows geometry and DPI

\`mvkform.dfm\` declares \`PixelsPerInch=96\`, \`ClientWidth=1008\`, \`ClientHeight=929\`, Tahoma \`Font.Height=-13\`. \`Pages\` main tab has logical \`TabHeight=44\`; \`PageStatus\`/ADC/Spectrum internal tab heights are \`36\`. Bottom \`pnMeasure\` is \`1008x53\` (bottom-aligned, border 6), containing \`pnMeasureControls\` \`843x41\` and five logical buttons: (6,0,160,41), (172,0,160,41), (338,0,160,41), (504,0,160,41), (670,0,160,41).

Native Windows 150% has logical-to-physical scale 1.5: client width 1512 physical px, panel height about 80 physical px, tab 66 physical px. **Qt widgets keep the original logical DFM coordinates and let Qt scale once**. No manual second scale; exact Win32 font raster parity still requires same-machine screenshot.

## Real connection lifecycle

Original \`bTaskConnectClick\` 00848E78 enters Mode2: creates 8 ADC + 2 TACH stores, shows pages and panel (00846D24..00846D84) **before** TMVKThread constructor 00846DCC. Thread constructor 008060B0, Execute 00807A98, Indy TCP/10230, connect/read timeouts 1000/5000 ms. Original has read exception branches, a wait/retry loop and a typed \`StatusIsError\`; Go R6.1 is passive and does not implement writable original commands.

## Original versus current Native error semantics

The Native R6.1 JSON includes \`seconds_since_last_packet\`, \`invalid_frames\`, \`frames_decoded\`, and ten per-channel counters for sequence discontinuities/nonfinite samples. Before CV, \`source_connection_display\` considered a "RECORDING" status with a *fresh JSON timestamp* and any prior decoded frames a good connection **even when packets had ceased for more than 4s**. This could incorrectly display a GREEN source lamp. New Core differentiates verified live frames, silence, data-integrity warnings, refused connection, stale snapshot and the export verification phase without pretending to know device \`StatusIsError\` or DSP values.

The original 5000ms TCP read timeout is NOT interchangeable with Native's 4s read-only silence warning: the two are reported as distinct provenances. Failed/malformed snapshots are rejected. All original 15 system fields remain \`—\` until actual vendor status records can be authenticated; this is not a mock system status.

## Core/Qt integration changes

- \`core/original_mode2_live_health.py\` validates and projects 8+2 channel stream data and original DPI96 geometry.
- \`core/original_connected_status.py\` requires packets newer than 4s for a green read-only indicator and preserves the ten-channel evidence in receipts.
- \`core/original_measurement_mode.py\` renders distinct silence, stream-integrity, refusal, stale and export phases.
- \`desktop/original_measure_controls_ui.py\` keeps native DFM button rectangles and attaches a no-double-scale DPI receipt while rendering correct status colors.
- \`desktop/original_shell.py\` retains current-run read-only source status across all 15 original PageStatus modes, without turning Go frame counts into vendor registers.

## Limits / next acceptance

The actual original wire command queue, rate selection from private image gvar_008D2F7C, Read/WriteData flags and source retry timing are not yet byte-for-byte reproduced. Native receiver remains read-only; full hardware integration must be tested only under the authorized operator. The public EXE is not declared device/source equivalent by these tests.
