@echo off
rem MVK IDR Bridge - read-only local MCP server.
setlocal
set "ROOT=%~dp0"
py -3 -u "%ROOT%mcp_server.py" --db "%ROOT%data\mvk_idr.sqlite" --sources "%ROOT%data\sources"