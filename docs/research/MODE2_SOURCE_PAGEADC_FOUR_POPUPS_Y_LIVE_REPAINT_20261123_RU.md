# MVKView 1.0.47 — восстановление четырёх pop-up PageAdc: численная Y-шкала и живой GetSignal

**Дата:** 23.11.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`. **Источник:** четыре приватных пользовательских скриншота «Временной сигнал» от 23.11.2026. Оригинальные PNG, Pascal, DFM, IDP, SQLite и реальные измерения НЕ коммитились.

## Доказательная база

Локально совместно перепроверены `Projects.7z/_Unit128.pas` и `mvkform.dfm`, `mvk_idr(1).sqlite` (quick_check=ok, SHA исходников совпал с индексом), `mvkview.idp` (хеш исходного IDR проекта). Ключевые адреса исходной программы:

- `0084AB98`: создание 14 пунктов `popGraphHScale` и 13 пунктов `popGraphVScale`, базис `GraphDefaultVScale` из текущего канала.
- `0084AF39..0084AF95`: исходные делители `008D33F4`, арифметика `GraphDefaultVScale / divisor`, `FormatSpec` и единица текущего канала из поля `[channel+8]`. Это **числовые подписи**, не строка «1/N диапазона Y».
- `0084B194`: H Tag меняет меню, вызывает `GetSignal`. `0084B1E0`: AC/AC+DC также переобрабатывает `GetSignal`.
- `0084B22C`: V Tag вызывает **только `pbAdcPaint`**, не новый `GetSignal`. `0084B2F8`: для исходного типа канала 1 — `ScrBottom=-GraphDefaultVScale/divisor`, `ScrHeight=2*GraphDefaultVScale/divisor`; исходный тип канала 2 имеет особый путь с фиксированной высотой и требует отдельного исходного типа, не угадывать.
- `0084B4AC`: `ADCGrapher.UpdateCursor` получает X мыши, а не новый приборный пакет.
- Совместное меню `popEnvelopeType` содержит 32 фильтра/две колонки 20+12; оба `bAdcEnvelopeType` и `bSpecEnvelopeType` используют один выбор. FIR только при наличии локального проверенного IDP, не подменять неизвестные коэффициенты.

## Проверенные меню со скриншотов

| Команда | Пункты |
| --- | --- |
| Filter | «Без фильтра» + 19×1/3окт + 6×1окт + 6×2окт |
| Type | AC; AC+DC |
| bAdcHScale (14) | 20с,10с,5с,2с,1с,500мс,200мс,100мс,50мс,20мс,10мс,5мс,2мс,1мс |
| bAdcVScale (13) | при источнике `GraphDefaultVScale=1000`: 1000,500,200,100,50,20,10,5,2,1,0,5,0,2,0,1 м/с2 |

На конкретных снимках пользователь выбрал **Без фильтра / AC+DC / 500 мс / 1000 м/с2**; это не трактуется как глобальный заводской default.

## Исправленный код

- `mvk_compatible/core/original_adc_view_controls.py`: исходные 13 делителей превращены в численные подписи `original_adc_vertical_physical_caption`; TSXML FRange (когда действительно предоставлен и привязан к тому же АЦП/BIN) использует source-derived `GraphDefaultVScale`; при **отсутствии** проверенного FRange — строго отдельный локальный 1/2/5 full-peak-fit с 20% запасом. Абсолютный ноль показывает читаемый локальный базис 1. Никакое приведение m/s2 не означает приборную калибровку.
- `mvk_compatible/desktop/main_window.py`: popup/кнопка/отмеченный Tag/собственно Y viewport согласованы для офлайн GetSignal. `_apply_live_wave_vscale` использует **только текущий уже полученный** source/preview/FIR буфер и `source_live_adc_vertical_view`, не вызывает `GetSignal`, не посылает TCP и не мутирует RAW. Подтверждённое Go кольцо исходного `FRange=1` и обычный calibrated-preview различаются. При Stop/ошибке/смене сессии/FIR-cancel старый вертикальный источник сбрасывается.
- Старые тесты перепроверены: `test_stage111z31bw_qt_adc_source_view.py` и `test_stage111z31bx_adc_x_frange_joint_core.py` ожидают **новую исходную численную UI-семантику**, а не исторические технические метки. `test_mode2_original_wave_menus_20261123.py` проверяет 32/2/14/13 пунктов, checked, FRange vs локальный 1/2/5, отсутствие нового GetSignal при V, live Y и отказ от stale session.
- Кодовые коммиты последовательного пакета: `08903edefb`, `9268ce63a8`, `f556c0127d`, `ead5332d8e`, `04d54588d9`, `53eb2c144b`, `7de54ef1a7`, `0b7b69b5d55`, `3de022786e6`, `80eb4513bde`, `74cefde89e`, `3b59989cd6`, `ba5fc918c69`, `5dfa7f6e1e`.

## Проверка и ограничения

- Первый Windows CI #45127150049: 2907 PASS, 1 FAIL на **устаревшем тесте**, ожидавшем строку «1/5» вместо числа. Это не дефект алгоритма получения сигнала; ожидание исправлено.
- Промежуточный Linux CI #45129079339: 2665 PASS, 1 FAIL на старом `axis_baseline_origin` после улучшения локального fallback. Проверка обновлена; действующий код не откатывался.
- Полный новый CI нужно проверять **строго по последнему кодовому SHA `5dfa7f6e1e75d940362a0f88a0cbe4b009bfe2c9`**. Ни новый PASS, ни Windows EXE нельзя объявлять до результатов.
- Тесты синтетические, без реального MVK01 и единой оригинальной Win32 сессии. Исходные GDI пиксели, `GraphDefaultVScale` x87 на всех порогах, аппаратная калибровка, 20мс UI-vs-source timing, LIVE FIR и точная физика всех source ADC channel types **не аттестованы**. Флаги 1:1 остаются false. Не смешивать разные записи BIN/TSXML/VALUES/TABLE.
- `main`, оригинальные приватные материалы и Go/Task2/WriteData/WriteValues/Stop **не изменялись** в этом пакете; выполнялись только UI/Core/тесты и документация.

**Приоритет далее:** общая парная оригинальная Win32+Go/Qt проверка на одном приборном RAW: IP → Измерить → GetSignal (включая AC/AC+DC, H/V/FIR/курсор) → GetSpectrum → WriteData/WriteValues → Stop. Новые аппаратные команды отправлять только с разрешения оператора.

## Окончательная приёмка CI и автономный EXE

**Выполнено 23.11.2026.** Для последнего **КОДОВОГО SHA `5dfa7f6e1e75d940362a0f88a0cbe4b009bfe2c9`** полный workflow [#45129335953](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45129335953) завершился **5/5 SUCCESS**: Linux Core SUCCESS, Linux Go TMVKThread RX/export SUCCESS, Windows Core+Qt SUCCESS (**2910 основных тестов PASS**, 15 skipped, Qt 59 + 50 + 194 PASS), Windows native QPA/DPI SUCCESS, PyInstaller Windows EXE SUCCESS.

- Windows ZIP `MVKViewCompatible_Stage111_Windows_Preview` — **69 535 240 байт**, [artifact 14797214167](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45129335953/artifacts/14797214167), `expires_at=2026-12-07T07:25:03Z`.
- [Проверенные скриншоты Qt при DPI100/150 artifact 14796809748](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45129335953/artifacts/14796809748).
- Два прошлых FAILED CI соответствовали устаревшим ожиданиям тестов (строки «1/5» и `axis_baseline_origin`); они исправлены и сохранены как регрессии на текущий UI, не отключены. Все проверки актуального кода зелёные.
- Данная приёмка — offline/synthetic; не является приборной Win32 original same-RX/x87, физические единицы без калибровки номинальны. `main`, source Go, приватные файлы и реальные данные не изменялись.
