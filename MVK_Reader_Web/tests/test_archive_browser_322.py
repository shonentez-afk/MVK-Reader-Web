from pathlib import Path
from fastapi.testclient import TestClient
from reader_web.server import app

HTML=Path(__file__).resolve().parents[1]/'reader_web'/'static'/'index.html'

def test_archive_controls_present():
    html=HTML.read_text(encoding='utf-8')
    for token in ['id="archiveDevice"','id="archiveChannel"','id="archiveFrom"','id="archiveTo"','function renderArchive()','data-spec=','data-open=','function archiveMetadata(r)']:
        assert token in html

def test_reader_web_home_opens():
    response=TestClient(app).get('/')
    assert response.status_code==200
    assert 'archiveDevice' in response.text
