# Stage111Z.24 — первичная карта присваиваний Original Storage.FRange (static audit)

Дата: 02.11.2026. Статус: **PARTIAL / SOURCE-BASED**. Продолжение Z.23 без изменения DSP, FFT goldens или UI.

## Метод и границы

Повторно прочитаны приватные original IDR из предоставленного Projects.7z: _Unit115.pas, _Unit125.pas, _Unit128.pas. В GitHub фиксируются **только выводы и адреса**; оригинальные PAS, EXE, IDP, BIN, RAW, PCAP и PNG не загружаются. Никаких сетевых подключений к МВК не выполнялось. Поиск строкового комментария FRange не является доказательством исчерпывающего перечня writers, так как обращения в других модулях могут быть без типизированных комментариев.

## Подтвержденные writer sites

1. **Конструктор Storage** _Unit115:007D0A61: `mov dword ptr [esi+4],3F800000`. Это устанавливает `TMvkChannelStorage.FRange=1.0f` для вновь созданной структуры. **Не** доказательство текущей runtime-калибровки после изменения параметров.
2. **Archive loader** _Unit128:0084655B..0084655E: `mov eax,[ebp-2C]; mov [ebx+4],eax` — присваивание предварительно разобранного Single из TSXML/fallback в `Storage.FRange`. Ветка при положительном `InternalChannelGain` позволяет не масштабировать сохраненные отсчеты повторно (см. Z.21/Z.23).

## Связанные dataflow sites, но не записи FRange

- _Unit125:00806964..00806985 читает коэффициент через GetFloatByAddr(0x0E) для Original TSXML writer; это **не** само по себе присваивание live `Storage.FRange`.
- _Unit115:007D23B7..007D23E5 читает FRange и выполняет in-place умножение Float32 в ApplyRange path; это **не** writer коэффициента.
- _Unit125:00808284..008082DE использует ProcessBufferChunk до ChannelFile.Write; pointer alias установлен Z.23.

## Что пока нельзя объявлять

- Полный список всех присваиваний live `Storage.FRange` в _Unit125, _Unit115 и других исходных модулях **не завершен**. Не исключён writer без символической подсказки IDR.
- Нет runtime-снимков FRange для ADC1–8 на конкретной сессии; нет same-run оригинального BIN и TCP с общими timestamp/ADC/sample-index.
- Не проверены физическая размерность, точное округление Single на pipeline загрузка → GetSignal → GetSpectrum и cross-application numeric parity.

## Следующий проверяемый шаг

Разметить все `[StoragePtr+4]` записи по межпроцедурным aliases в original original live path; получить исходный BIN+TSXML для того же сеанса, по одному ADC фиксировать Fs, N, sample index, GetSignal before/after ApplyRange, spectrum bins. Проверять только offline, без автоматического повторного применения TSXML gain, не менять исходный FFT golden. Следить за различием исходных Byte/Count и Float32 каналов.

## Acceptance Z.24

- [x] Подтверждены init writer и archive loader writer по точным исходным адресам.
- [x] Разделены writers и readers/metadata bridge.
- [ ] Полная межпроцедурная карта всех live writers и маршрутов вызова.
- [ ] Same-run runtime originals и независимый численный контроль.
- [ ] GetSignal/GetSpectrum parity.
