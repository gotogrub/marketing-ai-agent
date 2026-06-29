from __future__ import annotations

from marketing_agent.schemas import AttributionComparison, CampaignMetricsReport, RetrievedChunk


def brand_answer_messages(question: str, chunks: list[RetrievedChunk]) -> list[dict]:
    return [
        {
            "role": "system",
            "task": "brand_answer",
            "content": (
                "You are a marketing analyst. Use only retrieved brand context. "
                "Do not invent medical, cure, prevention, or guaranteed-effect claims. "
                "Give a concise answer with practical copy ideas and simple source notes."
            ),
            "context": {"chunks": [chunk.to_dict() for chunk in chunks]},
        },
        {"role": "user", "content": question},
    ]


def unsupported_brand_messages(question: str, requested_brand: str, available_brands: list[str]) -> list[dict]:
    return [
        {
            "role": "system",
            "task": "unsupported_brand",
            "content": (
                "You are a marketing analyst. The requested brand is not present in the brand KB. "
                "Do not answer using another brand's tone of voice. Say that the brand is unavailable, "
                "list available brands, and ask the user to pick one of them or add a brand document."
            ),
            "context": {
                "requested_brand": requested_brand,
                "available_brands": available_brands,
            },
        },
        {"role": "user", "content": question},
    ]


def analytics_answer_messages(question: str, report: CampaignMetricsReport) -> list[dict]:
    return [
        {
            "role": "system",
            "task": "analytics_answer",
            "content": (
                "You are a marketing analyst. Explain deterministic campaign metrics. "
                "Use only the provided report values. CTR is clicks / impressions. "
                "CPC is cost per click, never average check or order value. Format CTR as percent "
                "and CPC/spend as dollars. Higher CTR is better; lower CPC is cheaper and better "
                "for cost per click. Do not use external benchmarks. Do not claim a channel is "
                "globally more effective; only compare the sample by CTR and CPC."
            ),
            "context": {"report": report.to_dict()},
        },
        {"role": "user", "content": question},
    ]


def attribution_answer_messages(question: str, comparison: AttributionComparison) -> list[dict]:
    return [
        {
            "role": "system",
            "task": "attribution_answer",
            "content": (
                "You are a marketing analyst. Explain rule-based attribution results. "
                "Make clear that this is credit allocation, not causal attribution."
            ),
            "context": {"comparison": comparison.to_dict()},
        },
        {"role": "user", "content": question},
    ]


def clarifying_answer_messages(question: str) -> list[dict]:
    return [
        {
            "role": "system",
            "task": "clarifying_answer",
            "content": (
                "Ask the user to choose a supported marketing analytics question. "
                "Supported areas: brand knowledge, campaign metrics, attribution."
            ),
            "context": {},
        },
        {"role": "user", "content": question},
    ]
