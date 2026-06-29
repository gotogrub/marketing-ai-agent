from __future__ import annotations

from abc import ABC, abstractmethod
import json
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError
from uuid import uuid4

from marketing_agent.settings import Settings


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[dict]) -> str:
        raise NotImplementedError


class HuggingFaceProvider(LLMProvider):
    def __init__(self, token: str, model: str, base_url: str):
        if not token:
            raise ValueError("HF_TOKEN is required for Hugging Face")

        self.token = token
        self.model = model
        self.base_url = base_url.rstrip("/")

    def complete(self, messages: list[dict]) -> str:
        payload = {
            "model": self.model,
            "messages": role_content_messages(messages),
            "max_tokens": 700,
            "temperature": 0.25,
        }

        data = _post_json(
            url=f"{self.base_url}/chat/completions",
            payload=payload,
            headers={"Authorization": f"Bearer {self.token}"},
        )

        return _chat_completion_content(data, provider_name="Hugging Face")


class SberProvider(LLMProvider):
    def __init__(
        self,
        auth_key: str,
        model: str,
        scope: str,
        oauth_url: str,
        chat_url: str,
    ):
        if not auth_key:
            raise ValueError("SBER_AUTH_KEY is required for Sber/GigaChat")

        self.auth_key = auth_key
        self.model = model
        self.scope = scope
        self.oauth_url = oauth_url
        self.chat_url = chat_url

    def complete(self, messages: list[dict]) -> str:
        access_token = self._access_token()

        data = _post_json(
            url=self.chat_url,
            payload={
                "model": self.model,
                "messages": role_content_messages(messages),
                "temperature": 0.25,
                "max_tokens": 700,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        return _chat_completion_content(data, provider_name="Sber")

    def _access_token(self) -> str:
        body = parse.urlencode({"scope": self.scope}).encode("utf-8")

        req = request.Request(
            self.oauth_url,
            data=body,
            headers={
                "Authorization": f"Basic {self.auth_key}",
                "RqUID": str(uuid4()),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Sber OAuth failed with HTTP {exc.code}: {_safe_error_body(body_text)}") from exc

        token = payload.get("access_token")

        if not token:
            raise RuntimeError(f"Sber OAuth response has no access_token: {_safe_error_body(json.dumps(payload))}")

        return str(token)


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "huggingface":
        return HuggingFaceProvider(settings.hf_token, settings.hf_model, settings.hf_base_url)

    if settings.llm_provider == "sber":
        return SberProvider(
            auth_key=settings.sber_auth_key,
            model=settings.sber_model,
            scope=settings.sber_scope,
            oauth_url=settings.sber_oauth_url,
            chat_url=settings.sber_chat_url,
        )

    raise ValueError("Unsupported LLM_PROVIDER. Use `huggingface` or `sber`.")


def role_content_messages(messages: list[dict]) -> list[dict[str, str]]:
    rendered: list[dict[str, str]] = []

    for message in messages:
        content = message.get("content", "")

        if message.get("context"):
            context_json = json.dumps(message["context"], ensure_ascii=False, indent=2)
            content = f"{content}\n\nDeterministic tool context:\n{context_json}"

        rendered.append({"role": message.get("role", "user"), "content": content})

    return rendered


# подчёркивание в python не приватность а просто пометка что функция внутренняя
def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM request failed with HTTP {exc.code}: {_safe_error_body(body_text)}") from exc


def _chat_completion_content(data: dict[str, Any], provider_name: str) -> str:
    choices = data.get("choices") or []

    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")

        if content:
            return str(content).strip()

    raise RuntimeError(f"Unexpected {provider_name} response shape: {_safe_error_body(json.dumps(data))}")


def _safe_error_body(body: str) -> str:
    return body[:500].replace("\n", " ")
