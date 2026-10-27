# Протокол выполненных проверок

**Принцип:** тест «существует» ≠ тест «пройден». Указывать среду, дату, commit, точную команду, число пройденных/проваленных проверок и ссылку на лог. Не выдумывать результаты.

| Дата | Commit / версия | Проверка | Результат | Примечание |
|---|---|---|---|---|
| 2026-10-23 | Внешние исходные пакеты | Сравнение PCAPNG/BIN АЦП4 двух МВК | Ранее подтверждено в исследовании | Нужна привязка отчёта к контрольным хешам |
| 2026-10-26 | импорт v0.3.40 | Наличие ключевых файлов GitHub | Выборочно подтверждено | Полная SHA256-сверка 127 файлов не завершена |
| 2026-10-26 | Отдельный пассивный клиент, версия не зафиксирована | TCP/10230 connect + receive, без send(), два прибора | **ПРОВЕДЕНО**: 12.001 с каждый, первые данные через 0.0053/0.0055 с, 0 клиентских прикладных байт | `docs/PASSIVE_TCP10230_TEST_20261026_RU.md`; основной collector не запускался |
| — | — | Полный регрессионный прогон из GitHub | **НЕ ПРОВЕДЁН** | Не запускать сетевые тесты на реальном оборудовании |

| 2026-10-26 | Stage13 изолированный прототип; SHA коммита не указан в первичном журнале | Offline AUX4700/AUX160 + SQLite audit, два RAW | **59/59 unittest OK на Linux**; по 192 AUX4700 строк и 384 AUX160 строк на RAW, SQLite integrity OK | `docs/STAGE13_VALIDATION_IMPLEMENTATION_TRACKER_20261026_RU.md`; Windows не проверена | 
| 2026-10-27 | Отдельный спектральный анализ, SHA не указан | АЦП4/6, бинарные данные против таблиц MVKView | АЦП4 10–3000 Гц: +0.81%; АЦП6: −20.06% (не синхронизировано) | `docs/STAGE13_ADC4_ADC6_HIGH_BAND_AUDIT_20261027.md` | 
| 2026-10-27 | Повторная независимая запись АЦП6 | 61.039 с, 11 TABLE CSV, 10–3000 Гц | 2.860116 против медианы 3.551 м/с²: −19.46%, причина не установлена | `docs/STAGE13_ADC6_REPEAT_RECORDING_20261027_RU.md` | 

Следующие записи вносить ниже с обязательной фиксацией фактического вывода. Исторические проверки без SHA помечены как такие, не выдавать их за CI на текущем commit.

| 2026-10-27 | Stage13 повторный анализ файлов (commit исходного кода не требуется) | Пересчёт загруженного 61.039-с BIN + 9 TABLE CSV | BIN SHA256 совпал с прежним; медианы 9 CSV 1.626/2.221/3.602; PSD 1.673664/1.917813/2.860116 м/с² для полос 10–1000/2000/3000 Гц | `docs/STAGE13_ADC6_REPEAT_RECORDING_20261027_RU.md`; это не второй независимый захват; временное совмещение не выполнено |

| 2026-10-27 | Исследовательский анализ VALUES/BIN, offline, локальная среда Python/SciPy | 124 строки VALUES, номинальная привязка к 61.039-с BIN; PSD 1/2/4 с | 120/118/114 пар окон; отношение 10–3000 BIN/MVKView ~0.804/0.805/0.807; причина не установлена | `docs/STAGE13_ADC6_VALUES_TIME_ALIGNMENT_20261027_RU.md`; инструмент внесён в GitHub, отдельный прогон GitHub-версии ещё не проведён |

| 2026-10-27 | Исследовательский лаг-скан VALUES/BIN | 2-секундные оконные PSD, сдвиги ±6 с с шагом 0.5 с | Максимальные r по полосам 10–3000/2000/1000: 0.4145/0.3653/0.5885 при неодинаковых лагах | Пилотное выравнивание, не измерение реальной задержки, см. `docs/STAGE13_ADC6_VALUES_TIME_ALIGNMENT_20261027_RU.md` |

| 2026-10-27 | Offline ADC4 independent recording | BIN 2212096 samples at 65536 Hz, 10 TABLE, VALUES | RMS 10-3000 = 4.366532 m/s2, VALUES median 4.376 (-0.22%), TABLE median 4.346 (+0.47%) | Separate from ADC6 recording; not time synchronized; no device access |

| 2026-10-27 | Offline Python SciPy | ADC4 and ADC6 BIN, ideal cutoff versus Butterworth bandpass orders 1–8 | Order 3: ADC4 4.365510, ADC6 3.538408 m/s2; close to MVKView medians but post-hoc chosen, not hardware/filter proof | `docs/STAGE13_BUTTERWORTH_EDGE_CHECK_20261027_RU.md`; `tools/adc_filter_edge_audit/check.py` |

| 2026-10-27 | Offline SciPy spectral model, two exported BIN | Fixed order-3 filter applied across 3 bands on ADC4 and ADC6 | Six VALUES median relative errors under 0.35%; split-half results recorded; non-synchronized | Not a blind confirmation of the true filter; see docs/STAGE13_BUTTERWORTH_EDGE_CHECK_20261027_RU.md |

| 2026-10-27 | Анализ документации производителя | ВАРБ.411711.112 РЭ, приложение 1, стр. 41–44 | Документально подтверждён Hann FFT и крайние весовые функции фиксированных полос; Баттерворт 3-го порядка НЕ указан | `docs/MVK01_HANDBOOK_FILTER_ALGORITHM_20261027_RU.md`; документальная, не вычислительная проверка |

| 2026-10-27 | Offline fixed-band scaffold | Код и 3 синтетических unittest добавлены в PR #11 | NOT RUN / НЕ ПРОВЕРЕНЫ в чистом checkout | tools/mvk_fixed_band_lab/, docs/STAGE13_FIXED_BAND_RECONSTRUCTION_20261027_RU.md |

| 2026-10-27 | Документальная проверка таблицы 4 ВАРБ.411711.112 РЭ | Полосы и класс третьоктавных фильтров | CLASS 2 по ГОСТ Р 8.714-2010; 10–3000 Гц не перечислена в табл. 4 | docs/MVK01_TABLE4_BANDS_CLASS2_20261027_RU.md; только изучение руководства, не вычислительный тест |

| 2026-10-27 | GOST class 2 documentary audit | Third-octave 3150 Hz and ADC6 peaks | 3105/3313 inside nominal band; fixed-band weights unknown | docs/STAGE13_THIRD_OCTAVE_CLASS2_EDGE_20261027_RU.md |

| 2026-10-27 | P1.4 two-spectrum scaffold | Added p14_two_spectrum.py and 3 synthetic tests | NOT RUN; no BIN validation, no vendor windows | docs/STAGE13_P14_TWO_SPECTRUM_CORRECTION_20261027_RU.md |

| 2026-10-27 | Local Python + numpy; P1.4 structural test copy | 3 synthetic unit tests | 3 PASS, 0 FAIL; GitHub checkout itself not tested | docs/STAGE13_P14_EXECUTION_20261027_RU.md |
| 2026-10-27 | Local SciPy Welch Hann, two BIN exports | ADC4/ADC6 independent spectral preflight | RMS 10-3000: 4.366450/2.860347; 3000-3536: 0.328961/2.865118 m/s2 | Offline PSD baseline only, not final P1.4 output |

| 2026-10-27 | Handbook review | Indexed all 55 pages by main sections, Appendix 1 DSP and Appendix 2 Modbus | Identified GOST ISO 2954-2014 for fixed 10-3000; A+0x60; 42 vs 43; buffer status bits | `docs/MVK01_MANUAL_FULL_ANNOTATED_AUDIT_20261027_RU.md`; documentary, not instrument test |

| 2026-10-27 | Normative cross-check | MVK01 manual Appendix 1 sec 1.3 vs GOST ISO 2954-2014 sec 5.3 | Third-order Butterworth HP+LP directly named by standard; exact DSP still unknown | docs/STAGE13_GOST_ISO2954_BUTTERWORTH3_20261027_RU.md |

| 2026-10-27 | Repository reconciliation | docs/FRAME_4700_MODBUS_MAPPING_20261026_RU.md and decoder | 10230 sends 4700-byte calculated frames; 43 slots proven, reason for 42 in P1.3 unresolved | docs/STAGE13_TCP10230_CALCULATED_43_VS_42_RECONCILIATION_20261027_RU.md |

| 2026-10-27 | Created synthetic tests and offline audit for 4700 calculation frames | tools/raw_offline_audit/test_4700_calculated.py; audit_4700_first_octave.py | NOT RUN, results pending existing RAW / local runtime | docs/STAGE13_4700_DECODER_NEXT_STEP_20261027_RU.md |

| 2026-10-27 | GitHub evidence cross-check before Stage13 next step | Existing ADC4 screenshot vs 4700, master plan and evidence spec | Prior comparison confirmed NON-SYNCHRONOUS; full 24-field time-aligned MVKView validation not confirmed; do not repeat mapping | docs/MVKVIEW_ADC4_SCREEN_COMPARISON_20261026_RU.md |

| 2026-10-27 | Stage13 normative HP3*LP3 fixed bands | 4 synthetic unittest local and 2 real BIN ADC4/ADC6 | 4 PASS; 10-3000 ADC4 4.365258579, ADC6 3.542213511 m/s2; no synchronized instrument identity proof | docs/STAGE13_NORMATIVE_FIXED_BAND_EXECUTION_20261027_RU.md |

| 2026-10-27 | P1.2/P1.3/P1.4 offline orchestrator | Five synthetic unit tests with equivalent local prior P1.4 dependency | 5 PASS locally; clean GitHub checkout NOT TESTED | docs/STAGE13_P12_P14_PIPELINE_IMPLEMENTATION_20261027_RU.md |

| 2026-10-27 | All-eight ADC offline validation on four PCAPNG | Four saved captures 83/84; stream->gain->HP3*LP3->4700 median | 32 session-channel comparisons produced. Three PCAP show no TCP sequence gaps, recording83 has one missing 847-byte segment; ADC1 recording83 invalid. Most remaining errors within few percent; 83 ADC5 realtime +5.71%. NOT a time-aligned DSP acceptance | docs/STAGE13_ALL8_FOUR_PCAP_NORMATIVE_20261027_RU.md |
