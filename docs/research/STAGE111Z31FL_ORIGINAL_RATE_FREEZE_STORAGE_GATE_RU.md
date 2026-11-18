# Stage111Z31FL — исходное правило TMVKThread MvkSampleRate + FreezeUpdate

Дата: 18 ноября 2026. Ветка `research/stage111-mvkview-desktop-20261029`.
Критерий: восстановить **условие записи в оригинальные десять колец**, отдельно от непрерывного пассивного приёма TCP и forensic RAW. **Не включать** device TX без отдельного согласия.

## Совместная сверка трёх приватных источников

Источники сохранены только в приватной среде: `/mnt/data/mvkview.idp` (IDR v3, SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`), `/mnt/data/Projects.7z` (исходные реконструкции `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas`, `mvkform.dfm`), `/mnt/data/mvk_idr(1).sqlite` (quick_check=ok, 25404 functions, 92767 calls). Все четыре PAS/DFM повторно имеют **4/4** SHA и byte size совпадения с SQLite.

Подтверждённое IDP/Pascal/SQLite:
- `_Unit125:0080618E`: при `TMVKThread.Create` устанавливается **MvkSampleRate=777**; `00806198`: **FreezeUpdate=false**.
- `_Unit128:00846DDF–00846DF7`: сразу после создания Task2 вызывается `mRate1Click(Items[0])`, который выбирает Tag **65536 Гц** и `0084DF18` вызывает исходную `TMVKThread.SetRate`.
- `_Unit125:00809400–00809413`: `SetRate` **сначала записывает новое значение MvkSampleRate в память**, а затем ставит команду в очередь через `00809364/00809330`. Настоящая передача 36 байт на устройство по-прежнему требует явного отдельного разрешения; пассивный режим не должен представлять выбор 65536 как физически отправленную команду.
- `_Unit125:008081F0–008082EB`: всегда считывается полная фактическая полезная нагрузка TCP (включая куски, пересекающие край кольца). Перед `ProcessBufferChunk` выполняется `packet_rate==MvkSampleRate`, далее `!FreezeUpdate`. При невыполнении условия **FRxPos не увеличивается**; полные байты прочитаны, но текущий исходный GetSignal не должен их использовать.
- `_Unit128:0084DEA4–0084DEC3`: кнопка `bFreezeUpdate` переключает ровно `TMVKThread.FreezeUpdate` и затем перерисовывает меню/иконку; это не сетевой приказ и не блокирование TCP.
- `_Unit115:007D1AE0` — `InvalidateData`; `007D1998` — `CheckDataAvailability`; `007D2398` — `ProcessBufferChunk` с UInt64 `FRxPos` и Float32/Byte в зависимости от типа канала.

## Реализация

**Основной пакет `1fec703`:**
- `source_original_receive_gate.go`: отдельная модель selected rate и freeze, начальная последовательность `777→65536` без скрытой передачи прибора; десять независимых счётчиков допущенных и пропущенных элементов (TACH — **bytes**, ADC — **Float32**); `last_skipped_native_samples` для защиты коротких кадров.
- `main.go`: создаёт этот gate только для реального Task2 Live, не для offline replay или Task0 IP. Единственный Go RX goroutine читает ограниченную stdin очередь `FREEZE 0/1` и `RATE <Fs>` на уже запущенном процессе.
- `monitor.go` и `live_bin_spool.go`: после безусловной forensic RAW записи source кольцо обновляется **только по gate**; при freeze/rate mismatch ни один пакет не дописывается в исходное кольцо. Forensic Native BIN и временный Native preview остаются независимыми и прямо не называются исходным Delphi storage; дополнительные проверки не позволяют выводить из них ложный GetSignal.
- `source_live_task2_tx.go`: команда `FREEZE` меняет локальный бит без доступа к `net.Conn`, даже когда SetRate TX не разрешён. Реальная `RATE` без отдельного аппаратного разрешения отвергается. При разрешении SetRate локальный MvkSampleRate меняется до фактической передачи/ACK — как исходный `SetRate`.
- `MVK_NATIVE_LIVE_STATUS.json` получает новый `source_original_receive_gate` с активным состоянием и независимыми десятью счётчиками. Не утверждает физическое SetRate.
- `original_receive_gate_receipt.py`, `native_r6_live_status.py`, `original_source_ring_receipt.py`: Python проверяет точную сумму `admitted + skipped_rate + skipped_freeze == real_tcp_elements`, исключает поддельные индексы и не требует равенства исходного кольца полному Native RX после FreezeUpdate.
- `original_measure_controls_ui.py`, `native_capture_dialog.py`: исходная `bFreezeUpdate` работает через **локальную строку QProcess stdin**; никаких новых сокетов и команд промышленному прибору. UI хранит отдельное доказательство, что Go подтвердил состояние паузы.
- `original_live_view_gate.py`: SHA-проверенный Native preview с байтами, исключёнными из original ring, не может быть назван текущим исходным GetSignal. Для нового короткого окна требуется достаточная история после последнего исключённого отсчёта. Raw forensic продолжает сохраняться независимо.

**Продолжение того же функционального пакета:** on-demand `source_live_long_window.go` и `original_source_long_window.py` получают допустимое равенство `source FRxPos == admitted count`, а не `source FRxPos == все Native TCP Samples`. После снятия паузы и получения полного свежего окна (например, 1310720 Float32 при 65 536 Гц ×20с) Source GetSignal снова разрешён, если весь участок доступен, непрерывен и не перезаписан. В период FreezeUpdate — запрещён. Old offline status без gate сохраняет прежнюю строгую проверку.

## Независимые регрессии

Go: исходное `777→65536`, пассивное несовпадение частоты, FreezeUpdate/Thaw, непрерывность RAW, сохранность byte TACH, отсутствие физического SetRate, локальная QProcess команда, статус gate, длинный 20с GetSignal после thaw, повторный запрет при freeze.

Python Core: точные 10 каналов, типы/суммы счётчиков и uint64, отказ от поддельных состояний/отсчётов/физической TX; source ring с различными Native/Gate позициями; длинный GetSignal после thaw, запрет при активном FreezeUpdate и перезаписи.

Qt: реальная кнопка `bFreezeUpdate` посылает только `FREEZE 1/0\n` существующему Go QProcess, отправка RATE по умолчанию остаётся недоступной; реальный source preview с замороженными пакетами не показывается до полного нового окна. Прямая операторская кнопка появляется после входа в Mode2 независимо от подключения.

Последний исходный полностью проверенный пакет: [Stage111Z31FK CI #44215525463](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44215525463) 5/5 SUCCESS включая Windows EXE. CI для FL следует проверять на итоговом SHA после фиксов; **не объявлять приёмку до 5/5**.

## Что остаётся OPEN, даже если FL 5/5

Это **source-backed compatible implementation** на Go/Python/Qt, **не оригинальный исполняемый Delphi `TMVKThread`**. Пассивный режим не посылает source SetRate(65536) автоматически — значит не может приписывать физическому МВК выбранную Fs, если её не подтвердил трафик. Полный исходный `Task/Stage=0/1/2/3`, QueueCommand/ACK/DENIED и реальное переключение источника Fs, Win32/x87 FRange, отправка WriteData/WriteValues и полный аппаратный E2E остаются OPEN. `original_delphi_compatibility_verified=false`. В GitHub запрещено копировать приватные IDP/PAS/DFM/SQLite, исходные RAW/PCAP и кадры с физических приборов.
