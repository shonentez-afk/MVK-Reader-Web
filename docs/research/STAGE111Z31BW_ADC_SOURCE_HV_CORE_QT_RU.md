# STAGE111Z31BW — исходные H/V меню PageAdc, привязка GetSignal к Qt

Дата: 12.11.2026. **Приёмка ожидает Windows GitHub Actions.**

## Source evidence
По приватному оригиналу Projects.7z/_Unit128.pas, данным оператора из mvkview.idp:
- 14 пунктов bAdcHScale Tag 0..13, 008D33BC, в миллисекундах: 20000, 10000, 5000, 2000, 1000, 500, 200, 100, 50, 20, 10, 5, 2, 1.
- 13 пунктов bAdcVScale Tag 0..12, 008D33F4, делители: 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000.
- _Unit128 00847EAC: N=int(SelectedSampleRate * milliseconds / 1000); 0084B194 → reload/repaint; 0084B22C → repaint; 0084B2F8 uses GraphDefaultVScale / divider. Source Delphi plot orientation/codepage/GraphDefaultVScale are **not yet accepted**.
- Original DFM bAdcHScale (9,103,162,41); bAdcVScale (9,150,162,41).

## Changes in current branch
New autonomous \`core/original_adc_view_controls.py\` validates the current BIN/ZIP selected SHA, ADC, actual Fs, 14 integer-length H presets, real GetSignal length, archive truncation, full pre-LOD plain-GetSignal peak and authenticated complete post-FIR Float32 cursor buffer for all 13 V divisors.

Qt \`desktop/main_window.py\` binds BOTH original split menus to that model: changing H affects the requested actual window in Core, visible line, cursor, N and Qt caption; V affects verified visible Qt Y boundaries without touching the computed samples. For standalone BIN, Y remains explicitly uncalibrated. V numerical baseline is a **local full-window peak candidate** until original GraphDefaultVScale of this ADC/recording is attested, not an original runtime Y-axis claim. Horizontal Qt orientation is still a user-selectable source/research view, not pixel 1:1.

Pure Core regression covers numerical 65536Hz*20ms//1000=1310, truncated short archives, SHA/ADC invalidation, source Float32 post-FIR vs plotted LOD. Windows Qt regression covers all 14+13 real menus and selected actual ADC+Y ranges, plus one 7-Page/3-Form source bound path including Copy/status/time/measurement/files; all fixtures synthetic. No private files, device commands, TCP or hardware calibration included.

## Next / limits
Complete original channel type AC/AC+DC GraphDefaultVScale and source reverse X orientation with a real same-window original GetSignal Float32 source; compare FRange and physical units where authenticated. This package is still not proof of a full MVKView clone, nor original Win32 runtime display 1:1. See BW CI and later accepted handoff for actual pass/fail.
