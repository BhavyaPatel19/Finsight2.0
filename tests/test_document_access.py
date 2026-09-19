"""Documents are private to their uploader; the shared corpus (user_id NULL) is visible to everyone."""
import io

from finsight import config


def _login(api_client, email):
    api_client.post("/auth/register", json={"first_name": "A", "last_name": "B", "email": email, "password": "secret-123"})
    r = api_client.post("/auth/login", json={"email": email, "password": "secret-123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _upload(api_client, headers, name="call.htm"):
    r = api_client.post(
        "/ingestion/documents/upload",
        files={"file": (name, io.BytesIO(b"<html><body><p>hello</p></body></html>"), "text/html")},
        params={"symbol": "INFY", "doc_type": "concall"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["document_id"]


class TestPrivateDocuments:
    def test_other_user_cannot_see_read_or_delete(self, api_client, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "DOCUMENTS_DIR", tmp_path)
        alice, bob = _login(api_client, "alice@example.com"), _login(api_client, "bob@example.com")
        doc_id = _upload(api_client, alice)

        assert [d["id"] for d in api_client.get("/ingestion/documents", headers=alice).json()] == [doc_id]
        assert api_client.get("/ingestion/documents", headers=bob).json() == []
        assert api_client.get("/rag/available-documents", headers=bob).json() == []
        assert api_client.get("/credisentiment/available-documents", headers=bob).json() == []

        for method, path in [
            ("get", f"/ingestion/documents/{doc_id}"),
            ("get", f"/ingestion/documents/{doc_id}/pdf"),
            ("post", f"/ingestion/documents/{doc_id}/process"),
            ("delete", f"/ingestion/documents/{doc_id}"),
            ("post", f"/credisentiment/process/{doc_id}"),
            ("post", f"/sentiment/recompute/{doc_id}"),
            ("post", f"/credibility/extract-claims/{doc_id}"),
        ]:
            r = getattr(api_client, method)(path, headers=bob)
            assert r.status_code == 404, f"{method} {path} -> {r.status_code}"

        # Alice's document is untouched
        assert api_client.get(f"/ingestion/documents/{doc_id}/pdf", headers=alice).status_code == 200

    def test_rag_query_cannot_target_another_users_document(self, api_client, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "DOCUMENTS_DIR", tmp_path)
        alice, bob = _login(api_client, "alice@example.com"), _login(api_client, "bob@example.com")
        doc_id = _upload(api_client, alice)
        r = api_client.post("/rag/query", json={"question": "anything?", "document_ids": [doc_id]}, headers=bob)
        assert r.status_code == 404
        r = api_client.post("/rag/prepare", json={"document_ids": [doc_id]}, headers=bob)
        assert r.status_code == 404
        r = api_client.post("/credisentiment/walk-the-talk",
                            json={"claims_document_id": doc_id, "actuals_document_id": doc_id}, headers=bob)
        assert r.status_code == 404


class TestSharedCorpus:
    def test_seeded_document_is_visible_to_everyone(self, api_client):
        from sqlmodel import Session

        import finsight.database.session as db
        from finsight.models import Document

        with Session(db.engine) as s:
            s.add(Document(symbol="INFY", doc_type="concall", status="pending", user_id=None))
            s.commit()
        for email in ("alice@example.com", "bob@example.com"):
            h = _login(api_client, email)
            docs = api_client.get("/ingestion/documents", headers=h).json()
            assert len(docs) == 1 and docs[0]["symbol"] == "INFY"
