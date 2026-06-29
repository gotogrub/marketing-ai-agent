from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _load_dotenv(root_path: Path) -> dict[str, str]:
    env_path = root_path / ".env"

    if not env_path.exists():
        return {}

    values: dict[str, str] = {}

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[len("export ") :].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            values[key] = value

    return values


def _env_value(env_file: dict[str, str], name: str, default: str) -> str:
    # env важнее .env для ci и локальных override
    return os.getenv(name, env_file.get(name, default))


def _path_from_env(env_file: dict[str, str], name: str, default: str, root_path: Path) -> Path:
    value = _env_value(env_file, name, default)
    path = Path(value).expanduser()

    return path if path.is_absolute() else root_path / path


@dataclass(frozen=True)
class Settings:
    root_path: Path
    llm_provider: str
    hf_token: str
    hf_model: str
    hf_base_url: str
    sber_auth_key: str
    sber_model: str
    sber_scope: str
    sber_oauth_url: str
    sber_chat_url: str
    chroma_path: Path
    chroma_collection: str
    vector_backend: str
    embedding_model: str
    brand_docs_path: Path
    campaign_spend_path: Path
    touchpoints_path: Path
    sessions_db_path: Path

    @classmethod
    def from_env(cls, root_path: Path | None = None) -> "Settings":
        root = root_path or Path(os.getenv("PROJECT_ROOT", Path.cwd())).resolve()
        env_file = _load_dotenv(root)
        provider = _normalize_provider(_env_value(env_file, "LLM_PROVIDER", "huggingface"))

        return cls(
            root_path=root,
            llm_provider=provider,
            hf_token=_env_value(env_file, "HF_TOKEN", ""),
            hf_model=_env_value(env_file, "HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct"),
            hf_base_url=_env_value(env_file, "HF_BASE_URL", "https://router.huggingface.co/v1"),
            sber_auth_key=_env_value(
                env_file,
                "SBER_AUTH_KEY",
                _env_value(env_file, "GIGACHAT_CREDENTIALS", ""),
            ),
            sber_model=_env_value(env_file, "SBER_MODEL", _env_value(env_file, "GIGACHAT_MODEL", "GigaChat")),
            sber_scope=_env_value(env_file, "SBER_SCOPE", "GIGACHAT_API_PERS"),
            sber_oauth_url=_env_value(
                env_file,
                "SBER_OAUTH_URL",
                "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
            ),
            sber_chat_url=_env_value(
                env_file,
                "SBER_CHAT_URL",
                "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
            ),
            chroma_path=_path_from_env(env_file, "CHROMA_PATH", "storage/chroma", root),
            chroma_collection=_env_value(env_file, "CHROMA_COLLECTION", "brand_kb"),
            vector_backend=_env_value(env_file, "VECTOR_BACKEND", "auto").lower(),
            embedding_model=_env_value(
                env_file,
                "EMBEDDING_MODEL",
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            ),
            brand_docs_path=_path_from_env(env_file, "BRAND_DOCS_PATH", "data", root),
            campaign_spend_path=_path_from_env(env_file, "CAMPAIGN_SPEND_PATH", "data/campaign_spend.csv", root),
            touchpoints_path=_path_from_env(env_file, "TOUCHPOINTS_PATH", "data/touchpoints.csv", root),
            sessions_db_path=_path_from_env(env_file, "SESSIONS_DB_PATH", "storage/sessions.sqlite", root),
        )


def load_settings(root_path: Path | None = None) -> Settings:
    return Settings.from_env(root_path)


# нормализуем старые алиасы из env
def _normalize_provider(value: str) -> str:
    provider = value.strip().lower()
    aliases = {
        "hf": "huggingface",
        "hugging_face": "huggingface",
        "sber": "sber",
        "gigachat": "sber",
        "giga": "sber",
    }

    normalized = aliases.get(provider, provider or "huggingface")

    if normalized not in {"huggingface", "sber"}:
        raise ValueError("LLM_PROVIDER must be `huggingface` or `sber`.")

    return normalized
