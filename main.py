from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from marketing_agent.kb import ingest_brand_kb
from marketing_agent.llm import HuggingFaceProvider, SberProvider
from marketing_agent.server import create_server
from marketing_agent.service import MarketingAgentService
from marketing_agent.settings import Settings, load_settings


COMMANDS = {"ask", "check-hf", "check-sber", "ingest", "ui"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Marketing AI Agent")
    parser.add_argument("command", nargs="?", default="ui")
    parser.add_argument("text", nargs="*")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    command = args.command
    text_parts = args.text

    if command not in COMMANDS:
        text_parts = [command, *text_parts]
        command = "ask"

    settings = load_settings(ROOT)

    if command == "ui":
        run_ui(args.host, args.port)
    elif command == "ask":
        question = " ".join(text_parts).strip() or "Сравни Meta и TikTok по CTR и CPC"
        print(MarketingAgentService(settings=settings).answer(question).answer)
    elif command == "ingest":
        count = ingest_brand_kb(settings)
        print(f"Ingested {count} brand KB chunks into {settings.chroma_path}")
    elif command == "check-hf":
        check_hugging_face(settings)
    elif command == "check-sber":
        check_sber(settings)


def run_ui(host: str, port: int) -> None:
    server = create_server(host=host, port=port, root_path=ROOT)
    print(f"Marketing Agent UI: http://{host}:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Marketing Agent UI")
    finally:
        server.server_close()


def check_hugging_face(settings: Settings) -> None:
    provider = HuggingFaceProvider(
        token=settings.hf_token,
        model=settings.hf_model,
        base_url=settings.hf_base_url,
    )
    answer = provider.complete(
        [
            {"role": "system", "content": "Answer in one short sentence."},
            {"role": "user", "content": "Say that the Hugging Face provider is connected."},
        ]
    )

    print(answer)


def check_sber(settings: Settings) -> None:
    provider = SberProvider(
        auth_key=settings.sber_auth_key,
        model=settings.sber_model,
        scope=settings.sber_scope,
        oauth_url=settings.sber_oauth_url,
        chat_url=settings.sber_chat_url,
    )
    answer = provider.complete(
        [
            {"role": "system", "content": "Answer in one short sentence."},
            {"role": "user", "content": "Say that the Sber provider is connected."},
        ]
    )

    print(answer)


if __name__ == "__main__":
    main()
