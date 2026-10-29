# Stage111N — TQGrapher signed screen spans, Canvas/Font/DPI sweep (29.10.2026)

## Confirmed against original PRIVATE Delphi (_Unit115.pas)

- Address 007CA4F7..007CA545: signed ScrWidth is supported. ScrWidth within the tiny interval around zero is coerced to signed Single 1e-6 (negative stays negative); ScrHeight below 1e-6 is coerced to positive Single 1e-6.
- Address 007CA55D..007CA571: nonpositive Series.XScale is coerced to 1.0 before the Single itos/stoi coefficients are calculated.
- Address 007CA62F..007CA6C9: itosM/C and stoiM/C are separately stored as Single; they should not be replaced by mathematical inversion of the other pair.
- Address 007CA843..007CA870: native cursor uses index(pixel) and index(pixel+1)-1; a negative ScrWidth can make the second smaller than the first. The implementation retains that exact ordering instead of sorting the window.
- Cursor horizontal line remains raw signed peak x YScale (Stage111M). Averaged label remains separate.

These observations are *source-structure* evidence, not a real running Delphi numerical/pixel reference.

## Implemented in autonomous Windows Desktop source

- `core/tqgrapher_canvas_idr_candidate.py`: preserve negative ScrWidth, normalize near-zero signed ScrWidth and tiny/negative ScrHeight, normalize nonpositive Series.XScale, encode Single inputs, return source clamp provenance.
- `core/tqgrapher_cursor_candidate.py` and `core/tqgrapher_multiseries_idr_candidate.py`: accept signed (but nonzero) X coordinate coefficients and preserve the native index order for inverted X.
- `canvas_sweep_reference_compare.py`: private offline batch compare of up to 128 separately measured original Canvas cases, operator DPI metadata, 14 original metrics, PixelRect and affine coefficients; only differences/SHA are reported, no original values or input series are copied into output.
- New synthetic tests for reversed X, signed tiny ScrWidth, tiny ScrHeight, source Single values, independent cursor selection and one/two crosshair lines. The new sweep test is included in both Linux and Windows Core workflow commands.
- Qt plot behavior is NOT replaced by a fictitious original Delphi pixel origin; existing Qt cursor remains diagnostic and functional, without an unsupported parity claim.

## Verification and status

Base: Stage111M 368/368 Linux, 368/368 Windows Core, 14/14 Qt, Windows EXE SUCCESS on program SHA ba5efaf3e868365a58edaa828bdfbb7953f45fdd, Actions https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/40900170911.

Stage111N code commits: `3fd408b4e273bc413d8af0f06bfdd2e300ffbd7b` and workflow commit `54462f6c254bb802c603a81e0343d3344878fcf4`. **At the moment of writing this source report, new Stage111N Actions verdict and Windows EXE are NOT yet confirmed.** Never inherit Stage111M QA numbers as Stage111N results; check the completed workflow run for the latest code SHA.

No original PAS/DFM/IDP, production BIN, PCAPNG or proprietary filter coefficients were committed; work used local `Projects.7z` only. `main` and v0.3.40 are unchanged. No real instrument connections or DSP substitution.

## Still NOT proven

Original TCanvas TextWidth/TextHeight, actual Canvas pixel origin and DPI, Windows TFont/GDI metrics, original CursorString/FormatFloat on the same measurement, Delphi RTL/x87 and exact data arrays, 1/2 real series crosshair match, FFT/GetSpectrum/GetNarrowbandValue/FRange numeric parity, all three tabs, Windows visual acceptance. All tests remain synthetic until an independent original same-window capture exists.

## Next continuation (111O)

1. Confirm newest full Linux Core, Windows Core, Windows Qt and Preview EXE CI on the exact source SHA.
2. Collect private original font/text metrics for multiple DPI settings using the same source archive and native Canvas. Use `python -m mvk_compatible.canvas_sweep_reference_compare --cases C:/private/original-canvas-sweep.json --confirm-same-canvas --report-json C:/private/canvas-errors.json`.
3. Compare real one- and two-series original CursorString, CursorDrawnX/Y and complete sample arrays against the existing private cursor comparator. Do not infer original metrics from Qt.
4. Continue Delphi RTL 0042EE10 / rounding/x87, original FFT and all three UI tabs. Never enable Live or rewrite stable branches without separate permission.


## GitHub Actions validation blocked (29.10.2026 UTC)

Latest checked Stage111N Actions: https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/40905305758, source SHA `9346557611fa1361bb43885859eba39d36d5fb9c`, `conclusion=failure`. Linux offline-core and Windows desktop-windows both reported `failure` **before a runner was assigned**: `runner_id=0`, empty `runner_name` and `steps=[]`, approximately 2–3 seconds after job creation. Windows EXE was `skipped`. Earlier Stage111N runs 40905127698 and 40905080313 also reported failure. No pytest failure or successful test execution can be inferred from these runs. Diagnose runner/account/repository Actions infrastructure or limits independently, re-run when runners are available, and accept Stage111N only after observing actual Linux/Windows/Qt jobs and an EXE artifact for the exact latest source SHA. Stage111M 40900170911 remains the most recent confirmed successful code CI and is **not** a Stage111N pass.


## Проверенная CircleCI-приёмка Stage111N (29.10.2026)
Программный SHA `11f022925a407495d7bf4b3b7dcb94b21afe7ced`: [Linux Core #15](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/15) **SUCCESS**, [Windows Core/Qt #16](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/16) **SUCCESS**, [Windows EXE #17](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/17) **SUCCESS**. Предыдущие runner=0 в GitHub Actions — исторический блокер, не ошибка текущего CircleCI. Qt и Linux работают в независимых заданиях; EXE бинарную контрольную сумму отдельно ещё не скачивали. [Полный протокол](STAGE111N_CIRCLECI_ACCEPTANCE_RU.md). Синтетические тесты НЕ доказывают Delphi численную/пиксельную идентичность.
