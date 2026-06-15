"""CLI entry point for the acquisition engine."""
import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

from src.config import get_config
from src.models import BusinessProfile, DigitalStrategy
from src.state_machine import StateMachine
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _load_json_profiles(path: str) -> list[BusinessProfile]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return [BusinessProfile(**item) for item in data]
    raise ValueError(f"Expected JSON array in {path}")


async def _run_full_pipeline(region: str, keywords: list[str]) -> None:
    config = get_config()
    async with StateMachine(config) as sm:
        final_state = await sm.run(region=region, keywords=keywords)
    if final_state["errors"]:
        logger.warning("Pipeline completed with %d errors", len(final_state["errors"]))
        for err in final_state["errors"]:
            logger.warning("  - %s", err)
    logger.info(
        "Pipeline finished. Businesses: %d | Analyzed: %d | Outreach: %d",
        len(final_state["businesses"]),
        len(final_state["analyzed"]),
        len(final_state["outreach"]),
    )


async def _run_scrape_only(region: str, keywords: list[str]) -> None:
    from src.utils.maps_client import GoogleMapsClient
    from src.utils.scraper import WebScraper
    from src.agents.scraper_agent import ScraperAgent

    config = get_config()
    maps_client = GoogleMapsClient(config.google_maps_api_key)
    scraper = WebScraper()
    agent = ScraperAgent(maps_client, scraper)
    try:
        profiles = await agent.run(keywords=keywords, region=region, max_results=config.max_results_per_search)
    finally:
        await scraper.close()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(config.output_dir, f"raw_businesses_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([p.model_dump(mode="json") for p in profiles], f, indent=2, ensure_ascii=False)
    logger.info("Scraped %d businesses -> %s", len(profiles), out_path)


async def _run_audit_only(input_path: str) -> None:
    from src.agents.auditor_agent import AuditorAgent

    config = get_config()
    profiles = _load_json_profiles(input_path)
    agent = AuditorAgent(config.llm_model, config)
    analyzed: list[tuple[BusinessProfile, DigitalStrategy]] = []
    for profile in profiles:
        try:
            pain_points, strategy = await agent.analyze(profile)
            profile.pain_points = pain_points
            analyzed.append((profile, strategy))
        except Exception as exc:
            logger.error("Audit failed for %s: %s", profile.business.name, exc)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(config.output_dir, f"analyzed_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            [{"business": b.model_dump(mode="json"), "strategy": s.model_dump(mode="json")} for b, s in analyzed],
            f,
            indent=2,
            ensure_ascii=False,
        )
    logger.info("Audited %d / %d businesses -> %s", len(analyzed), len(profiles), out_path)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Autonomous Hyper-Local Client Acquisition Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the full pipeline")
    run_parser.add_argument("--region", required=True, help="Target region (e.g., Cyberjaya)")
    run_parser.add_argument("--keywords", nargs="+", required=True, help="Keywords like cafe restaurant lounge")

    scrape_parser = subparsers.add_parser("scrape", help="Run only the scraper")
    scrape_parser.add_argument("--region", required=True, help="Target region")
    scrape_parser.add_argument("--keywords", nargs="+", required=True, help="Search keywords")

    audit_parser = subparsers.add_parser("audit", help="Run audit on existing JSON")
    audit_parser.add_argument("--input", required=True, help="Path to raw_businesses.json")

    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(_run_full_pipeline(args.region, args.keywords))
    elif args.command == "scrape":
        asyncio.run(_run_scrape_only(args.region, args.keywords))
    elif args.command == "audit":
        asyncio.run(_run_audit_only(args.input))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
