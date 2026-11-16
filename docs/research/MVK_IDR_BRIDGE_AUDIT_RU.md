# MVKView IDR — отчёт фактической реконструкции

Сформировано из приложенных `mvkview.idp` и `Projects.7z`; всё извлечено статически без запуска MVKView.

## Покрытие

| Набор | Количество |
|---|---:|
| source_files | 133 |
| functions | 25,404 |
| calls | 92,767 |
| forms | 3 |
| components | 162 |
| events | 95 |
| events_resolved | 95 |
| calls_resolved | 65,448 |
| dfm_class_count | 34 |
| pas_count | 129 |
| dfm_count | 3 |
| dpr_count | 1 |

## Проверенные ориентиры

| Компонент | Событие | Обработчик | Адрес | Источник |
|---|---|---|---|---|
| `bTaskConnect` | `OnClick` | `bTaskConnectClick` | `00848E78` | `mvkform.dfm:510` |
| `bTaskView` | `OnClick` | `bTaskViewClick` | `00848E84` | `mvkform.dfm:598` |
| `bTaskConfigCh` | `OnClick` | `bTaskConfigChClick` | `00848E60` | `mvkform.dfm:577` |
| `bTaskConfigIP` | `OnClick` | `bTaskConfigIPClick` | `00848E6C` | `mvkform.dfm:532` |
| `Pages` | `OnChange` | `PagesChange` | `0084ECF0` | `mvkform.dfm:49` |
| `bSpecCopyValue` | `OnClick` | `bSpecCopyValueClick` | `0084BC28` | `mvkform.dfm:1252` |
| `bSpecSaveValue` | `OnClick` | `bSpecSaveValueClick` | `0084BD7C` | `mvkform.dfm:1268` |

### GetSpectrum

`TMvkChannelStorage.GetSpectrum`: `007D13D4` (`_Unit115.pas:17386`).

Вызовы в восстановленном машинном коде:

- `00848200` — `sub_00848148` (`00848148`), `_Unit128.pas:4844`
- `0084FB03` — `TBackgroundProcessThread.Execute` (`0084FA6C`), `_Unit128.pas:12345`

## Границы доказательств

- Адреса и переходы получены из восстановленного IDR-листинга, а не из динамической трассировки.
- Полные записи IDP, включая RTTI и InfoRec, отдельно не декодировались.
- Элементы с `Caption = "$"` имеют динамическую подпись: её нельзя достоверно восстановить из DFM.
- Для аппаратных кнопок запрещено автоматическое выполнение; MCP-мост предоставляет только чтение.