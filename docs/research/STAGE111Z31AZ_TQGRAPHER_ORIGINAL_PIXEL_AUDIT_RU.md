# Stage111Z31AZ — контролируемая локальная проверка пикселей оригинального TQGrapher

Дата: 11.11.2026. Ветка `research/stage111-mvkview-desktop-20261029`.
База: Stage111Z31AY source `5f8dc3b855725a2432e7d96504d3b4185ae49b16`, GitHub Actions #42952035819 PASS.

## Результат повторного анализа приватных источников

На локальных приватных `Projects.7z` → `mvkform.dfm` и `_Unit115.pas` подтверждены **проектные** (не runtime) параметры графика:

| Элемент | DFM размер / параметр |
|---|---|
| `pnSpecGraph` | left=181, top=6, 807×756, BorderWidth=8 |
| `pbSpectrum` | внутри панели left=8, top=32, **767×716**, Align=alClient |
| `pnSpecGraphTop` | top=8, height=24 |
| `pnSpecGraphRight` | left=775, width=24 |
| `sbSpecHScroll` | DFM left=24, width=553, height=24, hidden on startup |
| `sbSpecVScroll` | DFM width=24, height=400, hidden on startup |
| Font | Tahoma, Font.Height=-13, PixelsPerInch=96 |

`_Unit115` at 007CACEE..007CACF9 copies the **ACTUAL caller TCanvas.Font** into the offscreen bitmap before TextOut. Real runtime text metrics, physical device-pixel size and DPI-awareness of the original process **cannot be inferred** from 96 PPI design-time. The source PaintBox size changes with Align=alClient. Source-derived affine, cursor, software TCo2Draw, GDI candidate text already exist; do not write another FFT, another graph engine or fake pixel profile.

## Why existing comparison was insufficient

An earlier helper `core/spectrum_bitmap_diff.py` accepted two already-cropped RGBA arrays and calculated best shifts, but did not bind them to the actual `source PixelRect`, current view ranges, Fourier series fingerprint, tag, observed Qt DPR and text metrics. It could not determine whether a difference was **within the plot** or **inside axis label/margin regions**, and did not export a reproducible original-data-free review package.

This is not a declaration that original windows/screenshots have been independently verified; no original program or x32dbg is launched for this stage.

## Implemented Stage111Z31AZ components

1. `mvk_compatible/core/spectrum_graph_pixel_audit.py` — strict source manifest: required bitmap dimensions/PixelRect, screen ranges, Tag0..3, N/df/bin count, SHA256 of candidate RGBA and full Float32 series, observed Qt DPR, DFM font vs optional GDI candidate dimensions. Only scalar **whitelist** is saved; never data arrays or original paths. Original font/DPI/provenance flags remain FALSE. Full canvas vs **plot PixelRect** vs **axis/margin outside PixelRect** RGB MAE, exact-pixel counts and mismatch counts are reported separately. No automatic resizing, rejects transparent/dimension mismatches, shifted candidates are diagnostic only.
2. `mvk_compatible/desktop/source_pixel_audit_io.py` — manual, local-only Qt PNG encoder/readback and JSON serializer. Requires a user-selected existing directory and creates a *new* uniquely named local QA folder. The file `candidate_source_bitmap.png` is the **pristine** bitmap without temporary XOR; `candidate_manifest.json` contains no original EXE/IDP/PAS/BIN or private paths. PNG lossless round-trip is revalidated against the true frame.
3. `mvk_compatible/desktop/main_window.py` — one research-dock button to **explicitly** export candidate bitmap; enabled only when original Power/Y reference and all three opt-in source software overlay controls are active. Existing "Геометрия Canvas" now also shows the **actually rendered** combined canvas PixelRect/TextOut backend separately from Qt viewport candidate. Original source process is never opened.
4. `tools/research/compare_stage111z31az_spectrum_pixel_audit.py` — local CLI to load a separately manually captured **original PaintBox-only PNG**, exported candidate PNG and manifest, verify their sizes/fingerprint, compare all pixels and print aggregate report in an explicit location **outside checkout**. Even a perfect comparison leaves `independent_capture_authentication=false` and `complete_mvkview_pixel_parity_verified=false`.
5. Regression: `tests/test_stage111z31az_graph_pixel_audit_core.py` (Linux/Windows, synthetic); `tests/test_stage111z31az_qt_pixel_audit.py` (Windows and DPI150 synthetic import/export + CLI). No original private attachments committed or uploaded to CI.

## Operator workflow for real same-window acceptance (only LOCAL)

1. On the Windows operator machine, manually open original MVKView with the **same data window, channel, SpectrumMode, EnvelopeCode, HScale, VScale, FFT count and zoom**. Manual screenshot capture is the operator's choice; **do not tell GigaCode to run x32dbg, F9, original process or GUI automation without separate permission**.
2. Manually crop the original screenshot down to the precise **`pbSpectrum` TPaintBox only**, without frame/scrollbars/desktop UI, without cursor. Save as `original_spectrum_crop.png` in a PRIVATE location such as `C:\mvk_log\pixel_qa`. Do not rescale, JPEG-compress, sharpen, or apply Windows Snip upscaling.
3. Open the **same approved local Power/Y x32dbg reference** in compatible Desktop. Enable source grid + software TCo2Draw raster + source series. Match view/scale. In the **research dock**, click "Сохранить график для локальной 1:1 проверки…", select a private folder OUTSIDE GitHub. The candidate PNG and manifest are saved into a new subdirectory. If dimensions differ, the CLI will **reject** the comparison, not fabricate a 1:1.
4. From repository root with `mvk_compatible/requirements-desktop.txt` installed, run (replace full local paths):

```powershell
python tools/research/compare_stage111z31az_spectrum_pixel_audit.py --original "C:\mvk_log\pixel_qa\original_spectrum_crop.png" --candidate "C:\mvk_log\pixel_qa\MVK_SPECTRUM_PIXEL_QA_...\candidate_source_bitmap.png" --manifest "C:\mvk_log\pixel_qa\MVK_SPECTRUM_PIXEL_QA_...\candidate_manifest.json" --report "C:\mvk_log\pixel_qa\result_001.json" --operator-same-window --shift-radius 2
```

The command creates a **local aggregate JSON report**. Exit 0 = identical unshifted RGB pixels **for this specific crop only**, exit 1 = mismatch, exit 2 = input invalid/rejected. A best shift of ±1–5px must never be counted as proof; compare ***unshifted*** results. Further region differences identify whether the remaining defect is graph curve/grid or original TextOut/axes/pixel margins.

5. Do NOT upload original PNG/IDP/BIN, original process traces or the raw source-array artifact to GitHub. Record only quantitative non-sensitive conclusions in research docs after explicit permission and identity verification.

## Acceptance limitations

Existing AY numerical/cursor/source tests stay untouched; DSP FIR/FFT/LOG and Go Native recorder are not modified. No device sockets, file protocol actions, autocomparison to unspecified originals or unauthorized automation. **New feature is a reproducible, explicit, private pixel comparison workflow, not closed original Delphi 1:1 parity**. The missing hard evidence remains original runtime TCanvas Font/TextWidth/TextHeight/PPI/PaintBox rectangle and same-window comparison supplied by operator.

Stage111Z31AZ **SUCCESS**: source `38bd2458d463ca046f80b0b1f24568936c2e00fc`, [CI #42953922189](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42953922189) — все 3 jobs PASS (Linux/Windows Core, Qt DPI150 + локальный PNG/manifest/CLI, verified native Windows EXE). [Artifact #13826616593](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42953922189/artifacts/13826616593) 68 625 898 байт, expires 2026-11-25. Исходный оригинальный runtime PaintBox/same-window original PNG в CI не присутствовал и не проверялся. Config/Calib remain next AFTER graph parity.
