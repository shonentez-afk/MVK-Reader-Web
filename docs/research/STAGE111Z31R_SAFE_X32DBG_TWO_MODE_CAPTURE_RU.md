# Stage111Z31R — один защищённый захват двух оригинальных спектров, 9 ноября 2026

**Приоритет только СПЕКТР.** Новые оригинальные данные пока отсутствуют. Текущая цель — связать original full Y с конкретным исходным Float32-окном одного архива и отдельно получить трассу FIR/IQ, не возвращаясь к принятым FFT, FRange, Hann, Tag0–3 Power→Y, коэффициентам FIR и Qt plotting.

## Исходный комплект (сохранён в рабочей ветке)

[Исходники инструмента](../../tools/research/stage111z31r_x32dbg_two_mode_capture/README_RU.md). ZIP для оператора: `MVK_STAGE111Z31R_TWO_MODE_X32DBG_CAPTURE.zip`, 21 290 байт, SHA256 `bcd05422fe5718439cce2523dfe3fd2f7dc7a717828d7885d23c961ce5ce0e71`. ZIP сгенерирован и проверен локально, но **не является GitHub Actions артефактом**. Содержимое без оригинального EXE/IDP/PAS/BIN/прошивки/сигнала: `Prepare-Capture.cmd`, `Prepare-Capture.ps1`, `CHECK_READY.template.txt`, `CAPTURE_BOTH.template.txt`, `Verify-Capture.py`, подробный `README_RU.md`, 14 синтетических тестов, SHA manifest.

**CI:** [run #42547430857](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42547430857) **2/2 SUCCESS**:
- Linux Python 3.11: `Ran 14 tests / OK`;
- Windows: `Ran 14 tests / OK`, плюс **физический smoke PowerShell 5.1** (`Prepare-Capture.ps1 -Adc 4 -N 4096 -SpectrumType 2`, создание `CAPTURE_BOTH.txt`/`CHECK_READY.txt`/`capture_config.json`, проверка отсутствия placeholder и основных маркеров).
- Ранее локально также сверены 6/6 коротких сигнатур указанного оригинального IDP в контрольных точках; это source evidence, **не Windows x32dbg runtime-тест**.

## Что сохраняет один x32dbg script

Режим A: SpectrumType 2 («Линейный ВС»), EnvelopeCode 0 («Без фильтра»), ADC 4, исходная Fs=65536. Режим B: **тот же архив/канал/режим**, EnvelopeCode 20 (FIR/IQ), выходная Fs=32768; N=262144 по умолчанию или явно выбранный при подготовке более короткий поддерживаемый N. После успешного прохода A пользователь только включает фильтр 20 на том же оригинальном окне, script продолжает B. Оба результата могут быть физически валидны, **но НЕ same-window**, если оригинал выбирает иную конечную позицию/исходные Float32.

Исходные EIP:
- `007D14AA`: исходный нормализованный Float32 до удаления DC, с `storage.bin` и исходной парой ring head/tail (учтено wrap); сохраняет Params и FRange
- `007D14B8`: те же отсчёты после DC до FIR
- `007D153D`: оригинальный буфер preFFT после FIR (или DC при коде0)
- `007D154B`: power pre-mode
- `007D17E7`: full power-after-mode + full displayed Y
- `007D1900`: physical triplet, final Params, snapshot журнал

Скрипт записывает оригинальные Params по 60 байт на каждой контрольной точке, FRange Float32 4 байта, N/2 Float32 Power/Y, сырой исходный вход (и отдельно кольцо), SHA/структурный отчёт `Verify-Capture.py`; размеры проверяются и недостаточная история не дополняется нулями.

## Устранённые потенциальные причины прежних провалов V2–V6

1. **Startup/System/Entry breakpoint:** prep не возобновляет процесс, `CHECK_READY` до живого GUI проверяет 6 адресных opcode signature, не пишет измерений.
2. **V5 `mem.valid` дал ложный отказ:** вместо единственного `mem.valid(pointer)` консервативно проверяется наличие `mem.base(start)`, `mem.base(last)`, непрерывность региона и точный размер памяти. Ошибка — **FAIL CLOSED**, не игнорировать.
3. **V6 начинал у pre-mode Power:** новый захват начинается раньше, с исходного original кольца/preDC; не присваивать старому `before_fft` статус исходного ADC raw.
4. **EBX/EBP, TID, storage, window drift:** проверяются на последовательных остановках; при изменении отказываемся от утверждения same-run. Pass A и Pass B имеют независимые snapshots; между проходами сравниваются original ring end и полный общий хвост нормализованных Float32.
5. **Tag2/Tag3 старые совпадающие Power имели разные window positions:** равенства Power/Y недостаточно для одного входного окна; новый валидатор не выдаёт ложный PASS, если end или tail различаются.
6. **Старые capture.log были только redirect:** физические Params/12-byte triplet не зависят от завершённости текста лога. В логах метка `Z31R_BOTH_COMPLETE` выводится только в конце.
7. Уникальные каталоги защищают предыдущие файлы, никаких записей по адресу прибора, patch/modify original EXE/RAM, сети либо публикации операторских исходников в GitHub.

## Уточнение выбора фильтра в оригинальном GUI (09.11.2026)

`EnvelopeCode=20` — **не фильтр 20 Гц**. Исходный `_Unit128` строит меню из 32 пунктов, берёт подписи по массиву в IDP (адрес `008CD900`); под индексом 20 записано **«1окт 16 кГц»**, октавная полоса с центром 16 кГц. Для оператора: в меню огибающей вкладки «Спектр» выбрать именно этот текст. FIR I/Q stage5 имеет децимацию 2; табличная промежуточная частота 65536 Гц, выход 32768 Гц: прежняя константа `EnvelopeOutputFs=32768` в сценарии правильна. Предоставлен ZIP v1.1 `MVK_STAGE111Z31R_TWO_MODE_X32DBG_CAPTURE_v1_2.zip` SHA256 `fe189ce7020e95e8d883ab4302a6e93385e2049f83721190b3da1033cee6df28` с уточнёнными подписями и устранённой ошибкой кавычек PowerShell 5.1 из v1.1, 14/14 локальными синтетическими тестами и [CI 2/2 SUCCESS #42562385095](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42562385095); адреса и проверки не менялись. Исходные IDP/PAS/DFM в GitHub не публиковались.

## Применение

Оператор скачивает ZIP из ChatGPT, распаковывает в каталог Windows без спецсимволов и запускает `Prepare-Capture.cmd`. Затем **уже при работающем original MVKView GUI внутри x32dbg** отключает старые пользовательские breakpoint и выполняет две готовые строки `scriptexec` из `RUN_ME.txt`: сначала `CHECK_READY` (без run/savedata), затем `CAPTURE_BOTH`. Не нажимать F9 вручную при активном скрипте. При сообщении `PLAIN capture finished` подтвердить и в GUI выбрать код20; итог `Z31R_BOTH_COMPLETE`. При `FAIL_...` сохранить частичную папку, сообщить ошибку и **не обходить проверки**. Локально `py -3 Verify-Capture.py "<run-folder>"`; отправить ZIP операторского captures **только в чат, не в публичный GitHub**.

**Доказательные границы**: подготовительный PowerShell Windows CI 2/2 PASS и 14+14 tests; выполнение `scriptexec` оригинальным процессом, действенность динамических указателей, full end-to-end BIN/Y и FIR same-window **ещё не испытывались**. Отдельное сравнение исходного raw-window с сохранённым архива BIN/TSXML требуется после capture. Весь стабильный основной Desktop и Native Go не изменён; с данным коммитом новый Windows EXE не пересобирался (не нужен).

**Далее**: первый тест в x32dbg на архиве №83, ADC4; при первом исходном `Z31R_FAIL_...` исправлять конкретную операцию по snapshot/логам, а не удалять memory guards. Затем использовать `private_same_window_spectrum_compare.py` (Stage31Q) для числа побитово одинаковых Y бинов, и `private_getspectrum_prefft_envelope_compare.py` для FIR. Не подменять недостающую original window аттестацию сравнением двух синтетических архивов.
