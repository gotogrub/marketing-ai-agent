from __future__ import annotations

from dataclasses import replace
import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from marketing_agent.service import MarketingAgentService
from marketing_agent.settings import Settings, load_settings


EXAMPLE_QUESTIONS = [
    "Какой tone of voice у VerdaVita и дай 3 заголовка под TikTok?",
    "Give me 3 Amazon listing headline ideas for PureRoot Creatine Pure.",
    "Сравни Meta и TikTok по CTR и CPC",
    "Какие каналы получают credit по last-touch и linear attribution?",
    "Who is the best singer, Freddie Mercury or Michael Jackson?",  # проверка валидатора на оффтоп
]


class MarketingAgentRequestHandler(BaseHTTPRequestHandler):
    settings: Settings
    static_path: Path

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/health":
            self._send_json(
                {
                    "ok": True,
                    "provider": self.settings.llm_provider,
                    "hf_token_present": bool(self.settings.hf_token),
                    "hf_model": self.settings.hf_model,
                    "sber_auth_present": bool(self.settings.sber_auth_key),
                    "sber_model": self.settings.sber_model,
                    "vector_backend": self.settings.vector_backend,
                }
            )
            return

        if parsed.path == "/api/examples":
            self._send_json({"examples": EXAMPLE_QUESTIONS})
            return

        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path != "/api/chat":
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        payload = self._read_json()
        question = str(payload.get("question", "")).strip()
        provider = str(payload.get("provider", self.settings.llm_provider)).strip().lower()

        try:
            settings = self._settings_for_provider(provider)
            service = MarketingAgentService(settings=settings)
            response = service.answer(question, user_id="ui")
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json(
            {
                "answer": response.answer,
                "intent": response.intent,
                "sources": response.sources,
                "debug": response.debug,
                "provider": provider,
            }
        )

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _settings_for_provider(self, provider: str) -> Settings:
        if provider in {"", "hf"}:
            provider = "huggingface"

        if provider == "gigachat":
            provider = "sber"

        if provider not in {"huggingface", "sber"}:
            raise ValueError(f"Unsupported provider: {provider}")

        return replace(self.settings, llm_provider=provider)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))

        if length <= 0:
            return {}

        raw = self.rfile.read(length).decode("utf-8")

        return json.loads(raw or "{}")

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        path = (self.static_path / relative).resolve()

        if not str(path).startswith(str(self.static_path.resolve())) or not path.exists() or not path.is_file():
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = path.read_bytes()

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(host: str, port: int, root_path: Path | None = None) -> ThreadingHTTPServer:
    root = root_path or Path.cwd()
    settings = load_settings(root)
    static_path = root / "static"

    class Handler(MarketingAgentRequestHandler):
        pass

    Handler.settings = settings
    Handler.static_path = static_path

    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Marketing Agent web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    server = create_server(args.host, args.port)
    url = f"http://{args.host}:{args.port}"
    print(f"Marketing Agent UI: {url}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Marketing Agent UI")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
