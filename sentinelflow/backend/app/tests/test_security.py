from types import SimpleNamespace
from typing import Annotated

import jwt
import pytest
from app.errors import install_error_handlers
from app.security import DEV_TOKENS, Principal, Role, get_principal
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

PrincipalDep = Annotated[Principal, Depends(get_principal)]


def build_settings(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "APP_ENV": "development",
        "AUTH_JWT_SECRET": None,
        "AUTH_ALGORITHM": "HS256",
        "AUTH_ALLOWED_ALGORITHMS": ["RS256", "ES256", "PS256", "HS256"],
        "AUTH_AUDIENCE": "sentinelflow-api",
        "AUTH_ISSUER": "sentinelflow-dev",
        "AUTH_OIDC_ISSUER": None,
        "AUTH_OIDC_DISCOVERY_URL": None,
        "AUTH_JWKS_URL": None,
        "AUTH_RESOURCE_CLIENT_ID": None,
        "AUTH_ROLE_MAP": {},
        "AUTH_ALLOW_DEV_TOKENS": True,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_dev_tokens_exist() -> None:
    assert "dev-investigator" in DEV_TOKENS
    assert "dev-reviewer" in DEV_TOKENS
    assert "dev-auditor" in DEV_TOKENS


def test_get_principal_accepts_authorization_header() -> None:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/protected")
    async def protected(principal: PrincipalDep) -> dict[str, str]:
        return {"user_id": principal.user_id}

    client = TestClient(app)

    response = client.get("/protected", headers={"Authorization": "Bearer dev-investigator"})

    assert response.status_code == 200
    assert response.json() == {"user_id": "investigator-001"}


def test_get_principal_rejects_query_string_token() -> None:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/protected")
    async def protected(principal: PrincipalDep) -> dict[str, str]:
        return {"user_id": principal.user_id}

    client = TestClient(app)

    response = client.get("/protected?token=dev-investigator")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_get_principal_accepts_valid_jwt_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jwt_secret = "test-secret-32-bytes-minimum-for-hs256"
    monkeypatch.setattr(
        "app.security.get_settings",
        lambda: build_settings(
            APP_ENV="production",
            AUTH_JWT_SECRET=jwt_secret,
            AUTH_ALLOW_DEV_TOKENS=False,
        ),
    )
    token = jwt.encode(
        {
            "sub": "reviewer-777",
            "roles": ["reviewer"],
            "aud": "sentinelflow-api",
            "iss": "sentinelflow-dev",
        },
        jwt_secret,
        algorithm="HS256",
    )

    app = FastAPI()
    install_error_handlers(app)

    @app.get("/protected")
    async def protected(principal: PrincipalDep) -> dict[str, str]:
        return {"user_id": principal.user_id}

    client = TestClient(app)

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"user_id": "reviewer-777"}


def test_get_principal_rejects_dev_token_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jwt_secret = "test-secret-32-bytes-minimum-for-hs256"
    monkeypatch.setattr(
        "app.security.get_settings",
        lambda: build_settings(
            APP_ENV="production",
            AUTH_JWT_SECRET=jwt_secret,
            AUTH_ALLOW_DEV_TOKENS=False,
        ),
    )

    app = FastAPI()
    install_error_handlers(app)

    @app.get("/protected")
    async def protected(principal: PrincipalDep) -> dict[str, str]:
        return {"user_id": principal.user_id}

    client = TestClient(app)

    response = client.get("/protected", headers={"Authorization": "Bearer dev-reviewer"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_get_principal_extracts_keycloak_realm_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jwt_secret = "test-secret-32-bytes-minimum-for-hs256"
    monkeypatch.setattr(
        "app.security.get_settings",
        lambda: build_settings(
            APP_ENV="production",
            AUTH_JWT_SECRET=jwt_secret,
            AUTH_ALLOW_DEV_TOKENS=False,
        ),
    )
    token = jwt.encode(
        {
            "sub": "reviewer-888",
            "realm_access": {"roles": ["reviewer"]},
            "aud": "sentinelflow-api",
            "iss": "sentinelflow-dev",
        },
        jwt_secret,
        algorithm="HS256",
    )

    app = FastAPI()
    install_error_handlers(app)

    @app.get("/protected")
    async def protected(principal: PrincipalDep) -> dict[str, list[str]]:
        return {"roles": sorted(role.value for role in principal.roles)}

    client = TestClient(app)

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"roles": ["reviewer"]}


def test_get_principal_applies_role_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jwt_secret = "test-secret-32-bytes-minimum-for-hs256"
    monkeypatch.setattr(
        "app.security.get_settings",
        lambda: build_settings(
            APP_ENV="production",
            AUTH_JWT_SECRET=jwt_secret,
            AUTH_ROLE_MAP={"group:fraud-auditors": "auditor"},
            AUTH_ALLOW_DEV_TOKENS=False,
        ),
    )
    token = jwt.encode(
        {
            "sub": "auditor-123",
            "groups": ["group:fraud-auditors"],
            "aud": "sentinelflow-api",
            "iss": "sentinelflow-dev",
        },
        jwt_secret,
        algorithm="HS256",
    )

    app = FastAPI()
    install_error_handlers(app)

    @app.get("/protected")
    async def protected(principal: PrincipalDep) -> dict[str, list[str]]:
        return {"roles": sorted(role.value for role in principal.roles)}

    client = TestClient(app)

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"roles": ["auditor"]}


def test_auditor_role_has_access_to_auditing_and_disputes() -> None:
    principal = DEV_TOKENS["dev-auditor"]
    assert Role.AUDITOR in principal.roles
    principal.require_any(
        Role.INVESTIGATOR, Role.SENIOR_INVESTIGATOR, Role.REVIEWER, Role.AUDITOR, Role.ADMIN
    )
