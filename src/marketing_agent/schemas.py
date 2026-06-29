from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Intent = Literal["brand_kb", "campaign_metrics", "attribution", "unknown"]


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    brand: str
    language: str
    section: str
    source_file: str

    def to_metadata(self) -> dict[str, str]:
        return {
            "brand": self.brand,
            "language": self.language,
            "section": self.section,
            "source_file": self.source_file,
        }


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    brand: str
    section: str
    source_file: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MetricRow:
    name: str
    spend: float
    impressions: int
    clicks: int
    ctr: float
    cpc: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CampaignMetricsReport:
    total: MetricRow
    by_channel: list[MetricRow]
    by_campaign: list[MetricRow]
    backend: str = "csv"

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total.to_dict(),
            "by_channel": [row.to_dict() for row in self.by_channel],
            "by_campaign": [row.to_dict() for row in self.by_campaign],
            "backend": self.backend,
        }


@dataclass(frozen=True)
class AttributionRow:
    model: str
    channel: str
    attributed_revenue: float
    credited_conversions: float
    spend: float
    attributed_roas: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AttributionReport:
    model: str
    rows: list[AttributionRow]
    purchases_analyzed: int
    window_days: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "rows": [row.to_dict() for row in self.rows],
            "purchases_analyzed": self.purchases_analyzed,
            "window_days": self.window_days,
        }


@dataclass(frozen=True)
class AttributionComparison:
    reports: list[AttributionReport]

    def to_dict(self) -> dict[str, Any]:
        return {"reports": [report.to_dict() for report in self.reports]}


@dataclass(frozen=True)
class AgentResponse:
    answer: str
    intent: Intent
    sources: list[dict[str, Any]] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)
