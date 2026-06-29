from __future__ import annotations

import csv
from pathlib import Path

from marketing_agent.schemas import CampaignMetricsReport, MetricRow


CHANNEL_ALIASES = {
    "amazon": "Amazon",
    "email": "Email",
    "meta": "Meta",
    "shopify": "Shopify",
    "tik tok": "TikTok",
    "tiktok": "TikTok",
}


# сейчас читаем только csv из задания
# потом можно заменить это на витрину из ads api и orders api
def calculate_campaign_metrics(path: Path) -> CampaignMetricsReport:
    rows = []

    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "channel": canonical_channel(field(row, "channel")),
                    "campaign": field(row, "campaign", "campaign_name", "campaign_id"),
                    "spend": money(row.get("spend")),
                    "impressions": integer(row.get("impressions")),
                    "clicks": integer(row.get("clicks")),
                }
            )

    return CampaignMetricsReport(
        total=metric_row("total", rows),
        by_channel=group_metrics(rows, "channel"),
        by_campaign=group_metrics(rows, "campaign"),
        backend="csv",
    )


def spend_by_channel(path: Path) -> dict[str, float]:
    return {row.name: row.spend for row in calculate_campaign_metrics(path).by_channel}


def canonical_channel(value: object) -> str:
    text = str(value or "").strip()
    return CHANNEL_ALIASES.get(text.lower(), text)


def group_metrics(rows: list[dict], field_name: str) -> list[MetricRow]:
    groups: dict[str, list[dict]] = {}

    for row in rows:
        groups.setdefault(str(row[field_name]), []).append(row)

    return sorted(
        (metric_row(name, group_rows) for name, group_rows in groups.items()),
        key=lambda item: item.name.lower(),
    )


def metric_row(name: str, rows: list[dict]) -> MetricRow:
    spend = sum(row["spend"] for row in rows)
    impressions = sum(row["impressions"] for row in rows)
    clicks = sum(row["clicks"] for row in rows)
    ctr = clicks / impressions if impressions else 0.0
    cpc = spend / clicks if clicks else None

    return MetricRow(
        name=name,
        spend=spend,
        impressions=impressions,
        clicks=clicks,
        ctr=ctr,
        cpc=cpc,
    )


def field(row: dict, *names: str, default: str = "") -> str:
    for name in names:
        value = row.get(name)

        if value not in (None, ""):
            return str(value)

    return default


def money(value: object) -> float:
    if value in (None, ""):
        return 0.0

    return float(value)


def integer(value: object) -> int:
    if value in (None, ""):
        return 0

    return int(float(value))
