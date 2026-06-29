from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

from marketing_agent.schemas import Chunk, RetrievedChunk
from marketing_agent.settings import Settings


SUPPORTED_DOC_EXTENSIONS = {".docx", ".md", ".txt"}

# в нормальном микросервисе тут ещё надо внедрять pdf и ocr пайплайн
# и я бы реализовал всё это через регулярки и NLP, а не через жёсткие заголовки
# но пока что :')

NON_BRAND_TOKENS = {
    "amazon",
    "meta",
    "shopify",
    "tiktok",
    "tik tok",
    "ctr",
    "cpc",
    "tone",
}

SECTION_HINTS = {
    "tone_of_voice": {"tone", "voice", "тон", "голос", "tone of voice"},
    "products": {"product", "products", "продукт", "creatine", "greens", "magnesium"},
    "channel_notes": {"channel", "канал", "tiktok", "amazon", "listing", "headline", "заголов"},
    "restrictions": {"restriction", "claims", "claim", "огранич", "обещан", "cures", "леч"},
}

SECTION_ALIASES = {
    "audience": "audience",
    "аудитория": "audience",
    "channel notes": "channel_notes",
    "замаетки по каналам": "channel_notes",
    "заметки по каналам": "channel_notes",
    "products": "products",
    "продукты": "products",
    "restrictions": "restrictions",
    "ограничения": "restrictions",
    "tone of voice": "tone_of_voice",
}


# читаем docx без обязательной зависимости python docx
def load_docx(path: Path) -> str:
    return _load_docx_stdlib(path)


def _load_docx_stdlib(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")

    root = ET.fromstring(xml)
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraph_tag = f"{namespace}p"
    table_tag = f"{namespace}tbl"
    row_tag = f"{namespace}tr"
    cell_tag = f"{namespace}tc"
    text_tag = f"{namespace}t"
    body = root.find(f"{namespace}body")

    if body is None:
        return ""

    lines: list[str] = []

    for child in body:
        if child.tag == paragraph_tag:
            text = "".join(node.text or "" for node in child.iter(text_tag)).strip()

            if text:
                lines.append(text)

        elif child.tag == table_tag:
            for row in child.iter(row_tag):
                cells = []

                for cell in row.iter(cell_tag):
                    cell_text = " ".join(
                        text.strip()
                        for text in (node.text or "" for node in cell.iter(text_tag))
                        if text.strip()
                    )

                    if cell_text:
                        cells.append(cell_text)

                if cells:
                    lines.append(" | ".join(cells))

    return "\n".join(lines)


def load_document_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        return load_docx(path)

    return path.read_text(encoding="utf-8")


def _field_value(lines: list[str], field: str, default: str) -> str:
    prefix = f"{field.lower()}:"

    for line in lines:
        if line.lower().startswith(prefix):
            return line.split(":", 1)[1].strip()

    return default


def _clean_brand(value: str) -> str:
    cleaned = re.sub(r"\s*\([^)]*\)", "", value).strip()
    return cleaned or value


def _slug(value: str) -> str:
    normalized = value.lower().replace("ё", "е")
    normalized = re.sub(r"[^a-zа-я0-9]+", "_", normalized)
    return normalized.strip("_") or "section"


def _infer_brand(path: Path, lines: list[str]) -> str:
    value = _field_value(lines, "Brand", "")

    if value:
        return _clean_brand(value)

    value = _field_value(lines, "Бренд", "")

    if value:
        return _clean_brand(value)

    name = path.stem.lower()

    # пока что я плотно кринжанул и захардкодил список тестовых брендов 
    # понято что потом НЕОБХОДИМО будет сделать нормальный поиск по базе

    if "verdavita" in name:
        return "VerdaVita"

    if "pureroot" in name:
        return "PureRoot"

    return path.stem


def _infer_language(path: Path, lines: list[str]) -> str:
    value = _field_value(lines, "Language", "")

    if value:
        return value.lower()

    name = path.stem.lower()

    if "_ru" in name or name.endswith("ru"):
        return "ru"

    if "_en" in name or name.endswith("en"):
        return "en"

    return "unknown"


def _split_section_text(text: str, max_words: int = 110) -> list[str]:
    words = text.split()

    if len(words) <= max_words:
        return [text]

    chunks: list[str] = []

    for index in range(0, len(words), max_words):
        chunks.append(" ".join(words[index : index + max_words]))

    return chunks


def split_into_chunks(path: Path) -> list[Chunk]:
    text = load_document_text(path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    brand = _infer_brand(path, lines)
    language = _infer_language(path, lines)
    sections: list[tuple[str, list[str]]] = []
    current_section = "general"
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines

        if current_lines:
            sections.append((current_section, current_lines))
            current_lines = []

    for line in lines:
        lower = line.lower()

        if lower.startswith("brand:") or lower.startswith("language:") or lower.startswith("бренд:"):
            continue

        section = _section_from_heading(line)

        if section:
            flush()
            current_section = section
            continue

        if line.startswith("##"):
            flush()
            current_section = _slug(line.lstrip("#").strip())
            continue

        current_lines.append(line)

    flush()

    chunks: list[Chunk] = []
    brand_slug = _slug(brand)
    language_slug = _slug(language)

    for section, section_lines in sections:
        section_text = " ".join(section_lines)

        for index, chunk_text in enumerate(_split_section_text(section_text), start=1):
            chunk_id = f"brand_{brand_slug}_{language_slug}__{section}__{index:03d}"
            chunks.append(
                Chunk(
                    id=chunk_id,
                    text=chunk_text,
                    brand=brand,
                    language=language,
                    section=section,
                    source_file=path.name,
                )
            )
    return chunks


def load_brand_chunks(data_path: Path) -> list[Chunk]:
    chunks: list[Chunk] = []

    for path in sorted(data_path.glob("brand_*")):
        if path.suffix.lower() in SUPPORTED_DOC_EXTENSIONS:
            chunks.extend(split_into_chunks(path))

    return chunks


def available_brands(settings: Settings) -> list[str]:
    brands = {_clean_brand(chunk.brand) for chunk in load_brand_chunks(settings.brand_docs_path)}
    return sorted(brand for brand in brands if brand)


def requested_brand_status(question: str, settings: Settings) -> tuple[str | None, bool, list[str]]:
    brands = available_brands(settings)
    normalized_question = _brand_match_value(question)

    for brand in brands:
        if _brand_match_value(brand) in normalized_question:
            return brand, True, brands

    requested = _extract_brand_candidate(question)

    if not requested:
        return None, False, brands

    for brand in brands:
        if _same_brand(requested, brand):
            return brand, True, brands

    return requested, False, brands


class FallbackVectorStore:
    def __init__(self, settings: Settings):
        self.path = settings.chroma_path / f"{settings.chroma_collection}_fallback.json"

    def has_data(self) -> bool:
        return self.path.exists() and self.path.stat().st_size > 0

    def upsert(self, chunks: list[Chunk]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(chunk) for chunk in chunks]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load(self) -> list[Chunk]:
        if not self.has_data():
            return []

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return [Chunk(**item) for item in payload]

    def search(self, question: str, top_k: int = 5) -> list[RetrievedChunk]:
        q_tokens = _tokens(question)
        scored = [
            RetrievedChunk(
                text=chunk.text,
                brand=chunk.brand,
                section=chunk.section,
                source_file=chunk.source_file,
                score=_score_chunk(q_tokens, chunk),
            )
            for chunk in self._load()
        ]
        scored.sort(key=lambda item: item.score, reverse=True)

        return [item for item in scored[:top_k] if item.score > 0]


class ChromaVectorStore:
    def __init__(self, settings: Settings):
        import chromadb  # type: ignore

        embedding_function = None
        try:
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction  # type: ignore

            embedding_function = SentenceTransformerEmbeddingFunction(model_name=settings.embedding_model)
        except Exception:
            embedding_function = None

        settings.chroma_path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(settings.chroma_path))
        self.collection = self.client.get_or_create_collection(
            name=settings.chroma_collection,
            embedding_function=embedding_function,
        )

    def has_data(self) -> bool:
        return self.collection.count() > 0

    def upsert(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return

        self.collection.upsert(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[chunk.to_metadata() for chunk in chunks],
        )

    def search(self, question: str, top_k: int = 5) -> list[RetrievedChunk]:
        result = self.collection.query(query_texts=[question], n_results=top_k)
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0] or [0.0 for _ in documents]
        chunks: list[RetrievedChunk] = []

        for document, metadata, distance in zip(documents, metadatas, distances):
            score = 1.0 / (1.0 + float(distance))
            chunks.append(
                RetrievedChunk(
                    text=document,
                    brand=str(metadata.get("brand", "")),
                    section=str(metadata.get("section", "")),
                    source_file=str(metadata.get("source_file", "")),
                    score=score,
                )
            )

        return chunks


def _select_store(settings: Settings) -> FallbackVectorStore | ChromaVectorStore:
    if settings.vector_backend == "fallback":
        return FallbackVectorStore(settings)

    try:
        return ChromaVectorStore(settings)
    except Exception as exc:
        if settings.vector_backend == "chroma":
            raise RuntimeError(f"Chroma backend is not available: {exc}") from exc

        return FallbackVectorStore(settings)


def ingest_brand_kb(settings: Settings) -> int:
    chunks = load_brand_chunks(settings.brand_docs_path)
    store = _select_store(settings)
    store.upsert(chunks)

    if not isinstance(store, FallbackVectorStore):
        # локальная копия на случай если chroma потом сдохнет
        FallbackVectorStore(settings).upsert(chunks)

    return len(chunks)


def search_brand_kb(question: str, settings: Settings, top_k: int = 5) -> list[RetrievedChunk]:
    store = _select_store(settings)

    if not store.has_data():
        ingest_brand_kb(settings)

    results = store.search(question, top_k=top_k)
    target_brand = _target_brand(question)

    if target_brand:
        branded = [chunk for chunk in results if _same_brand(chunk.brand, target_brand)]

        if branded:
            return branded

    return results


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-zа-я0-9]+", value.lower().replace("ё", "е")))


def _score_chunk(question_tokens: set[str], chunk: Chunk) -> float:
    haystack = " ".join([chunk.text, chunk.brand, chunk.section, chunk.source_file])
    chunk_tokens = _tokens(haystack)
    overlap = len(question_tokens & chunk_tokens)
    score = float(overlap)
    brand_token = _slug(chunk.brand).replace("_", "")
    compact_question = "".join(question_tokens)

    if brand_token and brand_token in compact_question:
        score += 3.0

    for section, hints in SECTION_HINTS.items():
        if chunk.section == section and (question_tokens & hints):
            score += 2.0

    if "tiktok" in question_tokens and chunk.section == "channel_notes":
        score += 2.0

    if "amazon" in question_tokens and chunk.section == "channel_notes":
        score += 2.0

    return score


def _section_from_heading(line: str) -> str | None:
    if line.startswith("##"):
        return _slug(line.lstrip("#").strip())

    normalized = line.lower().replace("ё", "е").strip(" :")
    return SECTION_ALIASES.get(normalized)


def _target_brand(question: str) -> str | None:
    normalized = question.lower()

    if "verdavita" in normalized:
        return "VerdaVita"

    if "pureroot" in normalized:
        return "PureRoot"

    return None


def _same_brand(left: str, right: str) -> bool:
    left_value = _brand_match_value(left)
    right_value = _brand_match_value(right)
    return left_value == right_value or left_value in right_value or right_value in left_value


def _brand_match_value(value: str) -> str:
    return re.sub(r"[^a-zа-я0-9]+", "", _clean_brand(value).lower().replace("ё", "е"))


def _extract_brand_candidate(question: str) -> str | None:
    patterns = [
        r"\bу\s+([A-ZА-ЯЁ][\w&.-]*(?:\s+[A-ZА-ЯЁ][\w&.-]*)?)",
        r"\bбренд[а]?\s+([A-ZА-ЯЁ][\w&.-]*(?:\s+[A-ZА-ЯЁ][\w&.-]*)?)",
        r"\bfor\s+([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*)?)",
        r"\bof\s+([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*)?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, question)

        if not match:
            continue

        candidate = match.group(1).strip(" ?.,:;!\"'")

        if candidate.lower() not in NON_BRAND_TOKENS:
            return candidate

    return None
