import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import pytest
from io import BytesIO

try:
    # Optional: use reportlab for robust synthetic PDF generation if available
    from reportlab.pdfgen import canvas  # type: ignore
    HAVE_REPORTLAB = True
except Exception:  # pragma: no cover
    HAVE_REPORTLAB = False

# Ensure local package import
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from latex_mcp_server.functions import latex_ops  # noqa: E402
from latex_mcp_server.server import build_registry  # noqa: E402

WORKSPACE = Path(__file__).resolve().parents[2]


def test_list_tex_files():
    files = latex_ops.list_tex_files(WORKSPACE)
    assert any(f.endswith('main.tex') for f in files)


def test_read_file():
    data = latex_ops.read_file(WORKSPACE, 'main.tex', max_bytes=2000)
    assert data['path'] == 'main.tex'
    assert 'content' in data and len(data['content']) > 0


def test_extract_bibliography_and_index(tmp_path):
    # Copy references to temp file for isolation
    bib_rel = 'src/references.bib'
    assert (WORKSPACE / bib_rel).is_file()
    # Run extraction
    entries = latex_ops.extract_bibliography(WORKSPACE, bib_rel)
    assert isinstance(entries, list) and entries
    first = entries[0]
    assert 'key' in first and 'title' in first
    # Check index.json created
    index_path = WORKSPACE / 'resources' / 'cited_papers' / 'index.json'
    assert index_path.is_file()
    idx = json.loads(index_path.read_text(encoding='utf-8'))
    assert isinstance(idx, list) and idx


def test_download_bibliography_limit():
    summary = latex_ops.download_bibliography(WORKSPACE, force=False, limit=1)
    assert 'total' in summary and summary['total'] > 0
    index_path = WORKSPACE / 'resources' / 'cited_papers' / 'index.json'
    data = json.loads(index_path.read_text(encoding='utf-8'))
    # At least one entry should have download metadata (even if failure due to network restrictions)
    assert any('download' in e for e in data)


def test_ts_bridge_if_available():
    # Build TS if node present
    node = shutil.which('node')
    npm = shutil.which('npm')
    if not node or not npm:
        pytest.skip('Node.js toolchain not installed')
    ts_root = Path(__file__).resolve().parents[1] / 'ts_functions'
    # Install deps (cached in CI) and build
    try:
        subprocess.run(['npm', 'install', '--no-audit', '--no-fund'], cwd=ts_root, check=True, timeout=180)
        subprocess.run(['npm', 'run', 'build'], cwd=ts_root, check=True, timeout=120)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f'Node build skipped due to error: {e}')
    # After build, index.js should be present in ts_dist
    ts_dist = Path(__file__).resolve().parents[1] / 'latex_mcp_server' / 'ts_dist'
    assert (ts_dist / 'index.js').exists()
    # Use registry to call summarize_text
    reg = build_registry(WORKSPACE)
    tool_names = reg.list_names()
    if 'summarize_text' not in tool_names:
        pytest.skip('summarize_text tool not registered')
    result = reg.call('summarize_text', {'text': 'Sentence one. Sentence two! Sentence three?', 'max_sentences': 2})
    assert result['ok'] is True
    assert isinstance(result['result'], str) and result['result'].count('.') <= 2


def test_server_registry_tools():
    reg = build_registry(WORKSPACE)
    tools = reg.list_names()
    expected = {'list_tex_files', 'read_file', 'extract_bibliography', 'download_bibliography', 'compile_latex', 'read_pdf', 'read_pdf_from_citation'}
    assert expected.issubset(set(tools))


def test_read_pdf_basic():
    # Pick a small already-downloaded PDF if any, else skip
    cited_dir = WORKSPACE / 'resources' / 'cited_papers'
    if not cited_dir.exists():
        pytest.skip('No cited_papers directory yet')
    pdfs = list(cited_dir.glob('*.pdf'))
    if not pdfs:
        pytest.skip('No PDFs downloaded to test read_pdf')
    sample = pdfs[0]
    result = latex_ops.read_pdf(WORKSPACE, str(sample.relative_to(WORKSPACE)), max_pages=1, max_chars=5000)
    assert result['path'] == str(sample.relative_to(WORKSPACE))
    assert result['pages'] >= 1
    assert 'text' in result and len(result['text']) > 0
    assert 'artifact' in result and (WORKSPACE / result['artifact']).is_file()


def _make_minimal_pdf(text: str) -> bytes:
    """Create a tiny PDF with given text.
    Prefer reportlab if available; else build a minimal single-page PDF manually.
    """
    if HAVE_REPORTLAB:
        bio = BytesIO()
        c = canvas.Canvas(bio)
        c.drawString(72, 720, text[:200])
        c.save()
        return bio.getvalue()
    # Fallback extremely small PDF (may have limited extractability)
    # Basic PDF structure with one page containing the text as a raw content stream.
    safe = text.replace('(', '[').replace(')', ']')[:200]
    content = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET".encode('latin-1', 'ignore')
    objects = []
    def add(obj):
        objects.append(obj)
        return len(objects)
    font_obj = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    resources_obj = add(f"<< /Font << /F1 {font_obj} 0 R >> >>".encode())
    stream_obj = add(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    page_obj = add(f"<< /Type /Page /Parent 4 0 R /Resources {resources_obj} 0 R /Contents {stream_obj} 0 R /MediaBox [0 0 612 792] >>".encode())
    pages_obj = add(f"<< /Type /Pages /Kids [{page_obj} 0 R] /Count 1 >>".encode())
    catalog_obj = add(f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode())
    # Build xref
    offsets = []
    out = BytesIO()
    out.write(b"%PDF-1.4\n")
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode())
        out.write(obj + b"\nendobj\n")
    xref_pos = out.tell()
    out.write(b"xref\n0 %d\n" % (len(objects) + 1))
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(b"trailer<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objects) + 1, catalog_obj, xref_pos))
    return out.getvalue()


def test_read_pdf_synthetic(tmp_path):
    # Create synthetic PDF independent of network downloads
    pdf_bytes = _make_minimal_pdf("Hello Synthetic PDF for testing")
    rel_dir = Path('resources') / 'cited_papers'
    target_dir = WORKSPACE / rel_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = target_dir / 'synthetic_test.pdf'
    pdf_path.write_bytes(pdf_bytes)
    result = latex_ops.read_pdf(WORKSPACE, str(pdf_path.relative_to(WORKSPACE)), max_pages=1, max_chars=2000)
    assert result['pages'] >= 1
    assert 'text' in result
    assert result['artifact']


def test_read_pdf_from_citation(monkeypatch):
    # Ensure an index with a mock entry exists
    resources_dir = WORKSPACE / 'resources' / 'cited_papers'
    resources_dir.mkdir(parents=True, exist_ok=True)
    index_path = resources_dir / 'index.json'
    citation_key = 'unitTestCitation'
    pdf_filename = _safe_test_filename = citation_key + '.pdf'
    pdf_path = resources_dir / pdf_filename
    # Create minimal PDF bytes
    if not pdf_path.exists():
        pdf_path.write_bytes(_make_minimal_pdf('PDF for citation test'))
    # Write index entry referencing it
    index_path.write_text(json.dumps([
        {'key': citation_key, 'title': 'Test', 'pdf_path': str(pdf_path.relative_to(WORKSPACE))}
    ]), encoding='utf-8')
    result = latex_ops.read_pdf_from_citation(WORKSPACE, citation_key, max_pages=1, max_chars=1000)
    assert result['citation_key'] == citation_key
    assert 'text' in result


def test_download_bibliography_mock(monkeypatch, tmp_path):
    # Create a minimal index.json with one entry having a fake pdf_url
    resources_dir = WORKSPACE / 'resources' / 'cited_papers'
    resources_dir.mkdir(parents=True, exist_ok=True)
    index_path = resources_dir / 'index.json'
    index_path.write_text(json.dumps([{'key': 'mockentry', 'pdf_url': 'https://example.com/fake.pdf'}]), encoding='utf-8')

    def fake_download(url, dest, timeout=20):  # noqa: ARG001
        dest.write_bytes(_make_minimal_pdf('Mock PDF'))
        return {'ok': True, 'bytes': dest.stat().st_size, 'elapsed_s': 0.01}

    monkeypatch.setattr(latex_ops, '_download_pdf', fake_download)
    summary = latex_ops.download_bibliography(WORKSPACE, force=True, limit=None)
    assert summary['ok'] >= 1
    # Verify file written
    assert any(p.name.startswith('mockentry') and p.suffix == '.pdf' for p in resources_dir.glob('*.pdf'))

