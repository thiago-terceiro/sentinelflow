from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response

logger = logging.getLogger("sentinelflow.errors")


@dataclass(slots=True)
class AppError(Exception):
    code: str
    message: str
    status_code: int = status.HTTP_400_BAD_REQUEST


class AuthorizationError(AppError):
    def __init__(self, message: str = "You are not authorized to perform this action.") -> None:
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class NotFoundError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code=code, message=message, status_code=status.HTTP_404_NOT_FOUND)


def error_response(code: str, message: str, request_id: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        headers={"x-request-id": request_id},
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def attach_request_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.request_id = request.headers.get("x-request-id", f"req_{uuid4().hex[:12]}")
        response = await call_next(request)
        response.headers["x-request-id"] = request.state.request_id
        return response

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "Application error handled.",
            extra={
                "event": "app_error",
                "request_id": request.state.request_id,
                "path": request.url.path,
                "method": request.method,
                "error_code": exc.code,
                "status_code": exc.status_code,
                "principal_id": getattr(request.state, "principal_id", None),
                "principal_roles": getattr(request.state, "principal_roles", None),
            },
        )
        return error_response(exc.code, exc.message, request.state.request_id, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.info(
            "Validation error handled.",
            extra={
                "event": "validation_error",
                "request_id": request.state.request_id,
                "path": request.url.path,
                "method": request.method,
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "error_count": len(exc.errors()),
                "principal_id": getattr(request.state, "principal_id", None),
                "principal_roles": getattr(request.state, "principal_roles", None),
            },
        )
        return error_response(
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            request_id=request.state.request_id,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled exception.",
            extra={
                "event": "unhandled_exception",
                "request_id": request.state.request_id,
                "path": request.url.path,
                "method": request.method,
                "principal_id": getattr(request.state, "principal_id", None),
                "principal_roles": getattr(request.state, "principal_roles", None),
            },
            exc_info=exc,
        )
        return error_response(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
            request_id=request.state.request_id,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
