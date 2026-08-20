import asyncio
import logging
from datetime import date

import httpx

from src.config import config

logger = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"

# TMDb US Provider IDs for common flatrate streaming services
TMDB_PROVIDER_IDS: dict[str, int] = {
    "netflix": 8,
    "hulu": 15,
    "prime": 9,
    "max": 1899,
    "peacock": 386,
    "paramount": 531,
    "apple": 350,
    "disney": 337,
}


def _get_provider_ids(services: list[str]) -> str:
    ids = [str(TMDB_PROVIDER_IDS[s]) for s in services if s in TMDB_PROVIDER_IDS]
    return "|".join(ids)  # Use pipe '|' for OR logical operator in TMDb Discover


class Scanner:
    def fetch_since(self, since_date: str) -> list[dict]:
        """Fetch new movies and shows directly from TMDb released/aired since since_date (YYYY-MM-DD)."""
        return asyncio.run(self._fetch_all(since_date))

    async def _fetch_all(self, since_date: str) -> list[dict]:
        today_str = date.today().isoformat()
        provider_ids = _get_provider_ids(config.SERVICES)

        logger.info(f"Scanning TMDb from {since_date} to {today_str} for providers: {provider_ids}")

        async with httpx.AsyncClient(timeout=30) as session:
            movies, shows = await asyncio.gather(
                self._discover_movies(session, since_date, today_str, provider_ids),
                self._discover_shows(session, since_date, today_str, provider_ids),
            )

        logger.info(f"Found {len(movies)} movies, {len(shows)} shows from TMDb")
        return movies + shows

    async def _discover_movies(
        self,
        session: httpx.AsyncClient,
        since_date: str,
        today_str: str,
        provider_ids: str,
    ) -> list[dict]:
        params = {
            "api_key": config.TMDB_API_KEY,
            "watch_region": "US",
            "with_watch_monetization_types": "flatrate",
            "with_watch_providers": provider_ids,
            "primary_release_date.gte": since_date,
            "primary_release_date.lte": today_str,
            "with_original_language": "en",
            "sort_by": "popularity.desc",
        }
        return await self._fetch_all_pages(session, f"{TMDB_BASE}/discover/movie", params, "movie")

    async def _discover_shows(
        self,
        session: httpx.AsyncClient,
        since_date: str,
        today_str: str,
        provider_ids: str,
    ) -> list[dict]:
        params = {
            "api_key": config.TMDB_API_KEY,
            "watch_region": "US",
            "with_watch_monetization_types": "flatrate",
            "with_watch_providers": provider_ids,
            "first_air_date.gte": since_date,
            "first_air_date.lte": today_str,
            "with_original_language": "en",
            "sort_by": "popularity.desc",
        }
        return await self._fetch_all_pages(session, f"{TMDB_BASE}/discover/tv", params, "show")

    async def _fetch_all_pages(
        self,
        session: httpx.AsyncClient,
        url: str,
        params: dict,
        media_type: str,
    ) -> list[dict]:
        results = []
        page = 1
        max_pages = 5  # Limit pages to prevent hitting TMDb rate limits on broad queries

        while page <= max_pages:
            try:
                r = await session.get(url, params={**params, "page": page})
                if r.status_code == 429:
                    logger.warning("TMDb rate limit hit; waiting 5s")
                    await asyncio.sleep(5)
                    continue
                r.raise_for_status()
                data = r.json()

                for item in data.get("results", []):
                    item["_type"] = media_type
                    results.append(item)

                total_pages = data.get("total_pages", 1)
                if page >= total_pages:
                    break
                page += 1
            except Exception as e:
                logger.warning(f"TMDb Discover failed for {url} page {page}: {e}")
                break

        return results