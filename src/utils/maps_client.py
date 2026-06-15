"""Google Maps API wrapper with pagination and backoff."""
import logging
import time
from typing import Any

import requests

from src.models import BusinessDiscovery

logger = logging.getLogger(__name__)

BASE_URL = "https://maps.googleapis.com/maps/api/place"


class GoogleMapsClient:
    """Client for Google Places API (Text Search & Details)."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.session = requests.Session()

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{BASE_URL}/{endpoint}/json"
        params["key"] = self.api_key
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Google Maps API request failed: %s", exc)
            raise
        data: dict[str, Any] = response.json()
        status = data.get("status", "UNKNOWN")
        if status == "OVER_QUERY_LIMIT":
            logger.warning("Rate limit hit; backing off 2s")
            time.sleep(2.0)
            return self._get(endpoint, {k: v for k, v in params.items() if k != "key"})
        if status not in ("OK", "ZERO_RESULTS"):
            logger.error("Google Maps API error: %s - %s", status, data.get("error_message"))
        return data

    def get_place_details(self, place_id: str) -> dict[str, Any]:
        """Fetch detailed fields for a place_id."""
        fields = "website,formatted_phone_number,opening_hours,price_level"
        params = {"place_id": place_id, "fields": fields}
        return self._get("details", params)

    def search_places(
        self, query: str, region: str, max_results: int = 20
    ) -> list[BusinessDiscovery]:
        """Text Search with pagination and exponential backoff."""
        results: list[BusinessDiscovery] = []
        page_token: str | None = None
        attempts = 0

        while len(results) < max_results:
            params: dict[str, Any] = {
                "query": f"{query} in {region}",
                "language": "en",
            }
            if page_token:
                params["pagetoken"] = page_token
                time.sleep(2.0)  # Google requires delay before next_page_token is valid

            data = self._get("textsearch", params)
            status = data.get("status", "UNKNOWN")

            if status == "ZERO_RESULTS":
                logger.info("Zero results for query '%s' in %s", query, region)
                break

            if status != "OK":
                logger.error("TextSearch failed: %s", status)
                break

            for place in data.get("results", []):
                if len(results) >= max_results:
                    break

                place_id = place.get("place_id", "")
                name = place.get("name", "Unknown")
                address = place.get("formatted_address", "")
                rating = place.get("rating")
                review_count = place.get("user_ratings_total")
                types = place.get("types", [])
                maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"

                website: str | None = None
                phone: str | None = None
                try:
                    details = self.get_place_details(place_id)
                    result = details.get("result", {})
                    website = result.get("website")
                    phone = result.get("formatted_phone_number")
                except Exception as exc:
                    logger.warning("Details fetch failed for %s: %s", name, exc)

                # Simple social-media detection heuristic
                has_social = False
                if website:
                    lower_site = website.lower()
                    has_social = any(
                        s in lower_site for s in ["instagram", "facebook", "tiktok"]
                    )

                results.append(
                    BusinessDiscovery(
                        name=name,
                        address=address,
                        phone=phone,
                        website=website,
                        google_maps_url=maps_url,
                        rating=rating,
                        review_count=review_count,
                        categories=types,
                        place_id=place_id,
                        has_website=bool(website),
                        has_social_media=has_social,
                    )
                )

            page_token = data.get("next_page_token")
            if not page_token:
                break

            attempts += 1
            if attempts > 3:
                logger.warning("Pagination limit reached")
                break

        return results[:max_results]
