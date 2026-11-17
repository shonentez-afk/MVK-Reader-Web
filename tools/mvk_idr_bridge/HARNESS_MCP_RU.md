# Локальный агент (Hermes / Harness) + Ghidra 12.2 без OpenAI Tunnel

**Предпочтительный путь:** используйте уже установленный **GhidrAssistMCP 3.0.0** в Ghidra 12.2. Релиз LaurieWired/GhidraMCP 2.0 собран для Ghidra **12.1.4**, поэтому под имеющуюся 12.2 его нельзя рекомендовать как совместимую готовую сборку.

## 1. Убедиться, что Ghidra запущена

- Откройте CodeBrowser проекта `mvkview.exe`.
- Window → GhidrAssistMCP: Host **127.0.0.1**, Port **8080**, `Enable MCP Server` включено.
- В списке инструментов GhidrAssistMCP отключите `create_*`, `delete_*`, `set_*`, `rename_*`, `execute_*`, `analyze_program`, `disassemble_bytes`, `import_file`, запуск скриптов и другие mutating tools; нажмите `Save Configuration`.
- В PowerShell можно проверить только TCP-доступность:

```powershell
Test-NetConnection 127.0.0.1 -Port 8080
```

Успех TCP не доказывает полноценный MCP handshake; агент проверит `tools/list`.

## 2A. Hermes Agent (NousResearch)

Документация: https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp

Откройте `~/.hermes/config.yaml` (на Windows с локальным Hermes это обычно `%USERPROFILE%\.hermes\config.yaml`, в WSL — домашний Linux-каталог) и добавьте **внутрь существующего** `mcp_servers` (не дублируйте ключ, если он уже есть):

```yaml
mcp_servers:
  mvk_ghidra:
    url: "http://127.0.0.1:8080/mcp"
    timeout: 90
    connect_timeout: 20
    tools:
      include:
        - list_open_programs
        - get_program_info
        - list_functions
        - search_functions
        - get_function_info
        - get_function_prototype
        - get_pseudocode
        - get_pseudocode_batch
        - get_disassembly
        - get_pcode
        - get_call_graph
        - get_callers
        - get_callees
        - get_xrefs_to
        - get_xrefs_from
        - get_hexdump
```

Перезапустите Hermes (`hermes chat`) и попросите вывести список инструментов сервера `mvk_ghidra`. Они будут доступны с префиксом `mcp_mvk_ghidra_...`.

**Если Hermes установлен в WSL2, а Ghidra работает в Windows**, адрес `127.0.0.1` внутри WSL может относиться к Linux-окружению; сначала убедитесь, что WSL может обращаться к Windows loopback (mirrored networking), иначе нужен иной **локальный** маршрут. Не меняйте Host Ghidra на `0.0.0.0` и не открывайте порт в общую сеть без изоляции/авторизации.

## 2B. Любой локальный Harness с HTTP MCP

Добавьте Streamable HTTP сервер (точный формат зависит от программы):

```json
{
  "mcpServers": {
    "mvk-ghidra": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:8080/mcp"
    }
  }
}
```

Это **схематичный** JSON: разные Harness-клиенты используют ключи `mcpServers`/`mcp`/`servers` и разные значения `type`. Он не гарантирован для конкретного клиента. Если конфигурация просит URL — введите именно `http://127.0.0.1:8080/mcp`. В отдельном поле транспорта укажите **Streamable HTTP**, не `stdio`.

## 3. Первая безопасная проверка

Попросите агента:

> Подключись к локальному серверу `mvk_ghidra` и проверь, что открыта `mvkview.exe`. Только чтение. Получи `get_function_info`, `get_pseudocode`, `get_disassembly`, `get_callers`, `get_callees` для адресов `007D13D4`, `00807A98`, `00809330`, `00809400`, `00848E78`, `00846AD4`. Не меняй Ghidra-проект, не запускай EXE и не инициируй TCP-передачу прибору. Сохрани исходные результаты в локальные файлы, сообщи о неполных или отсутствующих функциях.

Результаты агент может сохранять в локальные файлы и отправлять в приватный чат либо загружать **только очищенные от оригинального кода** аналитические отчёты/патчи реализации в ваш GitHub. Для загрузки полной декомпиляции оригинального коммерческого бинарника в публичный репозиторий требуется отдельная проверка прав и приватности.

## 4. Полностью автономный резервный экспорт

Если в Harness проблемы с MCP, выполните `MVK_Export_IDR_Research.java` прямо в Ghidra Script Manager. Он экспортирует до 64 нужных функций и связи в локальную папку. Архивируйте результаты и приложите к приватному чату. Это не требует ни работающего Harness, ни прав администратора ChatGPT.