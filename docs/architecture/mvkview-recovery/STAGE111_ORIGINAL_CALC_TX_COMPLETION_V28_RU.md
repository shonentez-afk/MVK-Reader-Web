# Atlas v28 — расчётный контракт, TX/reconnect и завершение потоков

24.11.2026. Только оригинальная архитектура. Stage111/main/research/fix/PR #14 не изменялись, команд прибору не отправлялось. Приватные адреса, исходники, машинные инструкции и детальный граф не публикуются.

## Результат
Повторно сверены SHA всех 133 source files, IDP SHA, SQLite quick_check. Самостоятельное приватное дополнение v28: 26 карточек, 34 направленных отношения, 6 маршрутов, реестр 17 членов расчётной структуры. В текущем контейнере нет приватного v27 ZIP/HTML/CSV; прежние 641 IDs и полный v15–v27 не перезаписывались, интеграция не аттестована. Дополнение необходимо объединить с v27 при наличии архива, не заменять историческую карту.

- В структуре Params 17 именованных членов, из них 15 относятся к общему ADC/SPEC контракту, два — специализированному narrowband. Не трактовать 15 членов как 15 отдельных числовых UI-контролов. В DFM две сводки и два курсорных индикатора; PageStatus/VALUES/TABLE — иной регистровый путь. Отдельные Params и graphers ADC/SPEC для выбранного канала.
- Уточнены начальные значения, length/Fs, overlap/contiguous/position, output buffer, DC/envelope, RMS, peak frequency/amplitude, оси и units. Log chart и физическая summary различаются. Условный cursor aggregation и FFT count/summary endpoints не смешивать. Приватный реестр содержит формулы, единицы и исходные опоры; x87/locale/runtime parity не аттестованы.
- Task2 TX: changed desired rate → FIFO append → Stage1/count gate → synchronized dequeue → send → free → Read. Проверена граница dequeue/send/free; при исключении между удалением из очереди и освобождением не найден reinsert на просмотренном пути. Не заявлять доказанный runtime leak. ACK correlation не установлена.
- Reconnect: тот же thread self, новый TCP epoch, forced file cleanup, stage reset, условная повторная постановка желаемой rate, ожидание и retry. Начальный цикл ожидания включает дополнительную итерацию sleep; верхний порог роста паузы не является жёстким clamp. Range/Units обновляются на первом принятом PARAM эпохи, а не на каждом PARAM. Свежесть старого окна при metadata change остаётся условной.
- В машинном образе восстановлено тело явного synchronized calibration completion callback, отсутствовавшее в Pascal/SQLite. Восстановление подписи, включение двух кнопок, обнуление ссылки на calibration thread до возврата Execute. Два виртуальных callsite разрешены статически через DFM TButton, class VMT self/name/slot и машинную цель. Это не OnTerminate; self-free и DoTerminate отдельны. Реальные назначения OnTerminate остаются открытыми.
- Bounded raw-image scan четырёх исторических unresolved targets: по одному абсолютному совпадению, прямых rel32 E8/E9 кандидатов не найдено. Не доказательство отсутствия косвенного вызова. 33 reader routes, 7 GetRawSignal, background producer и аварийные interleavings остаются открытыми; без прежнего CSV нельзя пересчитать исторический ledger.

## QA
231/231 static/source/analytic checks PASS (включая 133 SHA, 10 машинных E8 проверок, VMT и аналитические sanity checks); 107/107 Chromium interaction checks PASS, JS syntax PASS, 0 page errors. Browser page.set_content; file:// заблокирован политикой среды. Это QA дополнения и статических доказательств, не original EXE или приборная приёмка.

## Дальше
Объединить v28 с полным приватным v27, сохранив все старые IDs/панели/маршруты. Затем resolver для procedural pointers/extended RTTI, OnTerminate assignment, background producer, 33 reader и 7 GetRawSignal routes, exception/Stop interleavings; уточнить названия ожидаемых 15 UI показателей, если имелся в виду иной реестр, не придумывать поля. Не исправлять рабочий код в этом чате, не публиковать приватные материалы.
