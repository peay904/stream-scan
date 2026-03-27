import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE_FILE = Path("/state/last_run.json")
logger = logging.getLogger(__name__)


class StateManager:
    def last_run_date(self) -> str:
        """Returns ISO date string (YYYY-MM-DD) of last run, or 30 days ago if first run."""
        try:
            data = json.loads(STATE_FILE.read_text())
            last = datetime.fromisoformat(data["last_run"])
            logger.info(f"Last run was: {last.isoformat()}")
            return last.strftime("%Y-%m-%d")
        except (FileNotFoundError, KeyError, ValueError):
            fallback = datetime.now(timezone.utc) - timedelta(days=30)
            logger.info(f"No prior state found; defaulting to 30 days ago: {fallback.date()}")
            return fallback.strftime("%Y-%m-%d")

    def update(self) -> None:
        """Write current UTC timestamp as last_run."""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        STATE_FILE.write_text(
            json.dumps(
                {
                    "last_run": now.isoformat(),
                    "last_run_human": now.strftime("%A, %B %d %Y at %H:%M UTC"),
                },
                indent=2,
            )
        )
        logger.info(f"State updated: last_run = {now.isoformat()}")
