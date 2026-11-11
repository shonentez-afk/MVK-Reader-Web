**Stage111Z31AV окончательная CI-приёмка (2026-11-11):** [GitHub Actions #42941474687](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42941474687) — `SUCCESS` для Linux core, Windows core/Qt (включая Windows 150% scaling) и verified standalone Windows EXE. Проверенный source SHA: `6de0fd367d4a9c92b14b318139755e35c08298c9`; новый artifact `MVKViewCompatible_Stage111_Windows_Preview` **#13820637823** (68 584 192 bytes archive). Этот artifact — новая сборка; старый локальный EXE оператора `C:\mvk_log\mvkview_exe\` автоматически не заменён. Автоматический CI не означает полного исходного pixel parity всех экранов.

# Stage111Z31AV — безопасная интеграция исходного UI по IDP/DFM

**Дата:** 2026-11-11  
**Ветка:** `research/stage111-mvkview-desktop-20261029`  
**Точная проверенная исходная база:** `4e2d5bfd7628ea323d5e76001e8abbd9b0eaa5ee` (Stage111Z31AP, Windows EXE QA SUCCESS).  
**Патч GigaCode Stage111Z31AU:** 4 из 4 context hunks технически совпали с базой. **НО** в Exchange опубликован 28-байтовый пустой тест и отсутствует полноценный отчёт; его `_update_pagefile_channels` изменял глобальный ADC combobox, но не исходную PageFile. Поэтому GigaCode AU **не интегрирован целиком**: полезные части реализованы ChatGPT заново, с привязкой к реально существующим компонентам и настоящими тестами.

## Основные изменения

| Модуль | Реализовано | Источник |
|---|---|---|
| `mvk_compatible/desktop/original_shell.py` | Самостоятельная `PageStatus` как отдельный видимый QWidget в `OriginalPageBodies`, с 15 `tcStatus` режимами, исходной таблицей и предупреждениями о недоступных данных. Старые исследовательские подстраницы сохранены для совместимости, но больше не используются как видимый PageStatus | Текущий `original_pagestatus_source.py` Stage28B, IDP/DFM `PageStatus/tcStatus` |
| `original_shell.py` | `PageFile/cbFileChannels` теперь **реальный** список каналов открытого архива/группы BIN+TSXML, выбор канала меняет тот же ADC model; справа информационные сообщения об исходных данных, без вымышленных приборных записей | `PageFile`, `DirectBinSession.channel_files` и `OfflineSession` |
| `original_shell.py` | На вкладке Config прежние 48×48 кнопки-пиктограммы со слишком длинным текстом заменены текстовым fallback шириной от 112, реальные команды прибору по-прежнему disabled | `pnConfig` DFM, сообщение пользователя по 14 скриншотам |
| `mvk_compatible/desktop/main_window.py` | Window title/Application name `ТПО МВК`; `Вид → Исследование` с сохранёнными техническими панелями и необязательными research task tabs (по умолчанию скрыты) | Caption Tmvkform в DFM; runtime captions прочих элементов ещё исследуются |
| `main_window.py` | После реального успешного `open_archive` вызывается `original_shell.sync_file_session(s,channels)`; добавлен `Файл → Закрыть измерение`, который без аппаратных команд сбрасывает локальную сессию и архивные графики, очищает PageFile, сбрасывает исходные статусы; при LIVE записи выход из просмотра блокируется | `OfflineSession`, существующие ограничения `MainWindow` |
| `main_window.py` | `_refresh_source_pagestatus` синхронизирует новую видимую таблицу `PageStatus` с тем же IDR `source_pagestatus_table`, исходными `TACH_FIELDS/ALARM_FIELDS/MODE_NAMES` и `_pagestatus_snapshot` | Stage111Z28B source contract |
| `mvk_compatible/tests/test_stage111z31ao_original_qt_shell.py` | Добавлены реальные Qt интеграционные тесты отдельного PageStatus, fail-closed DSP/TACH без AUX/VALUES, PageFile после ZIP и при закрытии, выбора ADC из списка, Config кнопок и research tabs | Qt headless test suite |

### Коммиты

- `6c73d089ba811f547ab59401c0084dad190355da`: source shell, PageStatus, File, Config.
- `8dc8671ee2275a01769819f2ce6acf92082dc462`: реальная интеграция MainWindow и safe close.
- `2f87159b895bddc4be153d103c0cdbcba8a047c1` + `6de0fd367d4a9c92b14b318139755e35c08298c9`: Qt тесты.
  
**Не изменялись:** `fft_idr_candidate.py`, `envelope_idr_candidate.py`, `envelope_spectrum_idr_candidate.py`, `spectrum_display_source.py`, `spectrum_metrics_idr_candidate.py`, original numerical Code20/LOG0; `original_pagestatus_source.py` не перезаписывался и остаётся совместим с прежними Stage28B тестами.

## Приёмка и ограничения

[GitHub Actions #42941474687](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42941474687): Linux core и Windows core/Qt + scale150% **SUCCESS**, Windows EXE pending as of authoring this report. Success означает **автоматизированные исходные и headless Qt проверки**, не визуальную 1:1 оригинального Delphi и не испытание прибора.

**Важно:** задача пользователя по восстановлению **полного оригинального интерфейса по IDP** ещё продолжается. Тут закончена самостоятельная функциональная интеграция новых UI страниц; точные runtime-переводы, оригинальные иконки, весь PageConfig/Calib функционал, Source TQGrapher/scroll/cursor и неподтверждённые фильтры остаются отдельными большими функциональными блоками. Stage111Z31AM оригинальный численный bitwise паритет Code20 LOG0 относится только к одному исходному окну; это не независимая аттестация остальных режимов.

Оригинальная MVKView и x32dbg не запускались. Новых скриншотов GigaCode не требует и не делает. Пользователь уже самостоятельно передал 14 скриншотов **предыдущей** сборки; новая версия после AU ещё не прошла ручную визуальную приёмку. Оригинальные IDP, DFM, BIN и bitmap в GitHub не публиковались.
