from pathlib import Path

HTML=Path(__file__).resolve().parents[1]/'reader_web/static/index.html'

def test_archive_navigation_controls():
 s=HTML.read_text(encoding='utf-8')
 for token in ['function sortedArchiveRows(rows)', 'function recordNavigation(target)', 'async function selectArchiveRecord(id,target)', 'id="waveRecordNav"', 'id="spectrumRecordNav"', 'id="reportsRecordNav"', 'data-report=', 'visibleArchiveRecords=filtered;', 'v0.3.24']:
  assert token in s

def test_device_io_unchanged():
 assert 'read_ranges' in (HTML.parents[2]/'collector/devices.json').read_text(encoding='utf-8')
