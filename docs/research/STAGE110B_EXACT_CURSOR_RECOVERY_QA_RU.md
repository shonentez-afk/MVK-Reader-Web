# Stage110B — recovery, evidence, exact cursors and QA (2026-10-29)

## Recovery
Direct GitHub branch inspection established Stage110A commit `0fb0d03fee58c5ef5cc183528886d9c6c7d5fc4c` (2026-10-29 07:42:29 UTC). **This is an EARLIER Stage110A source revision, not the final recovered archive.** Its 11 changed paths include Stage110 UI, FastAPI, test file, docs and server integration. Stage110A recovery report, apply script, and full checksum protections were NOT all present there. The supplied zip `MVK_STAGE110A_THREE_TABS_RECOVERED_SOURCE_QA_2026-10-29.zip` has 13 items with later revisions. Recovery package locally passed 13/13 module tests and 4/4 opt-in integration tests. Original full Web regression on the repository checkout is **not yet certified**.

## Actual changes Stage110B
- Restore fail-closed checksum gating for VALUES, TABLE, all eight TSXML, manifest-audit BIN checks and complete AUX4700 SHA sidecar (plus source RAW SHA comparison). Reject duplicate ZIP names and excessive sizes. BIN content is checked on requested channel.
- Fix min/max graph point times: real sample index and chronological sequence instead of a synthetic bucket-center time. This is required by ordered cursor search and makes sharp transient display meaningful.
- New `stage110b_exact_cursor.py` offline APIs: `waveform_cursor` reads precise calibrated BIN float32 sample (without reapplying K); `spectrum_cursor` computes and indexes the **undecimated** candidate local FFT bin; no device interaction, no interpretation as DSP values.
- Two opt-in research UI buttons dispatch selected plot coordinates to the precise APIs. The UI remains feature-flagged on existing server and stable main/v0.3.40 is not modified.
- New seven synthetic tests; locally 20/20 Stage110A + Stage110B Python unit tests PASSED (plus 4/4 integration patch tests on recovered package); JS parsing PASSED. These test counts are local and not a claim that GitHub CI or original Delphi parity passed.

## Original source inspected locally, NOT published
`Projects.7z` successfully unpacked privately using libarchive. `mvkform.dfm`, `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas`, and `mvkview.idp` were inspected. Original source files and production recordings remain private.
- `_Unit128.pas:0084B4A4` `pbAdcPaint` delegates to `0084B2F8`, `0084C910` `pbSpectrumPaint` delegates to `0084C770`.
- `pbAdcMouseMove:0084B4C7` and `pbSpectrumMouseMove:0084C933` both call `TQGrapher.UpdateCursor`, afterwards transfer `CursorString` into `lbAdcHint` / `lbSpecHint`.
- DFM has `pnAdcTools`, `pnSpecTools`, `pbAdc`, `pbSpectrum`, `bSpecCopyValue`, `sbSpecHScroll`, `sbSpecVScroll`. `bSpecCopyValueClick:0084BC28` copies formatted numeric values with tab separators from `SpecGrapher`; the current Web cursor copies a different string format and is NOT yet identical.
- `TMvkChannelStorage.GetSignal:007D0C30`, `GetAdjustedEnvelopeLength:007D1158` and `GetSpectrum:007D13D4` remain subjects for bitwise parity testing. Original GetSignal has output reversal and FRange/envelope branches; do not infer that a simple window-mean AC is proven equivalent. Stage81C Hann RMS and Stage81D FFT structure are credible static findings, NOT numerical parity.

## Feature matrix (current, intentionally conservative)
| Feature | State | Evidence / follow-up |
|---|---|---|
| 8 ADC files, calibrated BIN | Validated in R6.1/109 | Audit and per-channel SHA; no double gain |
| 43 third-octave RMS / 24 fixed RMS | Implemented, source `MVK_DSP` | AUX or verified VALUES, never derived FFT |
| Peak / peak-peak | Conditional full AUX | Provenance SHA required, no fake fallback |
| ADC statuses including 0x400 | Implemented | Never suppress channel errors |
| Waveform window, AC / AC+DC | Research candidate | Delphi window and ring-wrap behavior still open |
| Waveform exact sample cursor | Stage110B implemented / synthetic tests | True BIN sample and window mean; `UpdateCursor` snapping not yet reproduced |
| FFT 4 modes, Hann RMS | Research candidate | Delphi numeric normalization/open original export needed |
| Undecimated FFT-bin cursor | Stage110B implemented / synthetic tests | Avoids plot decimation; not the Delphi TQGrapher format |
| H/V scrollbar and zoom parity | Partial | DFM proves original scrollbars; not yet fully reproduced |
| Envelope/filter parity | Not confirmed | Need `GetAdjustedEnvelopeLength` tables and full assembly trace |
| Multi-client Live Native R6.1 | Not integrated | Single existing Collector only; no new connections |
| Pixel parity to original MVKView | Not confirmed | Need original UI screenshots and controlled compare |

## Safety and continuation
Stay on `research/stage41-spectrum-chain-20261028`. Never change stable v0.3.40/main before acceptance, issue no device commands, don't contact device without permission. Original DPR/DFM/IDP/PAS and industrial archives must not go to public Git history.
1. Repeat fetch of all edited GitHub paths, record branch head SHA and compare with approved patch.
2. Restore any remaining archive Stage110A edge-case tests (tampered VALUES and AUX, 8 BIN hash) in a future isolated test commit.
3. Run complete Web regression and Native R6.1 39 tests on trusted repository checkout; smoke-test explicit feature flag off/on.
4. Work through original TQGrapher rendering, exact tab-delimited clipboard, H/V zoom and scroll from `_Unit128.pas` and DFM. Keep proven/derived labels separate.
5. Obtain original MVKView FFT point export for same BIN/window before reporting numeric equivalence.
