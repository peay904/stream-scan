import logging
import time

import schedule

from src.config import config

logger = logging.getLogger(__name__)


def start_scheduler(run_scan_fn) -> None:
    """Start the weekly scheduler. Blocks forever."""
    day = config.SCAN_DAY.lower()
    hour = f"{config.SCAN_HOUR:02d}:00"

    day_map = {
        "monday": schedule.every().monday,
        "tuesday": schedule.every().tuesday,
        "wednesday": schedule.every().wednesday,
        "thursday": schedule.every().thursday,
        "friday": schedule.every().friday,
        "saturday": schedule.every().saturday,
        "sunday": schedule.every().sunday,
    }

    job = day_map.get(day, schedule.every().monday)
    job.at(hour).do(run_scan_fn)

    logger.info(f"Scheduler started: will run every {day} at {hour}")

    while True:
        schedule.run_pending()
        time.sleep(60)
