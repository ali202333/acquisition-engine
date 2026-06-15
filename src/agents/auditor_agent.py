"""The AI-Driven Pain-Point Analyzer."""
import asyncio
import json
import logging
import os
from typing import Optional

import openai

from src.config import Config
from src.models import BusinessProfile, DigitalStrategy, PainPoint

logger = logging.getLogger(__name__)

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")


def _load_prompt(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class AuditorAgent:
    """Uses LLM to analyze business profiles and generate strategies."""

    def __init__(self, llm_model: str, config: Config) -> None:
        self.llm_model = llm_model
        self.config = config
        self.client = openai.AsyncOpenAI(api_key=config.openai_api_key)
        self._token_usage = 0

    async def _chat(self, messages: list[dict[str, str]], temperature: Optional[float] = None) -> str:
        temp = temperature if temperature is not None else self.config.temperature
        try:
            response = await self.client.chat.completions.create(
                model=self.llm_model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temp,
                response_format={"type": "json_object"},
            )
            usage = response.usage
            if usage:
                self._token_usage += usage.total_tokens or 0
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("OpenAI API error: %s", exc)
            raise

    def _build_audit_messages(self, profile: BusinessProfile) -> list[dict[str, str]]:
        system = _load_prompt("audit_prompt.txt")
        user = json.dumps({
            "business": {
                "name": profile.business.name,
                "address": profile.business.address,
                "rating": profile.business.rating,
                "review_count": profile.business.review_count,
                "has_website": profile.business.has_website,
                "has_social_media": profile.business.has_social_media,
            },
            "seo": {
                "has_ssl": profile.seo.has_ssl,
                "mobile_friendly": profile.seo.mobile_friendly,
                "page_speed_score": profile.seo.page_speed_score,
                "meta_description_present": profile.seo.meta_description_present,
                "has_contact_page": profile.seo.has_contact_page,
                "has_menu_online": profile.seo.has_menu_online,
                "overall_score": profile.seo.overall_score,
            },
        }, indent=2)
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _build_proposal_messages(self, profile: BusinessProfile, pain_points: list[PainPoint]) -> list[dict[str, str]]:
        system = _load_prompt("proposal_prompt.txt")
        user = json.dumps({
            "business": profile.business.model_dump(mode="json"),
            "seo": profile.seo.model_dump(mode="json"),
            "social": profile.social.model_dump(mode="json"),
            "pain_points": [pp.model_dump(mode="json") for pp in pain_points],
        }, indent=2)
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    async def analyze(self, profile: BusinessProfile) -> tuple[list[PainPoint], DigitalStrategy]:
        """Run LLM audit and strategy generation with retries."""
        # --- Pain point analysis ---
        pain_points: list[PainPoint] = []
        for attempt in range(1, 4):
            try:
                content = await self._chat(self._build_audit_messages(profile))
                data = json.loads(content)
                raw_list = data if isinstance(data, list) else data.get("pain_points", [])
                pain_points = [PainPoint(**item) for item in raw_list]
                break
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                logger.warning("Audit JSON parse attempt %d failed: %s", attempt, exc)
                if attempt == 3:
                    logger.error("Audit failed after 3 attempts; returning empty pain points")
                    pain_points = []
            except Exception as exc:
                logger.error("Audit LLM error on attempt %d: %s", attempt, exc)
                if attempt == 3:
                    pain_points = []
                else:
                    await asyncio.sleep(1.5)

        # --- Strategy generation ---
        strategy = DigitalStrategy()
        for attempt in range(1, 4):
            try:
                content = await self._chat(self._build_proposal_messages(profile, pain_points))
                data = json.loads(content)
                strategy = DigitalStrategy(
                    recommendations=data.get("recommendations", []),
                    estimated_impact=data.get("estimated_impact", ""),
                    proposed_services=data.get("proposed_services", []),
                    timeline=data.get("timeline", ""),
                    pricing_estimate_myr=float(data.get("pricing_estimate_myr", 0.0) or 0.0),
                )
                break
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                logger.warning("Strategy JSON parse attempt %d failed: %s", attempt, exc)
                if attempt == 3:
                    logger.error("Strategy failed after 3 attempts; using default")
                    strategy = DigitalStrategy(
                        recommendations=["Build a responsive website", "Set up Google Business Profile", "Create Instagram page"],
                        estimated_impact="Moderate increase in local discovery",
                        proposed_services=["Website Design", "Local SEO", "Social Media Setup"],
                        timeline="Week 1-2: Design | Week 3-4: Build | Week 5: Launch",
                        pricing_estimate_myr=2500.0,
                    )
            except Exception as exc:
                logger.error("Strategy LLM error on attempt %d: %s", attempt, exc)
                if attempt == 3:
                    strategy = DigitalStrategy(
                        recommendations=["Build a responsive website", "Set up Google Business Profile", "Create Instagram page"],
                        estimated_impact="Moderate increase in local discovery",
                        proposed_services=["Website Design", "Local SEO", "Social Media Setup"],
                        timeline="Week 1-2: Design | Week 3-4: Build | Week 5: Launch",
                        pricing_estimate_myr=2500.0,
                    )
                else:
                    await asyncio.sleep(1.5)

        # Recalculate priority score
        total_severity = sum(pp.severity for pp in pain_points)
        profile.priority_score = total_severity + (100 - profile.seo.overall_score) * 0.5
        return pain_points, strategy
