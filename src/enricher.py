import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from src.config import config
from src.scanner import NETWORK_MAP

logger = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
OUTPUT_DIR = Path("/output")


@dataclass
class MediaItem:
    title: str
    type: str                    # "movie" or "show"
    premiere_date: str           # ISO date string YYYY-MM-DD
    overview: str
    poster_url: str              # Local relative path or TMDB URL
    services: list[str]
    genres: list[str]
    tmdb_id: int
    trakt_slug: str
    tmdb_rating: float = 0.0
    runtime_minutes: int = 0     # movies only
    seasons: int = 0             # shows only


def _target_provider_names(services: list[str]) -> set[str]:
    targets: set[str] = set()
    for svc in services:
        targets.update(NETWORK_MAP.get(svc.lower(), []))
    return targets


def _get_us_streaming_services(tmdb_data: dict, target_names: set[str]) -> list[str]:
    providers = tmdb_data.get("watch/providers", {}).get("results", {}).get("US", {})
    flatrate = providers.get("flatrate", [])
    found = [p["provider_name"] for p in flatrate if p["provider_name"] in target_names]
    return found


def poster_url(poster_path: str) -> str:
    return f"{TMDB_IMAGE_BASE}{poster_path}"


class Enricher:
    def enrich_all(self, raw_items: list[dict]) -> list[MediaItem]:
        return asyncio.run(self._enrich_all(raw_items))

    async def _enrich_all(self, raw_items: list[dict]) -> list[MediaItem]:
        target_names = _target_provider_names(config.SERVICES)
        posters_dir = OUTPUT_DIR / "posters"
        posters_dir.mkdir(parents=True, exist_ok=True)

        results: list[MediaItem] = []
        async with httpx.AsyncClient(timeout=15) as session:
            for raw in raw_items:
                item = await self._enrich_one(session, raw, target_names, posters_dir)
                if item is not None:
                    results.append(item)
                await asyncio.sleep(0.1)

        logger.info(f"Enrichment complete: {len(results)} items after filtering")
        return results

    async def _enrich_one(
        self,
        session: httpx.AsyncClient,
        raw: dict,
        target_names: set[str],
        posters_dir: Path,
    ) -> MediaItem | None:
        media_type = raw["_type"]
        trakt_network_matches = raw.get("_trakt_network_matches", False)

        if media_type == "movie":
            media = raw["movie"]
            tmdb_id = media.get("ids", {}).get("tmdb")
            premiere_date = raw.get("released", "")
            endpoint = f"/movie/{tmdb_id}"
        else:
            media = raw["show"]
            tmdb_id = media.get("ids", {}).get("tmdb")
            premiere_date = (raw.get("first_aired") or "")[:10]
            endpoint = f"/tv/{tmdb_id}"

        if not tmdb_id:
            logger.debug(f"Skipping '{media.get('title')}': no TMDB ID")
            return None

        tmdb_data = await self._safe_fetch(
            session,
            f"{TMDB_BASE}{endpoint}",
            params={"api_key": config.TMDB_API_KEY, "append_to_response": "watch/providers"},
        )
        if tmdb_data is None:
            return None

        # Only include English-language content
        if tmdb_data.get("original_language") != "en":
            logger.debug(f"Skipping '{media.get('title')}': non-English ({tmdb_data.get('original_language')})")
            return None

        # Determine streaming services from TMDB watch providers
        streaming_services = _get_us_streaming_services(tmdb_data, target_names)

        # For shows, Trakt network already filtered; still confirm via TMDB if available
        if media_type == "show":
            if not streaming_services and not trakt_network_matches:
                return None
            # If TMDB confirmed services, use those; otherwise use Trakt network name
            if not streaming_services and trakt_network_matches:
                trakt_network = raw.get("_trakt_network", "")
                streaming_services = [trakt_network] if trakt_network else []
        else:
            # Movies: must be confirmed on a target service via TMDB
            if not streaming_services:
                return None

        # Cache poster
        poster_path = tmdb_data.get("poster_path")
        if poster_path:
            local_poster = await self._cache_poster(session, poster_path, posters_dir)
        else:
            local_poster = ""

        # Extract genres
        genres = [g["name"] for g in tmdb_data.get("genres", [])]

        # Build MediaItem
        slug = media.get("ids", {}).get("slug", "")
        rating = tmdb_data.get("vote_average", 0.0) or 0.0
        overview = tmdb_data.get("overview") or media.get("overview") or ""
        title = tmdb_data.get("title") or tmdb_data.get("name") or media.get("title", "Unknown")

        if media_type == "movie":
            return MediaItem(
                title=title,
                type="movie",
                premiere_date=premiere_date or tmdb_data.get("release_date", ""),
                overview=overview,
                poster_url=local_poster,
                services=streaming_services,
                genres=genres,
                tmdb_id=tmdb_id,
                trakt_slug=slug,
                tmdb_rating=round(rating, 1),
                runtime_minutes=tmdb_data.get("runtime") or 0,
            )
        else:
            return MediaItem(
                title=title,
                type="show",
                premiere_date=premiere_date or tmdb_data.get("first_air_date", ""),
                overview=overview,
                poster_url=local_poster,
                services=streaming_services,
                genres=genres,
                tmdb_id=tmdb_id,
                trakt_slug=slug,
                tmdb_rating=round(rating, 1),
                seasons=tmdb_data.get("number_of_seasons") or 0,
            )

    async def _safe_fetch(
        self,
        session: httpx.AsyncClient,
        url: str,
        params: dict | None = None,
    ) -> dict | None:
        try:
            r = await session.get(url, params=params)
            if r.status_code == 429:
                logger.warning(f"TMDB rate limit; backing off 5s for {url}")
                await asyncio.sleep(5)
                return await self._safe_fetch(session, url, params)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"TMDB HTTP {e.response.status_code} for {url}")
            return None
        except Exception as e:
            logger.warning(f"TMDB request failed for {url}: {e}")
            return None

    async def _cache_poster(
        self,
        session: httpx.AsyncClient,
        poster_path: str,
        posters_dir: Path,
    ) -> str:
        filename = poster_path.lstrip("/").replace("/", "_")
        local_path = posters_dir / filename
        if local_path.exists():
            return f"posters/{filename}"
        try:
            r = await session.get(f"{TMDB_IMAGE_BASE}{poster_path}")
            r.raise_for_status()
            local_path.write_bytes(r.content)
            return f"posters/{filename}"
        except Exception as e:
            logger.warning(f"Failed to cache poster {poster_path}: {e}")
            return poster_url(poster_path)
