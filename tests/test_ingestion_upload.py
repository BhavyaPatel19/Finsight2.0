"""Upload endpoint: type/size/content checks and path sanitisation."""

import io

from finsight import config
from finsight.ingestion import uploads


def _upload(api_client, headers, filename, content, symbol="INFY", **fields):
    data = {"symbol": symbol, "doc_type": "concall", **fields}
    return api_client.post(
        "/ingestion/documents/upload",
        files={"file": (filename, io.BytesIO(content), "application/octet-stream")},
        params=data,
        headers=headers,
    )


class TestUpload:
    def test_html_upload_registers_pending_document(self, api_client, auth_headers, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "DOCUMENTS_DIR", tmp_path)
        r = _upload(api_client, auth_headers, "call.htm", b"<html><body><p>hi</p></body></html>")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending"
        saved = list(tmp_path.glob("INFY_*_call.htm"))
        assert len(saved) == 1

    def test_pdf_requires_pdf_magic(self, api_client, auth_headers, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "DOCUMENTS_DIR", tmp_path)
        r = _upload(api_client, auth_headers, "fake.pdf", b"<html>not a pdf</html>")
        assert r.status_code == 400 and "does not look like" in r.json()["detail"]
        r = _upload(api_client, auth_headers, "real.pdf", b"%PDF-1.4 minimal")
        assert r.status_code == 200

    def test_unsupported_extension(self, api_client, auth_headers):
        r = _upload(api_client, auth_headers, "macro.xlsm", b"zip")
        assert r.status_code == 400

    def test_size_cap(self, api_client, auth_headers, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "DOCUMENTS_DIR", tmp_path)
        monkeypatch.setattr(uploads, "MAX_UPLOAD_BYTES", 100)
        r = _upload(api_client, auth_headers, "big.txt", b"x" * 101)
        assert r.status_code == 413

    def test_symbol_and_filename_cannot_escape_documents_dir(self, api_client, auth_headers, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "DOCUMENTS_DIR", tmp_path)
        r = _upload(api_client, auth_headers, "../../evil.txt", b"hello", symbol="../../../tmp/x")
        assert r.status_code == 200, r.text
        saved = list(tmp_path.iterdir())
        assert len(saved) == 1 and saved[0].parent == tmp_path
        assert ".." not in saved[0].name and "/" not in saved[0].name

    def test_requires_auth(self, api_client):
        r = _upload(api_client, {}, "a.txt", b"x")
        assert r.status_code == 401


class TestCredisentimentUploadSharesRules:
    def test_traversal_blocked_on_second_endpoint(self, api_client, auth_headers, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "DOCUMENTS_DIR", tmp_path)
        r = api_client.post(
            "/credisentiment/upload",
            files={"file": ("../../evil.htm", io.BytesIO(b"<p>x</p>"), "text/html")},
            data={"symbol": "../etc", "doc_type": "concall"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        saved = list(tmp_path.iterdir())
        assert len(saved) == 1 and ".." not in saved[0].name

    def test_bad_type_rejected_on_second_endpoint(self, api_client, auth_headers):
        r = api_client.post(
            "/credisentiment/upload",
            files={"file": ("x.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
            data={"symbol": "INFY"},
            headers=auth_headers,
        )
        assert r.status_code == 400
