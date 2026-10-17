from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Any, cast

import httpx
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWKClient, PyJWKClientError

from app.config import get_settings
from app.errors import AppError, AuthorizationError


class Role(StrEnum):
    INVESTIGATOR = "investigator"
    SENIOR_INVESTIGATOR = "senior_investigator"
    REVIEWER = "reviewer"
    AUDITOR = "auditor"
    ADMIN = "admin"


@dataclass(slots=True)
class Principal:
    user_id: str
    roles: set[Role]

    def require_any(self, *required_roles: Role) -> None:
        if not any(role in self.roles for role in required_roles):
            raise AuthorizationError()


bearer_scheme = HTTPBearer(auto_error=False)
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


DEV_TOKENS: dict[str, Principal] = {
    "dev-investigator": Principal("investigator-001", {Role.INVESTIGATOR}),
    "dev-senior": Principal("senior-001", {Role.SENIOR_INVESTIGATOR}),
    "dev-reviewer": Principal("reviewer-001", {Role.REVIEWER}),
    "dev-auditor": Principal("auditor-001", {Role.AUDITOR}),
    "dev-admin": Principal("admin-001", {Role.ADMIN}),
}


def _as_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    value_dict = cast(dict[object, object], value)
    return {str(key): item for key, item in value_dict.items()}


def _extract_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [item for item in value.split(" ") if item]
    if isinstance(value, (list, tuple)):
        return [item for item in value if isinstance(item, str)]
    return []


def _normalize_role_name(raw_role: str, role_map: dict[str, str]) -> str:
    mapped = role_map.get(raw_role, raw_role).strip().lower()
    if mapped.startswith("sentinelflow."):
        mapped = mapped.split(".", 1)[1]
    if mapped.startswith("role:"):
        mapped = mapped.split(":", 1)[1]
    return mapped.replace("-", "_").replace(" ", "_")


def _extract_roles(payload: dict[str, Any], resource_client_id: str | None) -> set[str]:
    raw_roles: set[str] = set()
    for item in _extract_strings(payload.get("roles")):
        raw_roles.add(item)
    for item in _extract_strings(payload.get("groups")):
        raw_roles.add(item)
    for item in _extract_strings(payload.get("scp")):
        raw_roles.add(item)

    realm_access = _as_mapping(payload.get("realm_access"))
    for item in _extract_strings(realm_access.get("roles")):
        raw_roles.add(item)

    resource_access = _as_mapping(payload.get("resource_access"))
    if resource_client_id:
        client_access = _as_mapping(resource_access.get(resource_client_id))
        for item in _extract_strings(client_access.get("roles")):
            raw_roles.add(item)

    return raw_roles


def _principal_from_payload(payload: dict[str, Any]) -> Principal:
    settings = get_settings()
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise AppError(
            code="UNAUTHENTICATED",
            message="Invalid access token.",
            status_code=401,
        )
    roles: set[Role] = set()
    for raw_role in _extract_roles(payload, settings.AUTH_RESOURCE_CLIENT_ID):
        normalized = _normalize_role_name(raw_role, settings.AUTH_ROLE_MAP)
        try:
            roles.add(Role(normalized))
        except ValueError:
            continue
    return Principal(user_id=subject, roles=roles)


def _default_discovery_url(issuer: str) -> str:
    return f"{issuer.rstrip('/')}/.well-known/openid-configuration"


@lru_cache(maxsize=16)
def _load_oidc_metadata(discovery_url: str) -> dict[str, Any]:
    response = httpx.get(discovery_url, timeout=5.0)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("OIDC discovery payload must be an object.")
    payload_dict = cast(dict[object, object], payload)
    return {str(key): item for key, item in payload_dict.items()}


def _resolve_oidc_metadata() -> dict[str, Any] | None:
    settings = get_settings()
    discovery_url = settings.AUTH_OIDC_DISCOVERY_URL
    if not discovery_url and settings.AUTH_OIDC_ISSUER:
        discovery_url = _default_discovery_url(settings.AUTH_OIDC_ISSUER)
    if not discovery_url:
        return None
    return _load_oidc_metadata(discovery_url)


@lru_cache(maxsize=16)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)


def _resolve_expected_issuer(metadata: dict[str, Any] | None) -> str:
    settings = get_settings()
    if settings.AUTH_OIDC_ISSUER:
        return settings.AUTH_OIDC_ISSUER
    if settings.AUTH_ISSUER != "sentinelflow-dev":
        return settings.AUTH_ISSUER
    if metadata and isinstance(metadata.get("issuer"), str):
        return str(metadata["issuer"])
    return settings.AUTH_ISSUER


def _decode_with_shared_secret(token: str) -> Principal:
    settings = get_settings()
    if not settings.AUTH_JWT_SECRET:
        raise AppError(
            code="AUTH_CONFIG_ERROR",
            message="AUTH_JWT_SECRET is required for HMAC tokens.",
            status_code=500,
        )
    payload = jwt.decode(
        token,
        settings.AUTH_JWT_SECRET,
        algorithms=settings.AUTH_ALLOWED_ALGORITHMS,
        audience=settings.AUTH_AUDIENCE,
        issuer=settings.AUTH_ISSUER,
    )
    return _principal_from_payload(_as_mapping(payload))


def _decode_with_jwks(token: str) -> Principal:
    settings = get_settings()
    metadata = _resolve_oidc_metadata()
    jwks_url = settings.AUTH_JWKS_URL
    if not jwks_url and metadata and isinstance(metadata.get("jwks_uri"), str):
        jwks_url = str(metadata["jwks_uri"])
    if not jwks_url:
        raise AppError(
            code="AUTH_CONFIG_ERROR",
            message="AUTH_JWKS_URL or OIDC discovery is required for asymmetric tokens.",
            status_code=500,
        )
    signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=settings.AUTH_ALLOWED_ALGORITHMS,
        audience=settings.AUTH_AUDIENCE,
        issuer=_resolve_expected_issuer(metadata),
    )
    return _principal_from_payload(_as_mapping(payload))


def _decode_jwt(token: str) -> Principal:
    settings = get_settings()
    header = jwt.get_unverified_header(token)
    algorithm = header.get("alg")
    if not isinstance(algorithm, str):
        raise AppError(
            code="UNAUTHENTICATED",
            message="Invalid access token.",
            status_code=401,
        )
    if algorithm not in set(settings.AUTH_ALLOWED_ALGORITHMS):
        raise AppError(
            code="UNAUTHENTICATED",
            message="Token algorithm is not allowed.",
            status_code=401,
        )
    if algorithm.startswith("HS"):
        return _decode_with_shared_secret(token)
    return _decode_with_jwks(token)


async def get_principal(
    request: Request,
    credentials: CredentialsDep,
) -> Principal:
    settings = get_settings()
    token = credentials.credentials if credentials else None
    if not token:
        raise AppError(
            code="UNAUTHENTICATED",
            message="Authentication is required.",
            status_code=401,
        )
    if (
        settings.AUTH_ALLOW_DEV_TOKENS
        and settings.APP_ENV in {"development", "test"}
        and token in DEV_TOKENS
    ):
        principal = DEV_TOKENS[token]
        request.state.principal_id = principal.user_id
        request.state.principal_roles = sorted(role.value for role in principal.roles)
        return principal
    try:
        principal = _decode_jwt(token)
        request.state.principal_id = principal.user_id
        request.state.principal_roles = sorted(role.value for role in principal.roles)
        return principal
    except (InvalidTokenError, PyJWKClientError, httpx.HTTPError, ValueError) as exc:
        raise AppError(
            code="UNAUTHENTICATED",
            message="Invalid access token.",
            status_code=401,
        ) from exc
