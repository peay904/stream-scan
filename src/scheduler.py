import logging
import time

import schedule

from src.config import config

logger = logging.getLogger(__name__)


def start_scheduler(run_scan_fn) -> None:
    """Start the daily scheduler. Blocks forever."""
    hour = f"{config.SCAN_HOUR:02d}:00"

    schedule.every().day.at(hour).do(run_scan_fn)

    logger.info(f"Scheduler started: will run every day at {hour}")

    while True:
        schedule.run_pending()
        time.sleep(60)
