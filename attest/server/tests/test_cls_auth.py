from classroom.security import hash_password, verify_password

from classroom_helpers import auth, capp, signup  # noqa: F401


def test_password_hashing_roundtrip():
    h = hash_password("correct horse", n=2**10)
    assert h.startswith("scrypt$1024$")
    assert verify_password("correct horse", h)
    assert not verify_password("wrong", h)
    assert not verify_password("x", "garbage")
    assert hash_password("same", n=2**10) != hash_password("same", n=2**10)  # salted


def test_signup_login_me_logout(capp):
    s = signup(capp, "ana@demo.edu", "student")
    assert s["user"]["role"] == "student" and s["user"]["email"] == "ana@demo.edu"

    me = capp.get("/api/auth/me", headers=auth(s["token"]))
    assert me.status_code == 200 and me.json()["name"] == "Ana"

    r = capp.post("/api/auth/login", json={"email": "ANA@demo.edu", "password": "Passw0rd!x"})
    assert r.status_code == 200 and r.json()["user"]["user_id"] == s["user"]["user_id"]
    token2 = r.json()["token"]
    assert token2 != s["token"]  # each login mints its own token

    assert capp.post("/api/auth/logout", headers=auth(token2)).json()["ok"] is True
    assert capp.get("/api/auth/me", headers=auth(token2)).status_code == 401
    assert capp.get("/api/auth/me", headers=auth(s["token"])).status_code == 200  # other device still valid


def test_duplicate_email_conflicts(capp):
    signup(capp, "dup@demo.edu")
    r = capp.post("/api/auth/signup", json={"email": "Dup@Demo.edu", "password": "Passw0rd!x", "name": "D", "role": "student"})
    assert r.status_code == 409


def test_bad_login_is_generic_401(capp):
    signup(capp, "x@demo.edu")
    assert capp.post("/api/auth/login", json={"email": "x@demo.edu", "password": "nope-nope"}).status_code == 401
    assert capp.post("/api/auth/login", json={"email": "ghost@demo.edu", "password": "nope-nope"}).status_code == 401


def test_validation(capp):
    assert capp.post("/api/auth/signup", json={"email": "not-an-email", "password": "Passw0rd!x", "name": "N"}).status_code == 422
    assert capp.post("/api/auth/signup", json={"email": "a@b.co", "password": "short", "name": "N"}).status_code == 422
    assert capp.get("/api/auth/me").status_code == 401
    assert capp.get("/api/auth/me", headers={"Authorization": "Token abc"}).status_code == 401


def test_tokens_are_hashed_at_rest(capp):
    s = signup(capp, "h@demo.edu")
    db = capp.app.state.db
    rows = db.all("SELECT token_hash FROM auth_tokens")
    assert len(rows) == 1 and rows[0]["token_hash"] != s["token"] and len(rows[0]["token_hash"]) == 64


def test_expired_token_rejected(capp):
    s = signup(capp, "e@demo.edu")
    capp.app.state.db.exec("UPDATE auth_tokens SET expires_ms = 1")
    assert capp.get("/api/auth/me", headers=auth(s["token"])).status_code == 401


def test_signup_with_invalid_class_code(capp):
    r = capp.post("/api/auth/signup", json={"email": "c@demo.edu", "password": "Passw0rd!x", "name": "C",
                                            "role": "student", "class_code": "ZZZZZZ"})
    assert r.status_code == 404


def test_attest_engine_mounted_in_same_app(capp):
    assert capp.get("/healthz").json()["ok"] is True
    r = capp.post("/v1/session/start", json={})
    assert r.status_code == 200 and len(r.json()["genesis"]) == 64
