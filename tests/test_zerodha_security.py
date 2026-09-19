"""Zerodha link flow: CSRF state, purpose-bound connect token, token-at-rest encryption, auth rate limit."""
from sqlmodel import Session

from finsight import config
from finsight.zerodha import state as link_state
from finsight.zerodha.crypto import decrypt_token, encrypt_token


class TestState:
    def test_roundtrip(self):
        cookie, nonce = link_state.issue(42)
        assert link_state.verify(cookie, nonce) == 42

    def test_wrong_state_rejected(self):
        cookie, _ = link_state.issue(42)
        assert link_state.verify(cookie, "other-nonce") is None

    def test_tampered_user_id_rejected(self):
        cookie, nonce = link_state.issue(42)
        _, rest = cookie.split(".", 1)
        assert link_state.verify(f"7.{rest}", nonce) is None

    def test_missing_values(self):
        cookie, nonce = link_state.issue(1)
        assert link_state.verify(None, nonce) is None
        assert link_state.verify(cookie, None) is None
        assert link_state.verify("garbage", nonce) is None


class TestLinkFlow:
    def _configured(self, monkeypatch, scheme="https"):
        monkeypatch.setattr(config, "ZERODHA_API_KEY", "key")
        monkeypatch.setattr(config, "ZERODHA_API_SECRET", "sec")
        monkeypatch.setattr(config, "ZERODHA_REDIRECT_URI", f"{scheme}://example.test/zerodha/callback")
        import finsight.zerodha.client as client

        monkeypatch.setattr(client, "ZERODHA_API_KEY", "key")

    def test_connect_sets_signed_cookie_and_state_param(self, api_client, auth_headers, monkeypatch):
        self._configured(monkeypatch)
        r = api_client.get("/zerodha/connect", headers=auth_headers, follow_redirects=False)
        assert r.status_code == 302
        assert "redirect_params=state%3D" in r.headers["location"]
        cookie = r.cookies.get(link_state.COOKIE)
        nonce = r.headers["location"].split("state%3D")[1]
        assert link_state.verify(cookie, nonce) is not None
        assert "Secure" in r.headers["set-cookie"] and "HttpOnly" in r.headers["set-cookie"]

    def test_callback_rejects_link_without_matching_state(self, api_client, auth_headers, monkeypatch):
        self._configured(monkeypatch, scheme="http")
        api_client.get("/zerodha/connect", headers=auth_headers, follow_redirects=False)
        # attacker-supplied request_token, wrong/missing state
        r = api_client.get("/zerodha/callback", params={"request_token": "attacker", "status": "success", "state": "nope"})
        assert r.status_code == 400 and "not accepted" in r.text
        r = api_client.get("/zerodha/callback", params={"request_token": "attacker", "status": "success"})
        assert r.status_code == 400

    def test_callback_links_and_encrypts_with_valid_state(self, api_client, auth_headers, monkeypatch):
        # http: the test client is not TLS, and a Secure cookie would (correctly) not be sent back
        self._configured(monkeypatch, scheme="http")
        import finsight.zerodha.router as zr

        monkeypatch.setattr(zr, "exchange_request_token", lambda rt: {"access_token": "kite-token", "user_id": "AB1234"})
        r = api_client.get("/zerodha/connect", headers=auth_headers, follow_redirects=False)
        nonce = r.headers["location"].split("state%3D")[1]
        r = api_client.get("/zerodha/callback", params={"request_token": "rt", "status": "success", "state": nonce})
        assert r.status_code == 200 and "linked" in r.text

        import finsight.database.session as db
        from finsight.models import ZerodhaSession

        with Session(db.engine) as s:
            row = s.exec(__import__("sqlmodel").select(ZerodhaSession)).first()
            assert row.access_token.startswith("enc:") and "kite-token" not in row.access_token
            assert decrypt_token(row.access_token) == "kite-token"

    def test_connect_token_is_not_an_api_credential(self, api_client, auth_headers, monkeypatch):
        self._configured(monkeypatch)
        r = api_client.get("/zerodha/connect-url", headers=auth_headers)
        token = r.json()["connect_url"].split("token=")[1]
        assert api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
        r = api_client.get("/zerodha/connect-redirect", params={"token": token}, follow_redirects=False)
        assert r.status_code == 302

    def test_ordinary_jwt_cannot_start_connect_redirect(self, api_client, auth_headers):
        jwt = auth_headers["Authorization"].split()[1]
        r = api_client.get("/zerodha/connect-redirect", params={"token": jwt}, follow_redirects=False)
        assert r.status_code == 401


class TestCrypto:
    def test_roundtrip_and_prefix(self):
        enc = encrypt_token("abc")
        assert enc.startswith("enc:") and decrypt_token(enc) == "abc"

    def test_legacy_plaintext_passthrough(self):
        assert decrypt_token("plain-old-token") == "plain-old-token"

    def test_key_change_is_detected(self, monkeypatch):
        enc = encrypt_token("abc")
        monkeypatch.setattr(config, "SECRET_KEY", "a-different-key")
        try:
            decrypt_token(enc)
        except ValueError:
            return
        raise AssertionError("expected ValueError after key change")


class TestAuthRateLimit:
    def test_login_is_limited(self, api_client):
        body = {"email": "x@example.com", "password": "whatever-1"}
        codes = [api_client.post("/auth/login", json=body).status_code for _ in range(11)]
        assert codes[:10] == [401] * 10 and codes[10] == 429
