from pathlib import Path
from fastapi.testclient import TestClient
from reader_web.server import app

HTML=Path(__file__).resolve().parents[1]/'reader_web/static/index.html'

def test_archive_detail_controls_present():
    html=HTML.read_text(encoding='utf-8')
    for token in ['id="archiveDetails"','data-info=','async function showArchiveDetails(id)','SQL-история этого прибора','r.gain_metadata']:
        assert token in html

def test_details_route_keeps_404_for_unknown_record():
    assert TestClient(app).get('/api/recordings/not-a-real-id').status_code==404
