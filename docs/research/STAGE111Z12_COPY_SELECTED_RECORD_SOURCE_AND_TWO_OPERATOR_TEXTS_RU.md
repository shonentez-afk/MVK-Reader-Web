# Stage111Z.12 — оригинальная кнопка «Копировать» читает ВЫБРАННУЮ запись спектра

**Дата:** 01.11.2026. **Рабочая ветка:** `research/stage111-mvkview-desktop-20261029`.  
**Продукт:** автономная Windows Qt/PySide6 MVKView Compatible, не Web/сервер.

## 1. Какие настоящие строки уже прислал оператор

Два operator-reported оригинальных результата из «Копировать» (разделитель TAB, десятичная запятая):

| Визуальная запись | Интегральное | Частота пика, Гц | Амплитуда |
|---|---:|---:|---:|
| Одна соседняя запись | 6,15 | 19,93 | 6,096 |
| Другая соседняя запись | 5,57 | 19,94 | 5,522 |

Оба наблюдения **совместимы с исходным текстовым шаблоном 3/4/4 значащих цифры** и TAB-разделением. Они **не совпадают** с операторским runtime `GetSpectrum` Stage111Z.10: mean `40DC8F5E` (6.8925), peak-index `466D8095` (15200.1455), Y `3F475279` (.7786), Fs/N=.25, то есть частота около 3800.0364 Гц. Эти строки нельзя объявлять текстовым Delphi golden для старого GetSpectrum triplet; общий runtime provenance к конкретному backend вызову не доказан. Оператор уточнил, что строки относились к расположенным рядом спектральным записям.

## 2. Почему исходные записи отличаются — прямой SOURCE-аудит

В приватном оригинальном `mvkview.idp` local/offline disassembly подтверждены три окна **SHA256**:

| Code window | VA | Назначение |
|---|---|---|
| Copy prologue/selection prep | `0084BC46–0084BC7B` | Handler Form context |
| Copy selected-record body | `0084BC7B–0084BCE2` | Selection, Single inputs, XScale, 3 Formatter calls |
| Current selection helper | `0084EADC–0084EAF4` | Выбор записи текущего окна |

Оригинал в `0084BC7D` вызывает selection helper `0084EADC`. Если `[form+624]==1`, индекс 0; иначе берёт control `[form+430]` и вызывает `005B01C8` для получения активного индекса. На `0084BC85` вычисляет:

```text
ESI = FormEBX + 0x908 + selected_index * 72
```

**Три реальные поля, которые копирует САМО окно**, а не старые временные `GetSpectrum` параметры:

| Source instruction | Selected record DWORD | Значение |
|---|---|---|
| `0084BC8C` | `dword:[ESI+30]` | OutputMean Float32 |
| `0084BCAD` | `dword:[ESI+34]` | OutputPeakX в бинах Float32 |
| `0084BCCF` | `dword:[ESI+38]` | OutputPeakY Float32 |
| `0084BCA4–0084BCB3` | `dword:[dword:[dword:[EBX+FF4]+40]+14]` | XScale графика Float32 |

Оригинал выполняет `FLD Single OutputPeakX`; `FMUL Single graph XScale`; `FSTP Single frequency`, после чего вызывает `007B2090` с точностью 4 для частоты. Функция `007B2090` вызывается **трижды** с аргументами **3,4,4**. Результат Clipboard построен из этих трёх полей, разделённых TAB. Таким образом, частота в Copy зависит от **XScale актуального видимого графика**, не должна автоматически подменяться предположением Fs/N от ранее перехваченного GetSpectrum.

Это объясняет, почему сравнение с прошлым FFT-отчётом могло дать ложную «ошибку»: исходный Copy читает отдельное хранилище выбранной отображаемой записи. Поскольку настоящий текущий `ESI` и `XScale` оператор ещё не прислал, **не доказано**, связаны ли два исходных значения с разными каналами, окнами времени или просто разными выбранными элементами UI.

## 3. Новые инструменты

- `mvk_compatible/private_spectrum_copy_selection_source_audit.py`: read-only оригинальный приватный IDP audit трёх SHA code windows, E8 callsite, selection source и пути трёх полей+XScale. Не печатает исходных байтов/адресов файлов/измерений.
- `mvk_compatible/tests/test_private_copy_selection_source_audit.py`: synthetic-only фабрика opcode fixtures, SHA tamper и fail-closed.
- `mvk_compatible/private_spectrum_copy_selected_record_compare.py`: принимает один приватный локальный JSON с четырьмя исходными FLOAT32 HEX и ссылкой на отдельную оригинальную 3-TAB строку **от одного нажатия**. Вычисляет частоту через реально прочитанный XScale, форматирует 3/4/4 через пока кандидатный `007B2090` и возвращает только 3 boolean/text-equality, не приватные слова.
- `mvk_compatible/tests/test_stage111z12_same_click_copy_compare.py`: синтетические независимые тесты (все 3 равны, ровно одно поле меняется, ошибочная попытка привязать другую запись, unsafe file/symlink/input).

**Никаких оригинальных Exe/IDP/PAS/DFM/BIN/RAW/PCAPNG в GitHub и CircleCI не передавалось.** Числовой FFT и GetSpectrum Summary в текущей версии не изменены: Stage111Z.8 и Z.10 остаются валидны для прежней пары.

## 4. Следующее действие: один Copy-click x32dbg (Stage111Z.13)

В оригинальной MVKView открыть офлайн-архив и нужную из двух записей. В **x32dbg**:

```text
bp 0084BC8C
```

Нажать GUI-кнопку **«Копировать»**. Когда x32dbg остановится ровно на `0084BC8C`, записать:

```text
esi
ebx
dword:[esi+30]                          // mean Float32 HEX
dword:[esi+34]                          // peak bin Float32 HEX
dword:[esi+38]                          // peak amplitude Float32 HEX
dword:[dword:[dword:[ebx+FF4]+40]+14]  // XScale графика Float32 HEX
```

**Важно:** здесь `EBX` — *главный Form*, а не `CalcParams` из `007D1900`. На третьем вложенном адресе берётся именно график текущего окна, затем реальная `XScale`. Скопировать 4 HEX, затем F9, дать кнопке завершить работу и вставить одно TAB-содержимое Clipboard. **Не менять выбор записи между остановкой и Ctrl+V.** Это лучший первичный эталон форматирования и выбора графика, чем любые фрагменты FFT из другого вызова.

Для локального однопроходного сравнения использовать `python -m mvk_compatible.private_spectrum_copy_selected_record_compare C:\MVK_CAPTURE\same_click.json`; пример JSON приведён в отдельном [пошаговом руководстве](STAGE111Z12_X32DBG_COPY_SELECTED_RECORD_RU.md).

## 5. Ограничения и следующие шаги

**Теперь SOURCE VERIFIED:** Copy выбирает отдельную запись и 3 поля из `ESI`, XScale из текущего графика, 3/4/4 форматирования.  
**Operator observed:** две настоящие строки, обе с TAB и запятой, 3/4/4 шаблон.  
**NOT VERIFIED:** реальные 4 DWORD на `0084BC8C` от этой же строки, побитовая RTL FormatFloat parity, связь с прошлым GetSpectrum, курсор, TQGrapher pixel parity.

Далее снять 4 DWORD в том же Copy-click; сравнить символы и при необходимости исследовать `007B2090`/Delphi RTL округление, потом CursorString и графические координаты. Stable `main`, старую Web v0.3.40, прибор и приватные исходники не трогать.
