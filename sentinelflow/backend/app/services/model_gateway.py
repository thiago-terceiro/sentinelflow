from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar, cast, runtime_checkable

from app.config import Settings
from pydantic import BaseModel, SecretStr

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover
    ChatOpenAI = None

SchemaT = TypeVar("SchemaT", bound=BaseModel)
logger = logging.getLogger("sentinelflow.model_gateway")


def _as_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        value_dict = cast(dict[object, object], value)
        return {str(key): item for key, item in value_dict.items()}
    return {}


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _as_str(value: object, *, default: str) -> str:
    if isinstance(value, str):
        return value
    return default


class _StructuredInvoker(Protocol):
    async def ainvoke(self, input: object) -> object: ...


@runtime_checkable
class _AIMessageLike(Protocol):
    usage_metadata: object | None
    response_metadata: object | None
    content: object


@dataclass
class LLMCallResult[SchemaT: BaseModel]:
    value: SchemaT
    provider: str
    model_used: str
    deployment_id: str
    response_id: str | None
    prompt_template_id: str
    prompt_template_version: str
    prompt_template_sha256: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    latency_ms: float
    prompt_text: str
    output_text: str
    reasoning_text: str | None


class ModelGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self.settings.OPENAI_API_KEY and ChatOpenAI is not None)

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[SchemaT],
        prompt_template_id: str,
        prompt_template_version: str,
        prompt_template_sha256: str,
    ) -> LLMCallResult[SchemaT] | None:
        chat_openai_cls = ChatOpenAI
        if not self.enabled or chat_openai_cls is None or not self.settings.OPENAI_API_KEY:
            return None
        model = chat_openai_cls(
            model=self.settings.MODEL_NAME,
            api_key=SecretStr(self.settings.OPENAI_API_KEY),
            base_url=self.settings.MODEL_BASE_URL,
            timeout=self.settings.MODEL_TIMEOUT_SECONDS,
        )
        model_any = cast(Any, model)
        structured = cast(
            _StructuredInvoker,
            model_any.with_structured_output(schema, include_raw=True),
        )
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        attempts = self.settings.MODEL_MAX_RETRIES + 1
        for attempt in range(attempts):
            start = time.monotonic()
            try:
                raw_result_candidate = await structured.ainvoke(messages)
                latency_ms = (time.monotonic() - start) * 1000.0
                if not isinstance(raw_result_candidate, dict):
                    return None
                raw_result: dict[str, object] = cast(dict[str, object], raw_result_candidate)

                parsed_candidate = raw_result.get("parsed")
                if not isinstance(parsed_candidate, schema):
                    return None
                parsed = parsed_candidate

                ai_msg_candidate = raw_result.get("raw")
                ai_msg = ai_msg_candidate if isinstance(ai_msg_candidate, _AIMessageLike) else None

                usage = _as_mapping(ai_msg.usage_metadata if ai_msg is not None else None)
                token_details = _as_mapping(usage.get("output_token_details"))
                reasoning_tokens = _as_int(token_details.get("reasoning"))

                response_metadata = _as_mapping(
                    ai_msg.response_metadata if ai_msg is not None else None
                )
                response_id = response_metadata.get("id") or usage.get("response_id")
                model_used = _as_str(
                    response_metadata.get("model_name"),
                    default=self.settings.MODEL_NAME,
                )

                content = ai_msg.content if ai_msg is not None else ""
                output_text = content if isinstance(content, str) else str(content)
                reasoning_value = response_metadata.get("reasoning")
                reasoning_text = reasoning_value if isinstance(reasoning_value, str) else None

                return LLMCallResult(
                    value=parsed,
                    provider=self.settings.MODEL_PROVIDER,
                    model_used=model_used,
                    deployment_id=self.settings.MODEL_DEPLOYMENT_ID,
                    response_id=str(response_id) if response_id is not None else None,
                    prompt_template_id=prompt_template_id,
                    prompt_template_version=prompt_template_version,
                    prompt_template_sha256=prompt_template_sha256,
                    input_tokens=_as_int(usage.get("input_tokens")),
                    output_tokens=_as_int(usage.get("output_tokens")),
                    reasoning_tokens=reasoning_tokens,
                    latency_ms=round(latency_ms, 1),
                    prompt_text=user_prompt,
                    output_text=output_text,
                    reasoning_text=reasoning_text,
                )
            except Exception as exc:
                if attempt == attempts - 1:
                    logger.warning(
                        "LLM call failed after retries; using deterministic fallback.",
                        extra={
                            "event": "llm_call_failed",
                            "provider": self.settings.MODEL_PROVIDER,
                            "model": self.settings.MODEL_NAME,
                            "deployment_id": self.settings.MODEL_DEPLOYMENT_ID,
                            "attempts": attempts,
                            "error": str(exc),
                        },
                    )
                    return None
                await asyncio.sleep(
                    self.settings.MODEL_RETRY_BACKOFF_SECONDS * (2**attempt)
                )

    def metadata(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.settings.MODEL_PROVIDER,
            "model_name": self.settings.MODEL_NAME,
            "deployment_id": self.settings.MODEL_DEPLOYMENT_ID,
            "base_url": self.settings.MODEL_BASE_URL,
            "timeout_seconds": self.settings.MODEL_TIMEOUT_SECONDS,
            "max_retries": self.settings.MODEL_MAX_RETRIES,
        }
