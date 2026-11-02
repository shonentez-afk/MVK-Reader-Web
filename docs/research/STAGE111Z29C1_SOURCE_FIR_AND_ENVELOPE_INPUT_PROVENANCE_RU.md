# Stage111Z.29C1 — независимая проверка оригинальных FIR и связь GetSignal → envelope FFT

Дата: 02.11.2026. Ветка research/stage111-mvkview-desktop-20261029.
Точно протестированный исходный commit: 31efbed7f87a902991d95ebee25e0cb1f4929693.
Статус: SOURCE/LOCAL PRIVATE IDP AUDIT + SYNTHETIC CI + WINDOWS ONE-FILE VERIFIED. ORIGINAL WIN32 GetSignal/FFT LIVE NUMERIC PARITY остаётся OPEN.

## 1. Что на самом деле было найдено

В приложенном Projects.7z присутствуют декомпилированные оригинальные PAS/DFM, а в mvkview.idp присутствуют таблицы и FIR-коэффициенты; готового снимка выходного Float32 буфера GetSignal работающей MVKView в этих двух файлах НЕТ. Не смешивать отсутствие runtime GOLDEN с проверкой локального исходного кода.

Локально подтверждены оригинальные адреса _Unit115.pas:
- 007D1C48: диспетчер FIR-декомпозиций по отношению частот (одна или две декадирующие ступени);
- 007D1D50–007D1E0F: скалярная FIR-децимация, коэффициент k, индекс ((j+1)*decimation-1+taps-k), после КАЖДОГО умножения/прибавления FSTP Single на аккумулятор;
- 007D1E70–007D1F7B: парная I/Q FIR-свёртка с двумя Single аккумуляторами и модулем sqrt(I²+Q²) после полного суммирования;
- 007D0D0D/007D0D26: GetSignal использует децимацию и затем I/Q, возвращает обратный порядок Output[N-1-i], а огибающую GetSignal умножает на исходный FRange;
- 007D14D0/007D14E9: GetSpectrum использует те же FIR-процедуры; 007D1546 передаёт уже готовый Float32 вход (EDX) и его длину (ECX) в 007D1FE8 для Hann/FFT БЕЗ повторного DC после FIR;
- 007D14A5 и 007D22C8: GetSpectrum перед исходным DC/FIR читает original Float32 storage по ФЛАГУ 1 с делением на FRange. ВАЖНО: это отдельный неподтверждённый в новой envelope-кандидатной ветви input-domain gate Stage29C2.

## 2. Приватная проверка настоящей IDP без публикации коэффициентов

Контрольная сумма предоставленного mvkview.idp совпала с pinned fingerprint в исходном EnvelopeProfile. Проверены четыре source-таблицы адресов 0x8CD980/0x8D2A58/0x8CDA00/0x8CDA2C и 10 банков Float32 по 512 элементов от 0x8CDA58. Никакой приватный bank или sample не коммитился.

На искусственном сигнале, но с НАСТОЯЩИМИ локальными коэффициентами IDP, независимая скалярная симуляция порядка FIR операций и существующая оптимизированная numpy-реализация дали **6493 из 6493 побитово одинаковых Float32 выходов** суммарно по ВСЕМ 10 банкам. Это две реализации ИСХОДНЫХ ИНСТРУКЦИЙ, не измерение выхода настоящего Delphi-процесса. x87 80-bit промежуточные округления пока не проверены по оригинальному runtime.

## 3. Программная реализация

- core/envelope_fir_source_audit.py: независимая ограниченная скалярная модель каждой ступени (FSTP Single после каждого коэффициента), отдельная IQ/модульная ветвь, сравнение с оптимизированным _fir_step и полный каскад. Лимит входа 6000 отсчётов, нет публикации значений коэффициентов, всегда original_delphi_runtime_ulp_parity_verified=false.
- core/envelope_spectrum_idr_candidate.py: SHA256 ТОЧНОГО массива Float32 после FIR, до Hann/FFT, с признаком unreversed/chronological и original_pre_fft_envelope_runtime_parity_verified=false.
- core/offline_export.py: для существующих OfflineSession.envelope и spectrum_envelope добавлен SHA входной полной BIN-истории до FIR с ADC/Fs/sample-index/claimed RAW SHA (предыдущий Stage29A source provenance). Для GetSignal envelope есть отдельно SHA его ОБРАТНОГО return array и SHA исходного unreversed FIR output. Исходные RAW/BIN/19-file Native export и DSP AUX не изменялись.
- private_getsignal_envelope_compare.py: приватный CLI сравнения оригинального возвращённого x32dbg GetSignal envelope-buffer с нашей реконструкцией из завершённого Native R6 ZIP и проверенного локального mvkview.idp. Требует реальные channel/first_sample/input_samples/EnvelopeCode/FRange/оригинальный OutputLength; не угадывает. Возвращает только aggregate exact words/ULP/SHA, никаких приватных путей/чисел из буфера. Результат оригинального same-run НЕ удостоверяется автоматически.

Синтетическая связка для кода 20, fs=65536: original-inspired GetSignal adjusted history 2099 входных Float32 -> 1024 FIR output; envelope GetSpectrum inverse history 2099 -> 1024 pre-FFT Float32. Тесты доказали одинаковый SHA ИСХОДНОГО окна и одинаковый SHA после FIR перед FFT при FRange=1 и одинаковом локальном выборе окна. FRange=2.5 меняет GetSignal-output, но pre-FFT массив GetSpectrum остаётся иным, что правильно помечено кандидатом, а не подменено численно.

## 4. CI и Windows артефакт

[GitHub Actions #41415766247](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41415766247): все ТРИ JOB SUCCESS.
- Linux Offline Core 1105 passed, 3 skipped, 30 subtests passed.
- Windows Offline Core 1106 passed, 2 skipped, 30 subtests passed.
- Windows Qt 49 passed.
- Go Native R6.1 test/vet/Windows build PASS; Python PyInstaller one-file Qt+Go, PE header, BUILD_INFO/SHA256 PASS.
- [Windows EXE artifact id 13127149911](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41415766247/artifacts/13127149911), zip 68 539 860 bytes.
- EXE SHA256: f6b2da930bd4cb84ea34fe07ee73ef87cef2613d94e530765b9973398a124bcf
- GitHub artifact ZIP digest: f3dbae180ee3a22ae782cc939342a6e77063cfa9cfa631dcd65d2b597e662ddc
- EXACT tested SOURCE SHA: 31efbed7f87a902991d95ebee25e0cb1f4929693. Последующие docs-only коммиты не означают новую бинарную версию.

## 5. Как получить независимый оригинальный runtime-эталон (не включать в GitHub)

На ПК с оригинальной MVKView при открытии ТОГО ЖЕ archived BIN/TSXML (одного ADC/длины/FRange/функции):
1. На исходном подтверждённом адресе _Unit115:007D0E49 после успешного GetSignal проверить EnvelopeCode в [EBX+08], pointer возвращённого буфера [EBX], OutputLength [EBX+28], выходную частоту [EBX+2C]. Снять [EBX] -> 4*OutputLength байт, Little Endian Float32. Учитывать реверс Output[N-1-i]. Реальный модуль/VA предварительно сверить на данной сборке, ничего не писать в память прибора.
2. Запустить локально: python -m mvk_compatible.private_getsignal_envelope_compare --help; передать локальный SHA-проверенный IDP, завершённый ZIP Native той же записи, original_return.bin, настоящий channel, начало окна, число входных отсчётов, envelope code, FRange и число оригинальных выходных отсчётов. Эти параметры НЕ угадываются и НЕ читаются из другого сеанса.
3. Для входа original GetSpectrum до Hann можно отдельно снять EDX и ECX прямо на _Unit115:007D1546. Это НЕ обратный GetSignal return и НЕ исходный BIN, не путать массивы. Четыре spectral mode goldens и FRange branch нужно сравнить отдельно.

## 6. OPEN — без ложного утверждения о полном спектре

Stage29C1 source/code/CI CLOSED. Stage29B original GetSignal реальный исходный обратный буфер и same-run FRange/FRxPos OPEN. Stage29C2 original FRange division before spectrum FIR and actual `GetSpectrum` pre-FFT snapshot OPEN. Stage30 4-mode numerical power/FFT/post-mode/summary/Copy/Save and TQGrapher pixel parity OPEN. Stage26C bounded long LIVE 65536/262144 и Stage32 аппаратная long-run acceptance OPEN. Не повторять Stage52 original FRange writer, Stage108–109 Native, Stage111Z8 bitwise 131072/131072 power и Stage111Z10 3/3 Tag0 summary. Полная [матрица S01-S10](STAGE111Z30_SPECTRUM_PARITY_OPEN_GATES_RU.md).

Stable main/Web не трогать; оригинальные Projects.7z, IDP, EXE, PAS, DFM, captured spectra/RAW/BIN оставлять приватно.