import asyncio
from http.cookies import SimpleCookie
import json as json_module
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import _hash_password, _verify_password, normalize_email, _attempts
from app.core.database import get_db_session
from app.api.workspaces import get_workspace_session
from app.main import app
from app.models import Base
from app.models.identity import AuthSession, User
from app.models.workspace import Workspace


class LocalResponse:
    def __init__(self, status, headers, body):
        self.status_code = status
        self.headers = headers
        self.content = body
        self.text = body.decode("utf-8", "replace")

    def json(self):
        return json_module.loads(self.content)


class LocalAsgiClient:
    """Small no-lifespan ASGI test client for the restricted Windows runner."""

    def __init__(self, asgi_app):
        self.app = asgi_app
        self.cookies = {}

    def request(self, method, url, *, json_body=None, json=None, headers=None):
        if json_body is not None and json is not None:
            raise TypeError("Pass only one of json_body or json")
        if json is not None:
            json_body = json
        parsed = urlsplit(url)
        request_headers = {key.lower(): value for key, value in (headers or {}).items()}
        request_headers.setdefault("host", "testserver")
        if json_body is None:
            body = b""
        else:
            body = json_module.dumps(json_body).encode()
            request_headers.setdefault("content-type", "application/json")
            request_headers["content-length"] = str(len(body))
        if self.cookies:
            request_headers["cookie"] = "; ".join(f"{name}={value}" for name, value in self.cookies.items())
        messages = []
        received = False

        async def receive():
            nonlocal received
            if received:
                return {"type": "http.disconnect"}
            received = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            messages.append(message)

        path = parsed.path or "/"
        scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1", "method": method.upper(), "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": parsed.query.encode(), "root_path": "", "headers": [(key.encode(), value.encode()) for key, value in request_headers.items()], "client": ("127.0.0.1", 32100), "server": ("testserver", 80), "state": {}}
        asyncio.run(self.app(scope, receive, send))
        start = next(item for item in messages if item["type"] == "http.response.start")
        payload = b"".join(item.get("body", b"") for item in messages if item["type"] == "http.response.body")
        output_headers = {key.decode().lower(): value.decode() for key, value in start.get("headers", []) if key.lower() != b"set-cookie"}
        for key, value in start.get("headers", []):
            if key.lower() == b"set-cookie":
                parsed_cookie = SimpleCookie(); parsed_cookie.load(value.decode())
                for name, morsel in parsed_cookie.items():
                    if morsel["max-age"] == "0": self.cookies.pop(name, None)
                    else: self.cookies[name] = morsel.value
        return LocalResponse(start["status"], output_headers, payload)

    def get(self, url, **kwargs): return self.request("GET", url, **kwargs)
    def post(self, url, **kwargs): return self.request("POST", url, **kwargs)
    def put(self, url, **kwargs): return self.request("PUT", url, **kwargs)
    def close(self): pass


@pytest.fixture
def auth_client(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr("app.main.get_session_factory", lambda: factory)
    monkeypatch.setattr("app.core.config.settings.SOURCE_DOCUMENT_STORAGE_DIR", tmp_path / "private-sources")
    _attempts.clear()

    def override_session():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_workspace_session] = override_session
    client = LocalAsgiClient(app)
    yield client, factory
    client.close()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def register(client, email="ada@example.test"):
    return client.post("/api/v1/auth/register", json={
        "first_name": "Ada", "surname": "Lovelace", "email": email,
        "password": "Proofmint!Secure2026", "confirm_password": "Proofmint!Secure2026",
    })


def test_email_normalization_and_password_hashing_are_one_way():
    encoded = _hash_password("Proofmint!Secure2026")
    assert encoded != "Proofmint!Secure2026"
    assert _verify_password("Proofmint!Secure2026", encoded)
    assert not _verify_password("Wrong!Password2026", encoded)
    assert normalize_email("  ADA@Example.Test ") == "ada@example.test"


def test_registration_login_profile_and_logout_use_revocable_cookie_sessions(auth_client):
    client, factory = auth_client
    assert client.get("/api/v1/workspaces/00000000-0000-4000-8000-000000000000").status_code == 401
    created = register(client)
    assert created.status_code == 201, created.text
    profile = created.json()["user"]
    assert profile["email"] == "ada@example.test"
    assert client.cookies.get("proofmint_session")
    with factory() as db:
        user = db.query(User).filter_by(email="ada@example.test").one()
        assert user.password_hash != "Proofmint!Secure2026"
        workspace = Workspace(kind="session", owner_user_id=user.id)
        db.add(workspace)
        db.commit()
        workspace_id = workspace.id
    assert client.get(f"/api/v1/workspaces/{workspace_id}").status_code == 200
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": client.cookies.get("proofmint_csrf")}).status_code == 200
    assert client.get(f"/api/v1/workspaces/{workspace_id}").status_code == 401


def test_users_cannot_read_other_users_workspaces_and_judges_are_confined(auth_client):
    client_a, factory = auth_client
    assert register(client_a, "ada@example.test").status_code == 201
    with factory() as db:
        user_a = db.query(User).filter_by(email="ada@example.test").one()
        workspace_a = Workspace(kind="session", owner_user_id=user_a.id)
        db.add(workspace_a)
        db.commit()
        workspace_a_id = workspace_a.id
    client_b = LocalAsgiClient(app)
    assert register(client_b, "grace@example.test").status_code == 201
    assert client_a.get(f"/api/v1/workspaces/{workspace_a_id}").status_code == 200
    assert client_b.get(f"/api/v1/workspaces/{workspace_a_id}").status_code == 404
    judge = LocalAsgiClient(app)
    started = judge.post("/api/v1/auth/judge")
    assert started.status_code == 200, started.text
    assert started.json()["label"] == "Judge — Demonstration Access"
    demo_workspace = started.json()["workspace_id"]
    workspace_response = judge.get(f"/api/v1/workspaces/{demo_workspace}")
    assert workspace_response.status_code == 200
    workspace_body = workspace_response.json()
    assert workspace_body["documents"] == []
    assert workspace_body["latest_audit_id"] is None
    assert judge.get(f"/api/v1/workspaces/{workspace_a_id}").status_code == 404
    assert client_a.get(f"/api/v1/workspaces/{demo_workspace}").status_code == 404
    data = judge.get("/api/v1/auth/me").json()
    assert data["role"] == "judge" and data["profile"] is None
    assert judge.post("/api/v1/auth/logout", headers={"X-CSRF-Token": judge.cookies.get("proofmint_csrf")}).status_code == 200
    assert judge.get(f"/api/v1/workspaces/{demo_workspace}").status_code == 401


def test_registration_validation_and_generic_login_failure(auth_client):
    client, _factory = auth_client
    invalid = client.post("/api/v1/auth/register", json={"first_name": "Ada", "surname": "", "email": "bad", "password": "short", "confirm_password": "short"})
    assert invalid.status_code == 422
    denied = client.post("/api/v1/auth/login", json={"email": "nobody@example.test", "password": "wrong"})
    assert denied.status_code == 401
    assert denied.json()["detail"] == "Email or password is incorrect."


def test_google_sign_in_fails_closed_without_provider_configuration(auth_client, monkeypatch):
    client, _factory = auth_client
    monkeypatch.setattr("app.core.config.settings.GOOGLE_AUTH_ENABLED", False)
    disabled = client.get("/api/v1/auth/google/start")
    assert disabled.status_code == 503
    assert "domain is not currently supported" in disabled.json()["detail"]
    monkeypatch.setattr("app.core.config.settings.GOOGLE_AUTH_ENABLED", True)
    monkeypatch.setattr("app.core.config.settings.GOOGLE_CLIENT_ID", None)
    monkeypatch.setattr("app.core.config.settings.GOOGLE_REDIRECT_URI", None)
    response = client.get("/api/v1/auth/google/start")
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_workspace_authorization_supports_path_and_query_contexts_and_fails_closed(auth_client):
    owner_client, factory = auth_client
    assert register(owner_client, "owner@example.test").status_code == 201
    with factory() as db:
        owner = db.query(User).filter_by(email="owner@example.test").one()
        owner_workspace = Workspace(kind="session", owner_user_id=owner.id)
        db.add(owner_workspace)
        db.commit()
        owner_workspace_id = owner_workspace.id

    other_client = LocalAsgiClient(app)
    assert register(other_client, "other@example.test").status_code == 201
    assert owner_client.get(f"/api/v1/workspaces/{owner_workspace_id}").status_code == 200
    assert other_client.get(f"/api/v1/workspaces/{owner_workspace_id}").status_code == 404
    assert owner_client.get(f"/api/v1/guidelines/not-a-uuid/rules?workspace_id={owner_workspace_id}").status_code in {404, 422}
    assert owner_client.get("/api/v1/workspaces/not-a-uuid").status_code == 404

    judge_a = LocalAsgiClient(app)
    judge_b = LocalAsgiClient(app)
    started_a = judge_a.post("/api/v1/auth/judge")
    started_b = judge_b.post("/api/v1/auth/judge")
    assert started_a.status_code == started_b.status_code == 200
    workspace_a = started_a.json()["workspace_id"]
    workspace_b = started_b.json()["workspace_id"]
    assert judge_a.get(f"/api/v1/workspaces/{workspace_a}").status_code == 200
    assert judge_b.get(f"/api/v1/workspaces/{workspace_a}").status_code == 404
    assert judge_a.get(f"/api/v1/guidelines/not-a-uuid/rules?workspace_id={workspace_a}").status_code in {404, 422}
    unauthenticated = LocalAsgiClient(app)
    assert unauthenticated.get(f"/api/v1/workspaces/{workspace_a}").status_code == 401
    assert workspace_a != workspace_b
