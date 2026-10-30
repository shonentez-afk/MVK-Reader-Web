# Stage111Z — first user-reported x32dbg runtime spectrum golden (2026-10-30)

Status: **USER-REPORTED ORIGINAL WINDOWS RUNTIME, NOT INDEPENDENTLY VERIFIED**. Original EXE previously matched private IDP sections (Stage111Y); no executable or user measurement data published here. Preserve main and Web v0.3.40.

The operator corrected a breakpoint typo: incorrect 00848631 versus correct 0084B631. The real pair of stop sites are 0084B631 (pre-log10) and 0084B882 (after Single store). Read-only x32dbg expressions were used; module base reported by prior Stage111Y as 00400000.

| Menu mode | Tag | Pre hex dword [ESI+62C] at 0084B631 | Post hex at 0084B882 | Post float32 |
|---|---|---|---|---:|
| Логарифмическая | 0 | 43FF4853 | 447A0000 | 1000 |
| Линейный ВУ | 1 | 43FF4853 | 447A0000 | 1000 |
| Линейный ВС | 2 | 459F8D34 | 461C4000 | 10000 |
| Линейный ВП | 3 | 47477081 | 47C35000 | 100000 |

During Tag=0 stop at 0084B631: [EBP-4] reported 00000000 (channel index 0), FRange bits from [ [ESI+21124] + 4] = 43FF4853, mode Tag from [ [ESI+5A8] + 0C] = 00000000, x87 FCW = 1372. After stop at 0084B882: FCW = 1372. FCW for Tag 1/2/3 was not individually reported. The same channel/FRange across other modes is plausible but should not be claimed as independently reread.

The four pre-log10 samples are consistent with multipliers 1,1,10,100 for Tag 0,1,2,3; this is not a boundary-condition proof or validation of FFT, Canvas, CursorString, FormatFloat or all runtime behavior. Values are copied as exact IEEE754 hex dwords supplied by the user. The approximate decimal interpretations are not golden evidence; compare raw hex. 

Next: run the existing private_x87_runtime_reference_compare.py with private, verified golden schema, compare candidate's float32 bit patterns and isolate any mismatch, then test boundaries and additional FRange values. Do not mutate Delphi original or touch a real device. No private EXE/IDP/measurement archives in GitHub.
