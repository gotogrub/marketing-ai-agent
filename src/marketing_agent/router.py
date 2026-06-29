from __future__ import annotations

import re

from marketing_agent.schemas import Intent


# аналог .reg файлов с регулярками

ATTRIBUTION_KEYWORDS = {
    "атрибуц",
    "attribution",
    "last-touch",
    "last touch",
    "first-touch",
    "first touch",
    "linear",
    "touchpoint",
    "touchpoints",
    "credit",
    "конверс",
    "roas",
}

CAMPAIGN_KEYWORDS = {
    "campaign",
    "campaigns",
    "meta",
    "tiktok",
    "amazon ads",
    "ctr",
    "cpc",
    "spend",
    "расход",
    "расходы",
    "показы",
    "клики",
    "канал",
    "каналы",
    "метрик",
    "сравни",
}

BRAND_KEYWORDS = {
    "tone",
    "voice",
    "tone of voice",
    "brand",
    "бренд",
    "брендов",
    "заголов",
    "headline",
    "listing",
    "pureroot",
    "verdavita",
    "creatine",
    "tiktok",
    "amazon",
    "claims",
    "обещан",
}


def _normalize(question: str) -> str:
    value = question.lower().replace("ё", "е")
    return re.sub(r"\s+", " ", value).strip()


def _has_any(text: str, keywords: set[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def route_question(question: str) -> Intent:
    q = _normalize(question)

    if not q:
        return "unknown"

    if _has_any(q, ATTRIBUTION_KEYWORDS):
        return "attribution"

    if _has_any(q, CAMPAIGN_KEYWORDS) and _has_any(
        q,
        {
            "ctr",
            "cpc",
            "spend",
            "расход",
            "расходы",
            "показы",
            "клики",
            "метрик",
            "сравни",
        },
    ):
        return "campaign_metrics"

    if _has_any(q, BRAND_KEYWORDS):
        return "brand_kb"

    return "unknown"
