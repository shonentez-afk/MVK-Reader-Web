# Stage111Z31BG — source GetValueText, TLanguage, WindowMan

Дата: 11.11.2026. Ветка: research/stage111-mvkview-desktop-20261029.
База BF: source SHA 10319ca736e2fd1aedf28b292a2bb6b45815c4f7; GitHub Actions #42995021324 SUCCESS (Linux Core, Windows Core/Qt DPI150, standalone Windows EXE + Native R6.1).
BG: **FULL CI PASS** для source e297e3627bf5c2893e4013583dd6603abfa2b490, GitHub Actions #42998754355 (Linux Core, Windows Core+Qt DPI150, autonomous EXE с Native R6.1). Только original Win32 paired/runtime/device parity остаётся открытым.

## 1. Приватные доказательства

Локально SHA256 Projects.7z = 3fad945b6f0bccf94a396875fc87098b214259263c8ec3178b507a1d0f6fd363.
Локально SHA256 mvkview.idp = 77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438.
Проанализированы _Unit94.pas, _Unit114.pas, _Unit115.pas, _Unit128.pas, WindowManForm.dfm. Приватные PAS/DFM/IDP/BIN/PNG не опубликованы.

## 2. GetValueText original 30-type switch

Независимое локальное извлечение из приватного _Unit115.pas: **30/30 записей switch в точности совпали** с SOURCE_DISPATCH_CASES, SHA256 30 байт кодов ветвей = d5f5b263736995b4a581557ea0d58b4c5eec3a0a311a7726b0b3f0c5edc9216f. Это source-data parity, не original runtime comparison.

Из _Unit115:007CE6E4 (таблица переходов) и _Unit114:007B2224/22E4/2390/2428/27CC/28F8/29D4/2D98 подтверждены:
- Type0: Single. _Unit114:007B1CC0/2090: NaN = NAN, +0/-0 = 0, остальные числа требуют оригинального FormatFloat/FormatSettings; кандидатное представление не заявляется оригинальным текстом.
- Type1 Int32; type2 UInt32 (Int64 overload); type3 Unix seconds -> Delphi DateTime (25569 + seconds/86400) -> вычитание bias/1440 по Windows GetTimeZoneInformation (_Unit94:0072F050/0072EFB4). Без явно заданного total Windows bias исходного процесса время UNKNOWN, не брать смещение ПК/CI.
- Type4 16 исходных байт в HEX без пробелов; type5 индексы установленных битов, разделённые запятыми, пусто = ---.
- Types 6/7/15 IPv4 по старшему к младшему байту UINT32; types 8/9/11/13/14 ANSI/NUL-terminated строки с source width, без неизвестного Unicode кодирования. Непечатный/не-ASCII байт = UNKNOWN, ConfigWifiPassword полностью маскируется.
- Types 10/29 hex uint32, type28 hex uint16, type12 hh:mm:ss из секунд; types16..23 — 4..32 LSB-first бит с пробелом после 4; types24..27 — 1..4 байта HEX с завершающим пробелом.
- Advanced type10: UInt32 + исходные Bits/BitStart + TMvkAdvancedCell source ID, при этом реальные локализованные названия неизвестны.

Новый Core: mvk_compatible/core/original_cell_source_renderer.py. Все значения из явно выбранного локального register-image, без сетевого/приборного чтения и без изменения регистров. Поля original_runtime_text_verified / original_live_device_verified всегда FALSE.

## 3. TLanguage — восстановленный контракт данных и source resource names

_Unit115:007C7CC0/7AD0/7DC4: TResourceStream RT_RCDATA=10, UTF-8 JSON array объектов, выбор по FCurrLang, перечисление language-массивов и проверка ключа id; поздний найденный ключ заменяет ранний.
_Unit128:0084411D..00844152: Localization, ExtLocalization; _Unit115:007C8D23..007C8D37: WindowManLocalization. Точный исходный язык для трёх ресурсов — ru-ru.

Новый Core: mvk_compatible/core/original_language_resource.py с ограничением размера JSON, symlink-guard, SHA256 и source-only fallback. Реальные resource JSON из оригинальной программы НЕ восстановлены и НЕ загружены; локальные файлы помечены unverified.

## 4. Третья оригинальная форма WindowManForm

Из WindowManForm.dfm: client 436x186 @96 DPI, Lbl 111,24,304,65, img 16,16,80,80, bYes/bNo/bCancel/bOk с modal results 6/7/2/1.
_Unit115:007C8B50/8B7C/8C90/8E1C/8EE4/8FB8/90E0/91C0: original SetupButtons, SetupTitle, Error, Information, UserQuery, Wait/HideWait.
Новые Core + Qt: original_windowman_source.py, original_windowman_form.py, window.original_window_man в original_shell.py; ошибка безопасного локального bConfigLoad теперь modeless WindowMan. Для Wait при отсутствии всех кнопок применена 2/3 логической высоты — кандидат, не оригинальная Win32 non-client пиксельная геометрия. Исходные image bitmaps и динамические locale JSON не встраиваются. Runtime TWindowManForm не запускалась.

Обязательные тесты: mvk_compatible/tests/test_stage111z31bg_original_cell_source_renderer.py, test_stage111z31bg_original_language_resource.py, test_stage111z31bg_windowman_source.py, test_stage111z31bg_qt_windowman_form.py. Новый Qt-тест добавлен в Windows DPI150 job. Не изменять и не переписывать принятую численную FFT/FIR/LOG цепь ради экранов.

## 5. Открыто для полного 1:1 восстановления

Оригинальный FormatFloat и точные Win32 TFormatSettings для Float32, исходный ANSI codepage и время через GetTimeZoneInformation исходной сессии; оригинальные UTF-8 JSON/иконки; проверка всех сценариев 7 страниц/3 форм и 62 handlers; полноценные форматы файлов, калибровка/генератор, реальные device-config записи и физическая верификация. Только статическое совпадение не означает функциональный Win32 parity.

Главный следующий шаг: безопасная paired original-vs-compatible Windows приёмка на одном файле с existing tools/research/compare_running_mvkview_windows.py и summarize_private_mvkview_parity.py. Пользовательский original процесс/x32dbg/F9/приборные Write/Upload/Calib НЕ запускать без согласованного испытания. Не помещать приватные исходные данные в GitHub.


## Окончательная автоматическая приёмка Stage BG

[GitHub Actions #42998754355](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42998754355) SUCCESS: все три задания. Проверенный исходный SHA: e297e3627bf5c2893e4013583dd6603abfa2b490. [Windows EXE artifact #13845742015](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42998754355/artifacts/13845742015) 68 686 785 bytes, expires 2026-11-25T09:59:40Z. Последующие docs-only commits не являются частью проверенного исходного SHA. Оригинальный MVKView/x32dbg/F9, настоящая аппаратная запись и калибровка не запускались; исходные Win32 PNG/JSON full 1:1 пока НЕ представлены.
