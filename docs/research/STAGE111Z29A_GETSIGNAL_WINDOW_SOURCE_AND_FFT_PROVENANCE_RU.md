# Stage111Z.29A — original GetSignal latest/sequential и SHA входного FFT-окна

Дата 02.11.2026. Ветка research/stage111-mvkview-desktop-20261029.
Проверенный source commit: 524cf7a0c1d4f242c339c7556fb41e957a02031b.
**CODE + SYNTHETIC CI + Windows one-file VERIFIED. Реальная original same-run численная и pixel/UI паритетная приёмка НЕ завершена.**

## 1. Проверка оригинальных файлов (локальная, приватная)

Проверены _Unit115.pas и _Unit128.pas из предоставленного Projects.7z. 12/12 выбранных адресных source-якорей подтвердились. Оригинальные PAS/DFM/IDP, захваты и пользовательские RAW/BIN не публиковались в GitHub. Извлечённые временные файлы удалены. Исходные Projects.7z/mvkview.idp оставлены неизменными.

| Исходная точка | Проверенная семантика |
|---|---|
| _Unit115:007D1A80…1ADF | InitParams: NoDC=true, sequential flag +0x14=false, availability flag +0x15=true, исходная позиция FRxPos |
| 007D1998…1A06 | CheckDataAvailability для sequential: требуемая длина от начальной позиции, ошибка Buffer overflow due to insufficient processing speed при отставании свыше capacity |
| 007D0C5E…0C86 | sequential использует end=start+OutputLength; latest использует end=FRxPos |
| 007D0CD6 / 007D2228…233D | Float32-кольцо по маске FBufferMask; при неполной истории возможен нулевой префикс в ОРИГИНАЛЬНОМ LIVE storage |
| 007D0CF0 / 007D2344…2396 | Float32-накопление и вычитание DC при NoDC или огибающей |
| 007D0DEC / 007D0DDB…0E28 | Output[N-1-i] (обратный порядок) и отдельная оценка СКЗ через double-аккумулятор с конечной Float32 записью |
| _Unit128:00847F54…7F6C | исходная вкладка AC/AC+DC устанавливает NoDC с учётом типа данных АЦП |

Наш источник-кандидат сознательно строже в одном краевом случае: sequential start до FValidPos отклоняется как перезаписанная история даже если Delphi guard ещё не сработал. ЭТО БЕЗОПАСНЫЙ ФИЛЬТР, НЕ утверждение exact runtime parity.

## 2. Программная реализация (численная FFT не менялась)

- core/getsignal_source_window.py: latest vs sequential, completed vs not-yet-ready, переполнение/rewind, корректное UInt64 ring modulo, zero-prefix только для оригинальной live-модели; никаких нулей в неполный архивный BIN.
- core/getsignal_input_evidence.py: исходный SHA256 последовательности Little Endian Float32 до DC/Hann, номер АЦП, заявленный RAW-session SHA, абсолютные sample bounds, sample rate, явно неподтверждённая оригинальная ring/Win32 связь. Сравнение разных каналов/сеансов запрещено даже при одинаковом синусе.
- core/offline_export.py: GetSignal и GetSpectrum на одной завершённой Native/проверенной BIN-сессии получают идентичный input_source_window при совпадении исходных samples; это НЕ равенство выходных обработанных массивов. Дополнительно возвращаются end_s и признак усечения waveform окна концом архива.
- core/native_r6_live_preview.py: абсолютные ADC sample indices и SHA привязаны к текущему 8192-sample provisional окну из одного Go Native spool, без второго TCP и без повторной калибровки.
- private_getsignal_original_pair_compare.py: read-only Python CLI для конкретного операторского оригинального выходного массива GetSignal (в ОБРАТНОМ порядке), сравнение с явным Native ZIP/ADC/first_sample/N/mode AC или AC+DC. Отчёт: only aggregate Float32 exact/ULP count + SHA и не содержит путей/значений; настоящий same-run и FRange остаются UNAUTHENTICATED.
- Синтетические тесты: test_stage111z29a_getsignal_source_windows.py, test_stage111z29a_live_absolute_sample_windows.py, test_stage111z29a_original_getsignal_private_compare.py. Отдельные тесты wrong ADC/session/start/mode, оригинальный reversed output, all-zero/NaN/ref tamper/symlinks/UInt64 history.

## 3. Приёмка

[GitHub Actions #41408120811](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41408120811) — ВСЕ 3 JOB SUCCESS; tested SHA 524cf7a0c1d4f242c339c7556fb41e957a02031b.
- Linux Offline Core: 1067 passed, 3 skipped, 30 subtests.
- Windows Offline Core: 1068 passed, 2 skipped, 30 subtests.
- Windows Qt: 49 passed.
- Native Go R6.1 test/vet/Windows build PASS; прежние RAW/BIN/TSXML и TCP-10230 не менялись.
- PyInstaller Windows onefile Qt+embedded Go, PE/header/build manifest/SHA256 PASS.
- [Windows Artifact 13123989621](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41408120811/artifacts/13123989621), ZIP 68 475 394 bytes, expired=false на дату отчёта.
- EXE SHA256: f836dc539bda5a032a5a1348601505df692845ae1b51d96b64cc45efaf5f9ce4
- GitHub artifact ZIP SHA256: 7f6d3ecfa0e74ba24254945d41c5df272d9758b650922aed615e02a8df3f39f2
- Последующие docs-only коммиты не изменяют эту проверенную EXE.

## 4. Оригинальный GetSignal в x32dbg: только локальная проверка

Для последующей аттестации требуется операторский оригинальный GetSignal return Float32 array, НЕ before_fft.bin. В source _Unit115 точка 007D0E49 находится после успешного заполнения буфера, перед выходом; до установки breakpoint необходимо проверить, что реальная версия/VA совпадает. На этой точке в исходном коде Params находится в EBX, [EBX+0x00] — указатель возвращённого буфера, [EBX+0x28] — OutputLength, байт [EBX+0x0C] — NoDC. Измерение нужно сопроводить same-run BIN/TSXML и точными ADC/sample index/N/режимом. Приватные значения/дампы не помещать в публичный GitHub.

Локальный вызов: python -m mvk_compatible.private_getsignal_original_pair_compare --help

Даже при 100% exact words компаратор возвращает original_same_run_identity_authenticated=false, пока не подтверждены аппаратный источник, FRange и временная позиция оригинального кольца. Не приравнивать синтетический CI к оригинальной численной сверке.

## 5. Что ещё нужно

**Stage29A SOURCE+CODE+OFFLINE CI CLOSED, REAL RUNTIME PARITY OPEN**. Далее Stage29B — настоящий original GetSignal return same-run BIN, правильный end/ring cursor, сравнение ф32; Stage29C — оригинальная FIR/огибающая; Stage30 — четыре GetSpectrum режима с полным real golden, Cursor/Copy/Save и графическим совпадением; Stage26C — длинный live FFT 65536/262144 после RAM/CPU safety gate. Не переписывать Stage111Z8 (131072/131072 original power) и Z10 (3/3 Tag0 summary), Stage52 FRange и Native R6.1. [Спектральные критерии S01–S10](STAGE111Z30_SPECTRUM_PARITY_OPEN_GATES_RU.md).