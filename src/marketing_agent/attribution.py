from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

from marketing_agent.analytics import canonical_channel, field, money, spend_by_channel
from marketing_agent.schemas import AttributionComparison, AttributionReport, AttributionRow


SUPPORTED_MODELS = {"last_touch", "first_touch", "linear"}


# это rule based credit allocation а не causal attribution
# тут можно добавить time decay и position based если появятся реальные данные
# но пока как есть
def calculate_attribution(
    touchpoints_path: Path,
    campaign_spend_path: Path | None = None,
    model: str = "last_touch",
    window_days: int = 14,
) -> AttributionReport:
    if model not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported attribution model: {model}")

    events = read_touchpoints(touchpoints_path)
    events_by_user: dict[str, list[dict]] = {}

    for event in events:
        events_by_user.setdefault(event["user_id"], []).append(event)

    for user_events in events_by_user.values():
        user_events.sort(key=lambda event: event["time"])

    revenue_by_channel: dict[str, float] = {}
    conversions_by_channel: dict[str, float] = {}

    for purchase in events:
        if purchase["event_type"] != "purchase" or purchase["revenue"] <= 0:
            continue

        start_time = purchase["time"] - timedelta(days=window_days)
        touches = [
            event
            for event in events_by_user[purchase["user_id"]]
            if event["event_type"] != "purchase"
            and event["channel"]
            and start_time <= event["time"] <= purchase["time"]
        ]

        for touch, weight in credit_touches(touches, model):
            revenue_by_channel[touch["channel"]] = (
                revenue_by_channel.get(touch["channel"], 0.0) + purchase["revenue"] * weight
            )
            conversions_by_channel[touch["channel"]] = (
                conversions_by_channel.get(touch["channel"], 0.0) + weight
            )

    spend = spend_by_channel(campaign_spend_path) if campaign_spend_path else {}

    rows = [
        AttributionRow(
            model=model,
            channel=channel,
            attributed_revenue=revenue,
            credited_conversions=conversions_by_channel.get(channel, 0.0),
            spend=spend.get(channel, 0.0),
            attributed_roas=(revenue / spend[channel]) if spend.get(channel, 0.0) else None,
        )
        for channel, revenue in sorted(revenue_by_channel.items())
    ]

    purchases_analyzed = sum(
        1
        for event in events
        if event["event_type"] == "purchase" and event["revenue"] > 0
    )

    return AttributionReport(
        model=model,
        rows=rows,
        purchases_analyzed=purchases_analyzed,
        window_days=window_days,
    )


def calculate_attribution_comparison(
    touchpoints_path: Path,
    campaign_spend_path: Path | None = None,
    models: tuple[str, ...] = ("last_touch", "linear"),
    window_days: int = 14,
) -> AttributionComparison:
    return AttributionComparison(
        reports=[
            calculate_attribution(
                touchpoints_path=touchpoints_path,
                campaign_spend_path=campaign_spend_path,
                model=model,
                window_days=window_days,
            )
            for model in models
        ]
    )


def read_touchpoints(path: Path) -> list[dict]:
    events = []

    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            events.append(
                {
                    "user_id": field(row, "user_id"),
                    "time": datetime.fromisoformat(field(row, "event_time", "timestamp")),
                    "event_type": field(row, "event_type").lower(),
                    "channel": canonical_channel(field(row, "channel")),
                    "campaign": field(row, "campaign", "campaign_id", "campaign_name"),
                    "revenue": money(row.get("revenue")),
                }
            )

    return events


def credit_touches(touches: list[dict], model: str) -> list[tuple[dict, float]]:
    if not touches:
        return []

    if model == "last_touch":
        return [(touches[-1], 1.0)]

    if model == "first_touch":
        return [(touches[0], 1.0)]

    weight = 1.0 / len(touches)

    return [(touch, weight) for touch in touches]
