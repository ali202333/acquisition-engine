"""Playwright-based web scraper for SEO and social audits."""
import asyncio
import logging
import re
from typing import Any

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Error as PlaywrightError

from src.models import SEOAudit, SocialMediaAudit

logger = logging.getLogger(__name__)


class WebScraper:
    """Async scraper using Playwright."""

    def __init__(self) -> None:
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None

    async def _ensure_browser(self) -> None:
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            )

    async def _fetch_page(self, url: str) -> str | None:
        await self._ensure_browser()
        page = await self._context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(1.0)
            html = await page.content()
            return html
        except PlaywrightError as exc:
            logger.warning("Playwright error fetching %s: %s", url, exc)
            return None
        finally:
            await page.close()

    async def audit_website(self, url: str) -> SEOAudit:
        """Audit a single URL and return SEO/UX findings."""
        audit = SEOAudit()
        try:
            html = await self._fetch_page(url)
            if html is None:
                return audit

            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator=" ", strip=True).lower()

            audit.has_ssl = url.startswith("https://")

            viewport = soup.find("meta", attrs={"name": "viewport"})
            audit.mobile_friendly = viewport is not None

            desc = soup.find("meta", attrs={"name": "description"})
            og_desc = soup.find("meta", attrs={"property": "og:description"})
            audit.meta_description_present = bool(desc or og_desc)

            # Contact page detection
            contact_links = soup.find_all(
                "a", href=re.compile(r"contact|kontak|reach|call|email|whatsapp", re.I)
            )
            audit.has_contact_page = len(contact_links) > 0

            # Menu detection
            menu_keywords = ["menu", "food", "drinks", "beverages", "price", "dish", "cuisine"]
            audit.has_menu_online = any(kw in text for kw in menu_keywords)

            # Very rough page-speed proxy: count resource tags
            resources = len(soup.find_all(["img", "script", "link"]))
            if resources < 30:
                audit.page_speed_score = 80
            elif resources < 60:
                audit.page_speed_score = 50
            else:
                audit.page_speed_score = 25

            # Overall score heuristic
            score = 0.0
            if audit.has_ssl:
                score += 15
            if audit.mobile_friendly:
                score += 20
            if audit.meta_description_present:
                score += 15
            if audit.has_contact_page:
                score += 15
            if audit.has_menu_online:
                score += 15
            if audit.page_speed_score:
                score += min(audit.page_speed_score / 2, 20)
            audit.overall_score = round(score, 1)

        except Exception as exc:
            logger.error("Error auditing %s: %s", url, exc)

        return audit

    async def check_social_media(self, business_name: str) -> SocialMediaAudit:
        """Search for social media presence (best-effort)."""
        social = SocialMediaAudit()
        try:
            await self._ensure_browser()
            # Search Instagram via Google
            query = f"{business_name} Instagram"
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            html = await self._fetch_page(search_url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                links = [a.get("href", "") for a in soup.find_all("a", href=True)]
                insta_links = [l for l in links if "instagram.com/" in l]
                if insta_links:
                    social.instagram_handle = insta_links[0].split("instagram.com/")[-1].split("/")[0]
                    social.platforms_found.append("instagram")

            # Search Facebook
            query = f"{business_name} Facebook"
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            html = await self._fetch_page(search_url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                links = [a.get("href", "") for a in soup.find_all("a", href=True)]
                fb_links = [l for l in links if "facebook.com/" in l]
                if fb_links:
                    social.facebook_url = fb_links[0]
                    social.platforms_found.append("facebook")

            # Follower estimate is unreliable without login; mock as unknown
            social.follower_count_estimate = None
            social.engagement_estimate = "unknown"

        except Exception as exc:
            logger.error("Error checking social media for %s: %s", business_name, exc)

        return social

    async def close(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
