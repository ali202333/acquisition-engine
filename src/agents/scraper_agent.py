"""The Cyberjaya Business Scraper Agent."""
import asyncio
import logging
from typing import Optional

from src.models import BusinessProfile, SEOAudit, SocialMediaAudit
from src.utils.maps_client import GoogleMapsClient
from src.utils.scraper import WebScraper

logger = logging.getLogger(__name__)


class ScraperAgent:
    """Orchestrates Google Maps search + web scraping to build BusinessProfiles."""

    def __init__(self, maps_client: GoogleMapsClient, scraper: WebScraper) -> None:
        self.maps_client = maps_client
        self.scraper = scraper

    async def _process_single(self, business: BusinessProfile) -> Optional[BusinessProfile]:
        """Audit one business; return None on total failure."""
        try:
            if business.business.website:
                try:
                    seo = await self.scraper.audit_website(business.business.website)
                except Exception as exc:
                    logger.warning("Website audit failed for %s: %s", business.business.name, exc)
                    seo = SEOAudit()
                business.seo = seo

            try:
                social = await self.scraper.check_social_media(business.business.name)
            except Exception as exc:
                logger.warning("Social audit failed for %s: %s", business.business.name, exc)
                social = SocialMediaAudit()
            business.social = social

            return business
        except Exception as exc:
            logger.error("Unhandled error processing %s: %s", business.business.name, exc)
            return None

    async def run(
        self, keywords: list[str], region: str, max_results: int
    ) -> list[BusinessProfile]:
        """Run scraping for all keywords and compile BusinessProfiles."""
        all_profiles: list[BusinessProfile] = []
        for keyword in keywords:
            logger.info("Searching keyword '%s' in %s", keyword, region)
            try:
                discoveries = self.maps_client.search_places(keyword, region, max_results)
            except Exception as exc:
                logger.error("Maps search failed for '%s': %s", keyword, exc)
                continue

            for disc in discoveries:
                profile = BusinessProfile(business=disc)
                all_profiles.append(profile)

        # Audit each in parallel with concurrency limit
        semaphore = asyncio.Semaphore(5)

        async def _with_sem(profile: BusinessProfile) -> Optional[BusinessProfile]:
            async with semaphore:
                return await self._process_single(profile)

        tasks = [asyncio.create_task(_with_sem(p)) for p in all_profiles]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid: list[BusinessProfile] = []
        for profile, result in zip(all_profiles, results):
            if isinstance(result, BusinessProfile):
                valid.append(result)
            elif isinstance(result, Exception):
                logger.error("Async scrape exception for %s: %s", profile.business.name, result)
            else:
                logger.warning("Skipping %s due to failure", profile.business.name)

        logger.info("ScraperAgent finished: %d / %d profiles valid", len(valid), len(all_profiles))
        return valid
