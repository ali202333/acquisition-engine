"""State machine orchestrating the full pipeline."""
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Optional, TypedDict

from src.agents.auditor_agent import AuditorAgent
from src.agents.outreach_agent import OutreachAgent
from src.agents.scraper_agent import ScraperAgent
from src.config import Config, get_config
from src.models import BusinessProfile, DigitalStrategy, OutreachPackage
from src.utils.maps_client import GoogleMapsClient
from src.utils.pdf_generator import ProposalPDFGenerator
from src.utils.scraper import WebScraper

logger = logging.getLogger(__name__)


class State(TypedDict):
    region: str
    keywords: list[str]
    businesses: list[BusinessProfile]
    analyzed: list[tuple[BusinessProfile, DigitalStrategy]]
    outreach: list[OutreachPackage]
    current_step: str
    errors: list[str]


class StateMachine:
    """LangGraph-style state machine with sequential fallback."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.maps_client = GoogleMapsClient(config.google_maps_api_key)
        self.scraper = WebScraper()
        self.scraper_agent = ScraperAgent(self.maps_client, self.scraper)
        self.auditor_agent = AuditorAgent(config.llm_model, config)
        self.pdf_generator = ProposalPDFGenerator(config.output_dir)
        self.outreach_agent = OutreachAgent(self.pdf_generator, config)

    async def _scrape_node(self, state: State) -> State:
        state["current_step"] = "scrape"
        try:
            businesses = await self.scraper_agent.run(
                keywords=state["keywords"],
                region=state["region"],
                max_results=self.config.max_results_per_search,
            )
            state["businesses"] = businesses
            logger.info("Scrape node completed: %d businesses found", len(businesses))
        except Exception as exc:
            state["errors"].append(f"Scrape error: {exc}")
            logger.exception("Scrape node failed")
        return state

    async def _audit_node(self, state: State) -> State:
        state["current_step"] = "audit"
        analyzed: list[tuple[BusinessProfile, DigitalStrategy]] = []
        for biz in state["businesses"]:
            try:
                pain_points, strategy = await self.auditor_agent.analyze(biz)
                biz.pain_points = pain_points
                analyzed.append((biz, strategy))
            except Exception as exc:
                state["errors"].append(f"Audit error for {biz.business.name}: {exc}")
                logger.warning("Audit failed for %s: %s", biz.business.name, exc)
        state["analyzed"] = analyzed
        logger.info("Audit node completed: %d / %d analyzed", len(analyzed), len(state["businesses"]))
        return state

    async def _outreach_node(self, state: State) -> State:
        state["current_step"] = "outreach"
        try:
            outreach_packages = await self.outreach_agent.build_batch(state["analyzed"])
            state["outreach"] = outreach_packages
            logger.info("Outreach node completed: %d packages built", len(outreach_packages))
        except Exception as exc:
            state["errors"].append(f"Outreach error: {exc}")
            logger.exception("Outreach node failed")
        return state

    async def _save_node(self, state: State) -> State:
        state["current_step"] = "save"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_dir = os.path.join(self.config.output_dir, f"run_{ts}")
        os.makedirs(base_dir, exist_ok=True)

        # Save raw businesses
        raw_path = os.path.join(base_dir, "raw_businesses.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(
                [b.model_dump(mode="json") for b in state["businesses"]],
                f,
                indent=2,
                ensure_ascii=False,
            )

        # Save analyzed
        analyzed_path = os.path.join(base_dir, "analyzed.json")
        with open(analyzed_path, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {
                        "business": b.model_dump(mode="json"),
                        "strategy": s.model_dump(mode="json"),
                    }
                    for b, s in state["analyzed"]
                ],
                f,
                indent=2,
                ensure_ascii=False,
            )

        # Save outreach packages
        outreach_path = os.path.join(base_dir, "outreach_packages.json")
        with open(outreach_path, "w", encoding="utf-8") as f:
            json.dump(
                [o.model_dump(mode="json") for o in state["outreach"]],
                f,
                indent=2,
                ensure_ascii=False,
            )

        # Save state
        state_path = os.path.join(base_dir, "state.json")
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "region": state["region"],
                    "keywords": state["keywords"],
                    "current_step": state["current_step"],
                    "errors": state["errors"],
                    "business_count": len(state["businesses"]),
                    "analyzed_count": len(state["analyzed"]),
                    "outreach_count": len(state["outreach"]),
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        logger.info("Save node completed: artifacts in %s", base_dir)
        return state

    async def run(self, region: str, keywords: list[str]) -> State:
        """Execute the full state machine sequentially."""
        state: State = {
            "region": region,
            "keywords": keywords,
            "businesses": [],
            "analyzed": [],
            "outreach": [],
            "current_step": "init",
            "errors": [],
        }

        state = await self._scrape_node(state)
        if not state["businesses"]:
            state["errors"].append("No businesses found; pipeline halting.")
            logger.error("No businesses found; halting.")
            return state

        state = await self._audit_node(state)
        if not state["analyzed"]:
            state["errors"].append("No businesses analyzed; pipeline halting.")
            logger.error("No businesses analyzed; halting.")
            return state

        state = await self._outreach_node(state)
        state = await self._save_node(state)
        return state

    async def __aenter__(self) -> "StateMachine":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.scraper.close()
