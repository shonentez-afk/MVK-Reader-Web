# Stage111Z.18 — проект следующего этапа: Spectrum Compatibility UI (после Stage111Z.17 UI/UX audit)

**Статус:** IMPLEMENTATION PLAN, NOT YET IMPLEMENTED. Исходный аудит: [Stage111Z.17](STAGE111Z17_UI_UX_AUDIT_ORIGINAL_VS_QT_RU.md); [machine backlog](STAGE111Z17_UI_UX_AUDIT_BACKLOG.json). Рабочая ветка research/stage111-mvkview-desktop-20261029.

## Цель

Автономная Qt/PySide6 MVKView Compatible остаётся независимой Windows-программой. Оставляем функциональные/численные ядра GetSpectrum/GetSignal и проверенные исходные Source-derived golden, но **по умолчанию показываем обычный пользовательский интерфейс, похожий на оригинальную MVKView 1.0.47**. Инженерные инструменты и диагностика остаются в раскрываемом инспекторе («Исследование / Диагностика»). Новую web/server архитектуру не вводить.

## 1. Основная панель строго в исходном порядке

Из оригинального приватного mvkform.dfm (содержимое НЕ коммитить; source layout подтверждён в Stage111Z.17):

| По порядку | Original object | Qt current / planned | Ожидаемое отображение |
|---|---|---|---|
| 1 | bSpecEnvelopeType | spec_envelope_button + menu | «Без фильтра» пока фильтр не выбран; не писать «Огибающая — нет» |
| 2 | bSpecType | spec_mode presentation | «Логарифмич.» / «Линейный ВУ» / «Линейный ВС» / «Линейный ВП» |
| 3 | bSpecLines | spec_n presentation | «1/4 Гц/лин» при N=262144 Fs=65536, иначе фактическое Fs/N; NFFT указывать в tooltip/advanced |
| 4 | bSpecHScale | spec_hscale_button | актуальное имя шкалы («25600 Гц» в оригинальном reference), меню оригинальных HORIZONTAL_HZ |
| 5 | bSpecVScale | spec_vscale_button | выбранная вертикальная шкала («150 дБ» при соответствующем режиме Tag), меню source-derived original vertical presets |
| 6 | lbSpecHint | spec_hint | только компактные 2 строки частота/амплитуда курсора; если вне — «—», без provenance |
| 7 | lbSpecMean | spec_mean | СКЗ спектра, частота и амплитуда пика; с честным названием единиц и calibrated/uncalibrated state |
| 8 | bSpecCopyValue | spec_copy_button | «Копировать»; 3 колонки по оригинальным 3/4/4, исследовательские provenance и отсутствие физической калибровки не скрывать |
| 9 | bSpecSaveValue | spec_save_button | «Сохранить» или «Сохранить расчёт CSV», пока не доказан vendor file format; текст объяснения в tooltip |

Пример чисел 6,89 / 3800 / 0,7786 и курсор 3800 Гц / −55,32 дБ применять **только к принятому исходному случаю**; никогда не hardcode default values. Для исходных данных другого N/Fs/Tag UI должен отображать *их реальное* состояние.

## 2. Дополнительный инженерный инспектор

Переместить в выдвижной dock/accordion, НЕ удалять и НЕ ломать callbacks:
- spec_envelope_code и источник оригинального локального IDP/EnvelopeProfile;
- spec_n_provenance, backend switch IDR/NumPy, spec_hz developer override, spec_f_range, spec_graph_default_label, spec_input_domain;
- spec_last, spec_precise, spec_avg, кнопки «Обновить», «Сравнить FFT», «Сбросить масштаб»;
- original-copy TXT comparator, Canvas geometry, Narrowband test frequency/noise/run/result;
- source verification/предупреждения о Delta/Tag и расширенные диагностические тексты.

Главные кнопки/итоги всегда должны быть над сложными настройками. Для 1024×704 и 1920×1080 при 100/125/150% DPI пользователь должен видеть все 9 основных компонентов без горизонтального/вертикального скролла primary pane. Инспектор может иметь собственную вертикальную прокрутку, контекстные подсказки и кнопку «Закрыть».

### Важная техническая миграция

Не заменять напрямую spec_mode и spec_n обычными безсостоянийными кнопками: исходный Qt-код и многочисленные тесты вызывают currentIndex(), setCurrentIndex(), currentIndexChanged, currentText() и itemData(). Можно оставить скрытый QComboBox как единый model-state и сделать source-looking split button presenter со связанным QAction/QMenu или явно реализовать адаптер с тем же API. Нужно обеспечить двустороннее обновление: выбор кнопки меняет модель, программный выбор модели меняет текст кнопки, вызывается ровно один спектральный пересчёт когда он действительно нужен.

Нельзя допустить, чтобы простой Zoom/HScale каждый раз повторно пересчитывал исходный FFT. Желательно разделить calculate_spectrum и plot_spectrum согласно текущему cache/источнику данных; исходное NFFT и f32 мощность НЕ менять.

## 3. Пользовательские и достоверные физические единицы

Два возможных режима источника: 
- R6.1 export с проверенным EXPORT_AUDIT + AUX/VALUES provenance, где физическая калибровка всё равно должна соотноситься с каждым полем и неизвестным original FRange;
- DirectBinSession, где TSXML подтверждает только Single Float32 структуру, но НЕ исходную физическую калибровку. Никакие физические единицы «м/с²», «мм/с» и «мкм» для direct BIN нельзя выдавать за исходный приборный DSP.

В direct BIN основной summary сопровождается компактным «Исследовательский расчёт · калибровка не подтверждена»; рядом со значением в Copy/Save tooltip и CSV metadata соответствующее происхождение. Кнопку Copy не обязательно запрещать, но она не должна молча выдавать результат как аппаратно подтверждённый. Исходная строка трёх значений и исходный тип единиц не могут одновременно быть заявлены полным parity без независимой original runtime проверки.

## 4. Приёмочный checklist для разработчика

- [ ] Девять основных компонентов видны и в исходном порядке; научные поля не потеряны и доступны по «Исследование».
- [ ] Состояние всех пяти split кнопок соответствует реально выбранным параметрам и исходным единицам.
- [ ] В основной области нет Tag/IDR/FRange/протокольных адресов, кроме сознательного provenance warning.
- [ ] В 1024×704 и 1920×1080 первичные действия не обрезаются, не требуют прокрутки, сохраняют фокус и keyboard.
- [ ] При отсутствии полного FFT окна/неподтверждённой калибровке корректная ошибка и отсутствие fake DSP.
- [ ] CursorString выводит отдельно координату, summary отдельно СКЗ/пик; обработчики old spec_hint и spec_mean не потеряли source state.
- [ ] Три original Copy field golden Stage111Z.13 и спектр FFT Stage111Z.8/Z.10 не изменены; offline ZIP и direct BIN tests зелёные.
- [ ] Все GitHub Actions Linux Core, Windows Core+Qt, verified Windows EXE SUCCESS; ссылки на артефакт/sha зафиксированы в handoff.
- [ ] Только после пользовательского скриншота самой новой сборки с теми же исходными BIN, window, FRange, Tag, Fs/N, DPI проводить visual parity с original 1920×1080.

## 5. Что НЕ делать в Stage111Z.18

Не менять DSP/FFT формулы, не подгонять условные значения к одному оригинальному screenshot, не переносить аппаратную настройку МВК, не внедрять сервер или Web v0.3.40, не удалять advanced analysis, не публиковать приватные EXE/IDP/DFM/BIN/TSXML/RAW/PCAPNG/оригинальный PNG.

**Следом** Stage111Z.19: восстановить offline страницу «Задачи» и компоновку «Временной сигнал». Stage111Z.20: графические оси, GDI XOR, UI screenshot test на идентичной выборке.
