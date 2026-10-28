# Stage 61 — independent FRange assignment in local MVKView path (2026-10-28)

IDR `_Unit128.pas`, instruction addresses `0x008464B0..0x0084655E`, 6/6 static anchors checked.

The code reads channel sensitivity from configuration offset `+0x02` and ADC calibration from system offset `0x20`, computes **ADC_calibration / sensitivity** (x87 `fdivr`), and stores it in `TMvkChannelStorage.FRange` (+4) at `0x0084655E`. If sensitivity is zero/too small it substitutes 100.0 (`0x42C80000`). Example from DefaultConfig: 5.2191/0.010194=511.9776339, only a template—not a device-specific measurement.

Manufacturer protocol 1.0.39 explicitly differentiates sensor sensitivity at `A+0x02`, ADC calibration `0x0020`, and computed multiplier `A+0x0E`. This local derivation is consistent with the physical meaning of the fields.

Stage 52 traced a **different context**: read `TMvkCellList.GetFloatByAddr(+0x0E)` and assign that result as `FRange` in the thread. These paths must be reconciled by examining Live versus Archive initialization before deciding precedence. No firmware analysis and no stable v0.3.40 changes.

Local reproducibility bundle: `MVKVIEW_STAGE61_LOCAL_GAIN_20261028.zip` with test and report.
