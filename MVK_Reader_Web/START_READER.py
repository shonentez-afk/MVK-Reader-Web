"""Safe local launcher: no changes to instrument or polling settings."""
import sys, webbrowser
try:
 import uvicorn
 import integrated
except ImportError as exc:
 print('Не хватает зависимостей:',exc)
 print('Установите: python -m pip install -r requirements.txt')
 input('Enter для завершения...')
 raise SystemExit(2)
print('MVK Reader Web: http://127.0.0.1:8080')
print('Чтобы остановить: Ctrl+C')
uvicorn.run('integrated:app',host='127.0.0.1',port=8080,workers=1)
