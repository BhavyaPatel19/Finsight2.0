"""Auth endpoints end-to-end against the in-memory DB."""

REG = {"first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com", "password": "correct-horse"}


class TestRegister:
    def test_register_returns_user_without_hash(self, api_client):
        r = api_client.post("/auth/register", json=REG)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["email"] == "ada@example.com" and body["first_name"] == "Ada"
        assert "hashed_password" not in body and "password" not in body

    def test_duplicate_email_rejected(self, api_client):
        api_client.post("/auth/register", json=REG)
        r = api_client.post("/auth/register", json=REG)
        assert r.status_code == 400
        assert "already registered" in r.json()["detail"]

    def test_short_password_rejected(self, api_client):
        r = api_client.post("/auth/register", json={**REG, "password": "short"})
        assert r.status_code == 422
        assert "at least 8" in r.text

    def test_overlong_password_rejected(self, api_client):
        r = api_client.post("/auth/register", json={**REG, "password": "x" * 73})
        assert r.status_code == 422

    def test_invalid_email_rejected(self, api_client):
        r = api_client.post("/auth/register", json={**REG, "email": "not-an-email"})
        assert r.status_code == 422


class TestLogin:
    def test_login_then_me(self, api_client):
        api_client.post("/auth/register", json=REG)
        r = api_client.post("/auth/login", json={"email": REG["email"], "password": REG["password"]})
        assert r.status_code == 200
        token = r.json()["access_token"]
        me = api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200 and me.json()["email"] == REG["email"]

    def test_wrong_password(self, api_client):
        api_client.post("/auth/register", json=REG)
        r = api_client.post("/auth/login", json={"email": REG["email"], "password": "nope-nope"})
        assert r.status_code == 401

    def test_unknown_user(self, api_client):
        r = api_client.post("/auth/login", json={"email": "ghost@example.com", "password": "whatever1"})
        assert r.status_code == 401

    def test_garbage_token_rejected(self, api_client):
        r = api_client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
        assert r.status_code == 401

    def test_forged_token_with_other_key_rejected(self, api_client):
        from jose import jwt

        forged = jwt.encode({"sub": "1"}, "some-other-key", algorithm="HS256")
        r = api_client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
        assert r.status_code == 401
