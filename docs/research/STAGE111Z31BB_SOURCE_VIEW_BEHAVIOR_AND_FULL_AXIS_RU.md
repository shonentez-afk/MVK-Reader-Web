# Stage111Z31BB — единое безопасное состояние оригинальных форм и ось 25 600 Гц

Дата: 11.11.2026. Рабочая ветка: research/stage111-mvkview-desktop-20261029.
База: Stage111Z31BA; проверенный source SHA 342c47280e899be38296f74590ba309f1962b99f, CI #42960626061 SUCCESS.

## Цель большого функционального пакета

После полного реестра 3 оригинальных DFM форм Stage111Z31BA перейти от отдельных UI-фрагментов к автономному Core и сквозному поведению безопасных функций всех семи страниц. На этом этапе реализованы source view state и источник проверенных действий; полный оригинальный функционал всех форм ещё НЕ реализован и не заявлен.

## 1. Исправлено установленное оригинальным IDR расхождение спектра

Оригинальный скриншот одного Code20/LOG0 окна, предоставленный пользователем, показывает ось 0..25600 Гц, тогда как прежний Desktop показывал 0..12800 Гц, ошибочно объединяя ось горизонтального меню с концом TQGrapher Series.DataSize.

Подтверждения из приватной _Unit128.pas:
- 0084B536..0084B5CD — десять HScale-пресетов gvar_008D3428: 25600,12800,6400,3200,1600,800,400,200,100,50 Гц.
- 0084C3AC..0084C4BB — обработчик mSpecHScale1Click устанавливает Tag, FMax=full-1, PageSize=selected. Полная шкала скрывает scrollbar; для меньшей включается source-native прокрутка.
- 00848292..008482CE — независимо от горизонтального popup берётся DataSize=TRUNC(OutputLength/1.28). Для Code20 LOG0: NFFT131072, FsOut32768, df0.25 Гц, DataSize51200 => кривая до 12800 Гц, НО ось full HScale=25600 Гц.
- 0084EAF4..0084EB4F — bAnyDropDownClick нажатие main кнопки вызывает меню; не циклически меняет масштаб. Прежний Qt click-cycle заменён исходным popup.

В Core формализованы ОБА диапазона отдельно: конец кривой и конец полной горизонтальной оси. Ни один исходный Float32 бин или summary не заменён, увеличен или пересчитан. Это source-derived и операторски наблюдённое условие, но всё ещё не доказательство полной пиксельной 1:1 с работающим оригиналом.

## 2. Реализован автономный Core source view state

Модуль mvk_compatible/core/original_offline_view_state.py:

- Неизменяемый OriginalOfflineView для PageStart, PageConfig, PageStatus, PageAdc, PageSpectrum, PageFile, PageCalib.
- Контекст восьми каналов только как безопасный offline UI selector.
- 15 режимов Status из исходного контракта; 4 Tag режима спектра; 10 исходных HScale, 6 VScale, 6 NFFT меню.
- Переходы под управлением строгого allowlist: select_page, select_channel, select_status_tab, select_spectrum_mode, select_spectrum_hscale, scroll_spectrum_horizontal, select_spectrum_vscale, scroll_spectrum_vertical, select_spectrum_fft_lines.
- Source-native whole-Hz горизонтальный scroll и source range/page/position для вертикального; V меню сбрасывается на Tag0 при LOG и Tag3 при физическом режиме.
- Все некорректные, аппаратные и неразрешённые действия fail-closed. Core не содержит доступа к оборудованию и оригинальному процессу.

В desktop/original_shell.py отражаются текущая исходная страница, канал, Status tab, H/V menu и H/V прокрутка в view_state. Эта модель служит отдельным автономным контрактом для Qt и будущих клиентов, не перемещает данные FFT и не включает прибора.

В desktop/main_window.py при импорте оригинального Power/Y JSON отображается полноразмерная 25600-Гц source ось, даже если TQGrapher series корректно заканчивается 12800 Гц. Menu Tag0 получает checked, native scrollbar hidden. При выборе меньших H-масштабов и прокрутке обновляется Core. Исходная кнопка bSpecHScale main click показывает popup вместо неоригинального cycle.

## 3. Безопасный coverage контракт ВСЕХ 62 известных событий исходника

Модуль mvk_compatible/core/original_event_access_control.py принимает ранее верифицированную очищенную карту BA: 55 уникальных DFM handlers из 3 форм + 7 динамических FOnClick. У каждого события известен исходный метод VA, но это НЕ означает восстановленное runtime поведение.

Явная классификация: read-only UI события (пока только потенциально безопасные), local file действия (требуют диалога пользователя), device/configuration/calibration (запрещены по умолчанию), остальные untraced/unknown (тоже запрещены). Никакого автоматического делегирования оригинальной Delphi-кнопки в аппаратную команду. Only source-safe view transitions проходят через автономный Core; всё другое PermissionError.

## 4. Проверки

- tests/test_stage111z31bb_source_view_contract.py — 7 pages, 8 channels, 15 Status, 10 H, 6 V, 6 FFT, 4 modes, native scroll, rejection of unsupported/device actions.
- tests/test_stage111z31bb_event_coverage_and_guard.py — каждый из 55 DFM и семи dynamic handlers учтён, ни один не авторизует приборное действие.
- tests/test_stage111z31bb_qt_source_state_and_axis.py — синтетические оригинально-форматные Power/Y JSON+BIN, ось 25600 при series end12800, H menu select/scroll, untouched Float32, all seven Qt pages. Дополнительный Qt тест включён в Windows 150% CI.
- FIR/FFT/LOG/Native R6.1, original IDP/PAS/DFM/BIN/PNG и приватные данные не изменены, не переданы в репозиторий. Никаких x32dbg/F9 или original live GUI операций не было.

## 5. Что пока НЕ сделано и что дальше крупными пакетами

- Полные семантические цепочки PageFile ↔ PageAdc ↔ PageSpectrum ↔ PageStatus, включая числовые отчёты, настоящие AUX/VALUES и все оригинальные архивные форматы. Не подменять их фиктивными.
- Config/Channels/Alarms Load/Save и оригинальный редактор с read-only источником, затем отдельное согласование любых write, reset или calibration команд реальному прибору.
- TLanguage runtime переводы, оставшиеся обработчики, интеграция всей логики со всеми тремя формами.
- Прямой операторский read-only снимок двух Windows приложений BA, затем централизованная проверка безопасных сценариев, численных параметров и TCanvas/GDI UI, с явным разрешением перед активным GUI управлением оригиналом.

Цель BB — структурно и функционально корректное поведение безопасных source действий + исправленная ось спектра; НЕ полная MVKView 1:1.

CI Stage111Z31BB и номер нового EXE: PENDING до реальной проверки GitHub Actions. Предыдущая полностью принятая версия: BA source SHA 342c47280e899be38296f74590ba309f1962b99f, #42960626061.
