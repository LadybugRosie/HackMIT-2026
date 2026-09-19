from __future__ import annotations

from typing import Any, Dict, Optional

import pytest
from fastapi.testclient import TestClient

from classroom.app import create_app
from classroom.settings import ClassroomSettings


@pytest.fixture
def capp(tmp_path) -> TestClient:
    cfg = ClassroomSettings(DB_PATH=str(tmp_path / "classroom.db"), SCRYPT_N=2**10)  # small N: fast tests
    return TestClient(create_app(cfg))


def signup(client: TestClient, email: str, role: str = "student", name: Optional[str] = None,
           class_code: Optional[str] = None, password: str = "Passw0rd!x") -> Dict[str, Any]:
    body = {"email": email, "password": password, "name": name or email.split("@")[0].title(), "role": role}
    if class_code:
        body["class_code"] = class_code
    r = client.post("/api/auth/signup", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def auth(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
