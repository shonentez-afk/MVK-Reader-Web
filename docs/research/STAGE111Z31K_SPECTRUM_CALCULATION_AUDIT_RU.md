> **ИСПРАВЛЕНИЕ ИСТОРИИ ПРОЕКТА, 05.11.2026:** Прежняя версия этого отчёта ошибочно называла исходный FFT↔Power runtime golden «не закрытым». [Stage111Z8](STAGE111Z8_FIRST_NONZERO_ORIGINAL_FFT_262144_BITWISE_GOLDEN_RU.md) уже 30.10.2026 документально зафиксировал **131072/131072 bitwise Float32** для реальной operator-claimed ненулевой пары N262144: `before_fft(1).bin` SHA256 `9832b04ced202b793533823a2ec8d14c38971568c6e3cbd446eb2d7101d70d2d` и `after_power(1).bin` SHA256 `16ecc83ef511fc1809b474ec4c0dd3d8ce96321e81fd1ccad1af94e5fffa1c34`. Это ОДИН оригинальный заявленный пользователем захват, без независимой same-thread/frame аутентификации; не универсальный паритет. Исходные приватные BIN в GitHub не добавлялись. Канонический read-only компаратор уже существует: `mvk_compatible/private_getspectrum_raw_pair_compare.py`. Дополнительные Stage31K диагностические процедуры — НЕ повод повторять StageZ8.

# Stage111Z31K-CALC — аудит расчётной части СПЕКТРА MVKView

Дата: 05.11.2026. Репозиторий: `shonentez-afk/MVK-Reader-Web`, ветка `research/stage111-mvkview-desktop-20261029`. **Строго работа по СПЕКТРУ.** По решению пользователя не переключаться на временной сигнал, расчётные таблицы или восстановление семи страниц, пока спектр полностью не сравнен с оригиналом.

## Краткий ответ: расчёт спектра восстановлен НЕ полностью

| Этап вычислений | Что действительно подтверждено | Статус |
|---|---|---|
| Original GetSpectrum Power → Y, Tag0–3 | Ранее в ORIGINAL Win32 x32dbg operator capture **по 131072/131072 Float32 exact** на каждый из четырёх выбранных режимов, на данном оператором N/Fs/FRange | **CASE-SPECIFIC DATA-VERIFIED**; не для произвольных параметров |
| Итоговые Mean/PeakX/PeakY | **3/3 original Single HEX** совпали для каждого из 4 захватов; PeakX внутри данных — индекс FFT, не Гц; Tag0 график дБ не равен линейному PeakY | **CASE-SPECIFIC DATA-VERIFIED** |
| Original 262144 Hann-RMS | Original _Unit115 initialization 008C1064 источником подтверждена; 4 original runtime Single words совпадали ранее. Независимая C/x87 реконструкция по тому же 80-bit 2π и x87 CW=1372 генерирует **262144/262144 битово равных** нашей текущей таблице, SHA256 `df10f6ab747656aefaeb17dee2764dd552e80cb738a5390108b8943615398069`. От NumPy без 4 поправок отличается ровно на 4 ULP-позиции | **SOURCE-DERIVED FULL x87 REPLAY VERIFIED**; оригинальная runtime таблица целиком не прочитана |
| Pre-FFT DC mean / окно времени / FRange | Код воспроизводит последовательность Float32 и исходную структуру; конкретный original complete same-window остаётся не подтверждён | **SOURCE-MODELED, SAME-RUN OPEN** |
| Radix-2 FFT → спектральная мощность | **Stage111Z8 (30.10.2026) УЖЕ ПРИНЯТ:** original-operator `before_fft(1).bin` → `after_power(1).bin`, N=262144, **131072/131072 Float32 bitwise** на одной ненулевой заявленной оригинальной паре. NumPy DOUBLE — лишь контрольная альтернатива, совпало 733/131072. Разные N/каналы/оконные границы и независимая аутентификация сеанса остаются открыты. | **DATA-VERIFIED FOR ONE OPERATOR-CLAIMED CAPTURE; UNIVERSAL PARITY OPEN** |
| Интегрирование Tag2/Tag3 | Исходный коэффициент, двойное применение, Float32 stores восстановлены; выбранные оригинальные postmode Power проверялись на прошлых этапах, но другие Fs/N/окна — нет | **CASE-SPECIFIC** |
| Envelope/IQ/FIR | Проверенный приватный `mvkview.idp` с SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`: 10 банков по 512 Float32, все 5120 конечны. В коде имеется FIR/IQ source candidate, но exact original process same-window envelope result не подтверждён | **COEFFICIENTS VERIFIED, RUNTIME NUMERIC OPEN** |
| Калибровка и единицы | Source-derived FRange и хранение Float32 восстановлены; принадлежность BIN тому же калиброванному источнику/каналу не доказана | **OPEN** |
| Визуализация TQGrapher | Stage31I/J график, исходные координаты и исследовательский Qt TextOut есть, но original Canvas/GDI/DPI, курсор/масштаб/копирование 1:1 не аттестованы | **OPEN** |

**Итог (исправлено):** закрыть весь расчётный спектр как FULL PARITY нельзя. **НО** уже приняты реальные пользовательские данные Stage111Z8: полный N262144 FFT→Power 131072/131072 bitwise, плюс четыре режима post-FFT Power→Y и summary. Таблица Hann также независимо воспроизведена. Непроверенное — другие входные окна/N/Fs, происхождение same-run архивного диапазона, envelope runtime и точное изображение.

## Выполнено в коде Stage111Z31K

1. `mvk_compatible/core/spectrum_calculation_acceptance.py` — локальный CLI и безсетевая матрица приёмки. Он принимает **только указанные локальные** `reference.json` + SHA-checked original `Power/Y`, проверяет все битовые Y и 3 оригинальных слова summary (если имеются), отмечает покрытие 0/1/2/3, не выводит файлы, массивы, пути и не превращает synthetic replay в original attestation. Даже при 4/4 `full_mvkview_spectrum_recovered=False` пока нет exact FFT/Canvas. Для локального запуска `python -m mvk_compatible.core.spectrum_calculation_acceptance --manifest PATH_TO_TAG0_REFERENCE_JSON`; `--require-four-modes` ставит ненулевой статус, если не все 4 оригинальных режима представлены с summary HEX.
2. `core/original_spectrum_independent_check.py::compare_source_idr_fft_capture_pair` — дополнительная независимая проверка **pre-FFT prepared Float32 → собственный IDR radix-2 FFT → Power N/2** против исходного локального Power, как отличных от `source_derived_mode_display`. Показывает exact-bin count, долю битового совпадения, ошибки распределения, пик и энергию. Нельзя передать буфер другой стадии молча: функция требует два явных флага для стадии после DC/FIR и до mode/low-bin adjustment. Стадия Stage111Z8 уже имеет реальный operator-claimed original `before_fft(1)`/`after_power(1)` с совпадением 131072/131072; эта новая функция — **не основной компаратор и не повторная приёмка старой пары**. В текущей среде оригинальные файлы недоступны, тестовые пары нового инструмента CI — только синтетика.
3. `tools/research/hann_x87_reference_stage111z31k.c` — открытая независимая минимальная C/x87 реализация математической таблицы Hann из исходных формул, без приватных PAS/IDP/RAW. Локально проверен полный SHA (CW=0x1372 и 0x037f дают одинаковый digest); 4 операторских исходных слова совпали.
4. Тесты `test_stage111z31k_spectrum_calculation_acceptance.py`, `test_stage111z31k_original_fft_power_candidate.py`, `test_stage111z31k_hann_x87_source_digest.py`: полный source SHA Hann, multi-N stride, безопасность копий, оригинальные ограничения по стадиям, fail-closed при неверных мощностях/summary, отказ от ложного универсального оригинального паритета.
5. Никаких изменений формул GetSpectrum/FFT, checked original Golden, Go Native R6.1 или Web/main. Оригинальный `Projects.7z` и `mvkview.idp` просмотрены ТОЛЬКО локально, не загружались в GitHub/CI.

## CI + Windows EXE

Последний протестированный код SHA `ecb657c8b14d19a7947935e7f88cea56a45467a9`.

[GitHub Actions #41980082545](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41980082545): **ALL 3/3 SUCCESS**.
- Linux Core **1408 PASS /44 SKIP /1 warning /30 subtests**.
- Windows Core **1448 PASS /4 SKIP /1 warning /30 subtests**.
- Windows ordinary Qt **49 PASS**, Windows effective DPR=1.5 Qt **37 PASS**.
- Go Native R6.1 regression/build PASS, independent EXE PE/SHA/manifest copy-reverification PASS.

[Windows EXE artifact #13393757593](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41980082545/artifacts/13393757593): ZIP **68 548 333 bytes**, ZIP SHA256 `f421d4f060e8a77d4f97426201a39cd641fb85db5dda2806dbdbd35baca71710`, embedded `MVKViewCompatible_Stage111_PREVIEW.exe` SHA256 `69a3734d0bcda3266bcf8620e1b56464899d8e79a70fa1576ae5b3e3fb553408`, expires **19 ноября 2026**. CLI QA в репозитории; **не утверждать, что новые необязательные audit-модули автоматически вошли в PyInstaller EXE без проверки импортов**.

## Что делать дальше — исключительно СПЕКТР

**Stage111Z31L-CALC (исправление):** **не повторять** реальный N262144 `before_fft(1)`→`after_power(1)` из Stage111Z8 — точное 131072/131072 уже документально принято. Новые проверки — независимый источник-ориентированный x87 oracle для разных синтетических N и затем **новые** реальные окна/N/Fs/каналы, если доступны. При недоступности старых оригинальных бинарных файлов не утверждать, будто они заново проверены в этой среде. После этого перейти к незакрытому оригинальному GDI/DPI/Canvas и envelope в пределах спектра.

После расчётных ворот **вернуться к Stage111Z31K графической части**: original runtime TCanvas.Font/PPI/PaintBox/GDI + pixel diff одной и той же Tag0 кривой; затем курсор/масштабы/меню, экспорт/envelope. Только после **полного спектра** — временной сигнал/GetSignal, затем расчётные данные/AUX, затем страницы.

**Не повторять** уже принятые 4×131072 PostPower→Y и 4×3 summary как новое исследование без новой причины; не размещать приватные original files в GitHub.
