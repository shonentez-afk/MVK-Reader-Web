from pathlib import Path

def test_mode_separates_live_and_archive():
    html=(Path(__file__).parents[1]/'reader_web/static/index.html').read_text(encoding='utf-8')
    assert 'async function showCalcArchive()' in html
    assert "globalDataMode==='archive'" in html
    assert "/collector/api/devices/" in html
    assert '/measurements' in html and '/series?' in html
    assert 'последние сохранённые значения, НЕ текущие измерения' in html

def test_live_uses_existing_polling_no_new_commands():
    html=(Path(__file__).parents[1]/'reader_web/static/index.html').read_text(encoding='utf-8')
    assert "document.visibilityState==='visible'" in html
    assert 'TCP/10230 пока не активен' in html
