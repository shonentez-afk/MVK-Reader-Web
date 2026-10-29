# Stage111A — Windows native Desktop preview: сборка и QA (2026-10-29)

## Статус
**CI Windows EXE BUILD PASS**, **Linux Core QA PASS**, **Windows Qt QA PASS**. Статус полной копии оригинальной Delphi MVKView: **NOT ACCEPTED**.

Доказательство: [GitHub Actions run #40847041592](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/40847041592), SHA ветки, по которой проведена проверка: `5f9286b1b9e75072fa0fffbefe34b92f25810f14`.
- Linux `offline-core`: `19 passed in 0.46s`; NumPy only, pure core без HTTP/Qt.
- Windows `desktop-windows`: `21 passed in 1.50s`. Два дополнительных Qt теста: окно с тремя вкладками; открытие **синтетического** полного ZIP, заполнение DSP-таблиц, два графика, выбор АЦП7 и ALERT.
- Windows `windows-exe-preview`: PyInstaller `--onefile --windowed`, упаковка PASS, создание SHA256SUMS.txt PASS, artifact upload PASS.
- Artifact **`MVKViewCompatible_Stage111_Windows_Preview`**, id `12885936688`, размер ZIP 66 426 892 байта. Содержит `MVKViewCompatible_Stage111_PREVIEW.exe` и `SHA256SUMS.txt`. GitHub срок хранения: до **2026-11-12 09:11 UTC**.
- Получение: открыть GitHub Actions run и внизу раздел **Artifacts**. Не именовать эту сборку `MVKView Compatible 1.0` до численной и визуальной приёмки.

## Исправленные реальные дефекты CI (не прятать историю)
Первая Stage111 CI выявила:
1. В исходном GitHub Stage110 Local FFT считался с добавлением Nyquist-бина и прежним упрощённым логарифмом. Ядро Stage111 скорректировано по Stage81d/Stage110B: `N/2` без Nyquist, кандидатом dB служит `10*(fn(P)-2*fn(N/2))`, для `P<=0` возвращается `-180`. Сам `fn=log10` и точная нормировка **всё ещё требуют проверки по оригиналу**.
2. Windows code page CP1252 ломала тест чтения кириллицы из исходника. Исправлен `read_text(encoding='utf-8')`.
3. Для короткого архива (4 096 отсчётов) исходное FFT N=65 536 не подходит: новая Desktop UI автоматически выбирает доступное N (при наличии минимум 1024 отсчётов), что подтверждено Windows Qt интеграцией.

## Текущие ограничения
- Проводной Live R6.1 в Qt Desktop ещё не подключён. Никаких реальных приборных соединений в этом прогоне не было.
- Оригинальная FFT Delphi/float32, огибающая/фильтры, TQGrapher шкалы/копирование, все режимы архивирования и пиксельная идентичность **не проверены**.
- CI проверял синтетический ZIP. Промышленные архивы не выгружались в GitHub.
- PyInstaller сборка — экспериментальный unsigned EXE; нужно отдельное тестирование запуска/GUI на реальной Windows машине, без прибора.
- `main` и стабильная `v0.3.40` не затрагивались; всё находится в исследовательской ветке Stage111.

## Следующий шаг
Проверить запуск скачанного Windows Preview на ПК, офлайн открыть доверенный экспорт Native R6.1, сопоставить расчётные поля/статусы и осциллограмму с MVKView. Далее выбрать **один и тот же BIN**, N, режим и окно для первичной численной сверки локального FFT и курсоров по оригинальному экспорту. Двигаться дальше в ветке Stage111, не возвращаться к старому `server.py`. Перед новым чатом читать `docs/research/STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md`.
