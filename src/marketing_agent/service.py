from __future__ import annotations

from marketing_agent.analytics import calculate_campaign_metrics
from marketing_agent.attribution import calculate_attribution_comparison
from marketing_agent.kb import requested_brand_status, search_brand_kb
from marketing_agent.llm import LLMProvider, build_llm_provider

from marketing_agent.prompts import (
    analytics_answer_messages,
    attribution_answer_messages,
    brand_answer_messages,
    clarifying_answer_messages,
    unsupported_brand_messages,
)

from marketing_agent.router import route_question
from marketing_agent.schemas import AgentResponse
from marketing_agent.settings import Settings, load_settings
from marketing_agent.storage import SessionStore


# я конечно фанат функционального программирования, но тут класс с состоянием инициализации и зависимостей выглядит
# лучше чем куча функций с передачей контекста
class MarketingAgentService:
    def __init__(
        self,
        settings: Settings | None = None,
        llm: LLMProvider | None = None,
        history: SessionStore | None = None,
    ):
        self.settings = settings or load_settings()
        self.llm = llm or build_llm_provider(self.settings)
        self.history = history if history is not None else SessionStore(self.settings.sessions_db_path)

    def answer(self, question: str, user_id: str = "demo") -> AgentResponse:
        text = (question or "").strip()

        if not text:
            return AgentResponse(
                answer="Задайте вопрос по brand knowledge, campaign metrics или attribution.",
                intent="unknown",
            )

        self.history.add_message(user_id, "user", text)
        intent = route_question(text)

        # центральный пайплайн агента без фреймворков и лишней магии
        if intent == "brand_kb":
            requested_brand, is_known_brand, available_brands = requested_brand_status(text, self.settings)

            if requested_brand and not is_known_brand:
                answer = self.llm.complete(unsupported_brand_messages(text, requested_brand, available_brands))
                response = AgentResponse(
                    answer=answer,
                    intent=intent,
                    sources=[],
                    debug={
                        "guardrail": "unknown_brand",
                        "requested_brand": requested_brand,
                        "available_brands": available_brands,
                    },
                )
            else:
                chunks = search_brand_kb(text, self.settings, top_k=5)
                answer = self.llm.complete(brand_answer_messages(text, chunks))
                response = AgentResponse(
                    answer=answer,
                    intent=intent,
                    sources=[chunk.to_dict() for chunk in chunks],
                    debug={"retrieved_chunks": len(chunks)},
                )

        elif intent == "campaign_metrics":
            report = calculate_campaign_metrics(self.settings.campaign_spend_path)
            answer = self.llm.complete(analytics_answer_messages(text, report))
            response = AgentResponse(
                answer=answer,
                intent=intent,
                debug={"metrics": report.to_dict()},
            )

        elif intent == "attribution":
            comparison = calculate_attribution_comparison(
                touchpoints_path=self.settings.touchpoints_path,
                campaign_spend_path=self.settings.campaign_spend_path,
                models=("last_touch", "linear"),
                window_days=14,
            )
            answer = self.llm.complete(attribution_answer_messages(text, comparison))
            response = AgentResponse(
                answer=answer,
                intent=intent,
                debug={"attribution": comparison.to_dict()},
            )

        else:
            answer = self.llm.complete(clarifying_answer_messages(text))
            response = AgentResponse(answer=answer, intent="unknown")

        self.history.add_message(user_id, "assistant", response.answer)
        return response
