import asyncio
import logging
from datetime import date, datetime

import httpx

from src.config import config

logger = logging.getLogger(__name__)

TRAKT_BASE = "https://api.trakt.tv"

NETWORK_MAP: dict[str, list[str]] = {
    "netflix": ["Netflix"],
    "hulu": ["Hulu"],
    "prime": ["Amazon Prime Video", "Prime Video"],
    "max": ["Max", "HBO Max"],
    "peacock": ["Peacock"],
    "paramount": ["Paramount+", "Paramount Plus"],
    "apple": ["Apple TV+", "Apple TV"],
    "disney": ["Disney+", "Disney Plus"],
}


def _target_networks(services: list[str]) -> set[str]:
    targets: set[str] = set()
    for svc in services:
        targets.update(NETWORK_MAP.get(svc.lower(), []))
    return targets


def _is_target_network(network: str | None, targets: set[str]) -> bool:
    return network in targets if network else False


class Scanner:
    def fetch_since(self, since_date: str) -> list[dict]:
        """Fetch new movies and shows from Trakt since since_date (YYYY-MM-DD).

        Returns a flat list of raw dicts with an added '_type' key ('movie' or 'show').
        """
        return asyncio.run(self._fetch_all(since_date))

    async def _fetch_all(self, since_date: str) -> list[dict]:
        today = date.today()
        start = min(datetime.strptime(since_date, "%Y-%m-%d").date(), today)
        days = max((today - start).days, 1)
        logger.info(f"Scanning Trakt from {since_date} ({days} days)")

        headers = {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": config.TRAKT_CLIENT_ID,
        }
        targets = _target_networks(config.SERVICES)

        async with httpx.AsyncClient(timeout=30) as session:
            movies, shows = await asyncio.gather(
                self._fetch_movies(session, headers, since_date, days, targets),
                self._fetch_shows(session, headers, since_date, days, targets),
            )

        logger.info(f"Found {len(movies)} movies, {len(shows)} shows before enrichment")
        return movies + shows

    async def _fetch_movies(
        self,
        session: httpx.AsyncClient,
        headers: dict,
        start_date: str,
        days: int,
        targets: set[str],
    ) -> list[dict]:
        url = f"{TRAKT_BASE}/calendars/all/movies/{start_date}/{days}"
        raw = await self._fetch_all_pages(session, url, headers, {"extended": "full"})
        results = []
        for entry in raw:
            movie = entry.get("movie", {})
            network = movie.get("network")
            # For movies, Trakt network is often missing; include all and filter later via TMDB
            item = {
                "_type": "movie",
                "_trakt_network": network,
                "_trakt_network_matches": _is_target_network(network, targets),
                "released": entry.get("released"),
                "movie": movie,
            }
            results.append(item)
        return results

    async def _fetch_shows(
        self,
        session: httpx.AsyncClient,
        headers: dict,
        start_date: str,
        days: int,
        targets: set[str],
    ) -> list[dict]:
        url = f"{TRAKT_BASE}/calendars/all/shows/premieres/{start_date}/{days}"
        raw = await self._fetch_all_pages(session, url, headers, {"extended": "full"})
        results = []
        for entry in raw:
            show = entry.get("show", {})
            network = show.get("network")
            if not _is_target_network(network, targets):
                continue
            item = {
                "_type": "show",
                "_trakt_network": network,
                "_trakt_network_matches": True,
                "first_aired": entry.get("first_aired"),
                "show": show,
            }
            results.append(item)
        return results

    async def _fetch_all_pages(
        self,
        session: httpx.AsyncClient,
        url: str,
        headers: dict,
        params: dict,
    ) -> list:
        results = []
        page = 1
        while True:
            try:
                r = await session.get(url, headers=headers, params={**params, "page": page, "limit": 100})
                if r.status_code == 429:
                    logger.warning("Trakt rate limit hit; waiting 5s")
                    await asyncio.sleep(5)
                    continue
                r.raise_for_status()
                results.extend(r.json())
                total_pages = int(r.headers.get("X-Pagination-Page-Count", 1))
                if page >= total_pages:
                    break
                page += 1
            except httpx.HTTPStatusError as e:
                logger.warning(f"Trakt HTTP error {e.response.status_code} for {url}: {e}")
                break
            except Exception as e:
                logger.warning(f"Trakt request failed for {url}: {e}")
                break
        return results
