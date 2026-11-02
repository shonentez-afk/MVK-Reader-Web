# Stage111Z.28B2A — свежие исходные контрольные регистры, без выдуманных аварий

Дата: 02.11.2026. Рабочая ветка: research/stage111-mvkview-desktop-20261029.
Проверенный исходный коммит: 27e5871129d1a4c400295605473cc327a8f0bf97.
Статус: CODE, OFFLINE CI и автономная Windows EXE ПРОВЕРЕНЫ. Реальные оригинальные зоны/пороги/PageStatus 1:1 НЕ приняты.

## 1. Что сохранено
Stage52 FRange, Stage108/109 Native R6.1 с одним receive-only TCP, Stage26B live preview, Stage27A оригинальный BIN comparator, Stage28A DSP/TACH, Stage28B1 15 режимов PageStatus, исходные FFT golden Z8/Z10 и stable main/Web не переписывались. Ни один приватный оригинальный PAS/EXE/IDP/RAW/BIN/PCAPNG не публиковался. Новых сетевых команд и новых записывающих функций не добавлено.

## 2. Правило source freshness
Оригинальный ADC base = 0x2000 + N*0x200. Контрольный слот j=0..7 начинается по base+0x130+j*0x8: Float32 текущее, UInt32 status, Float32 последнее переходное, UInt32 резерв (всего 8 слов). AlarmState и AlarmAlert использовали ТО ЖЕ raw DWORD по +0x132; преобразователи в исходные строки пока не приняты. Пороги, номер параметра и гистерезис находятся в отдельной live-конфигурации, которой в наших данных нет.
Go source/control_timeline.go отслеживает только ПОСЛЕ initial 0x4000-word snapshot отдельные регистрационные кадры с целой 8-словной записью. Фрагменты и stale first snapshot НЕ считаются текущим событием. После предыдущего VALUES tick и до текущего tick данные регистрируются с source frame index. Неконечные Float32 подавляются без нарушения старого RAW/BIN экспортера.
В существующий 19-файловый SHA-audited TIMELINE.json добавляется только необязательное поле control_status. Поля raw value, raw status UInt32/hex, last transition и reserved; source schema MVK_NATIVE_R6_CONTROL_TICK_RAW_EVIDENCE_V1, source flag POST_INITIAL_FULL_REGISTER_UPDATE_BEFORE_VALUES_TICK, zone_and_alert_text_verified=false, config_parameter_selection_verified=false.
Python core/control_status_source.py и dsp_tach_timeline.py проверяют schema/SHA, ADC1–8/slot1–8, исходный регистр, UInt32/Float32, frame boundary, non-duplicate и отсутствие ложной аттестации. В PageStatus режим1 реальные данные показываются только там, где есть такой исходный кадр: AlarmValue — Float32, AlarmState и AlarmAlert — один и тот же статус с меткой RAW. Иначе видим —, не Норма или Авария. При смене тика, архива и LIVE старые записи не передаются в новый сеанс.
ОГРАНИЧЕНИЕ: при продолжительной записи и многочисленных обновлениях control_status uncompressed TIMELINE может вырасти за текущий лимит reader 4 MiB; long-run/streaming Stage32 остаётся OPEN.

## 3. Достоверный CI
[GitHub Actions #41405380739](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41405380739) — все три задания SUCCESS.
- Linux Offline Core: 1031 passed, 3 skipped, 30 subtests.
- Windows Offline Core: 1032 passed, 2 skipped, 30 subtests.
- Windows Qt: 49 passed, включая fresh RAW state+alert, очистку предыдущего тика/LIVE.
- Go Native R6.1 test/vet/Windows build PASS; проверка полного блока против initial snapshot, фрагмента и NaN PASS.
- PyInstaller one-file Qt + embedded Go, PE/source BUILD_INFO/SHA256 PASS.
- [Windows Artifact ID 13123801232](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41405380739/artifacts/13123801232), ZIP 68 533 443 bytes, expired=false на дату отчёта.
- EXE SHA256: 9ee15d1af865888d6dcbb7bd63adf0f6596ca766c3fbf91aa09ee9c731c76590
- Artifact ZIP SHA256: 68ba32625a55bf48640e0af0cdd12cb03c3c03b17149f310d18119e0bb688d42
- Tested source commit: 27e5871129d1a4c400295605473cc327a8f0bf97. Позднейшие docs-only коммиты не означают новую программу.

## 4. OPEN — не выдавать за полное восстановление
Stage28B2A code/CI CLOSED. Реальная same-run конфигурация, число параметра 1..144, пороги yellow/red, delays/hysteresis, 11 текстов зон и 3 текста событий, PageStatus pixel/runtime, исходный TACH Hz→RPM/пульсы на оборот, аппаратный тест новой EXE и Stage27B оригинальный BIN same-run OPEN.
Далее — Stage29 GetSignal original temporal history и Stage30 спектры всех четырёх режимов, параллельно собирать оригинальные control/register эталоны. Полный спектральный gap: [Stage111Z30](STAGE111Z30_SPECTRUM_PARITY_OPEN_GATES_RU.md).