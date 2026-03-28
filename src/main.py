import logging
import os
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%m-%d-%y %H:%M:%S",
)

logger = logging.getLogger(__name__)


def run_scan() -> None:
    """Called by scheduler (or directly when FORCE_RUN=true)."""
    from datetime import datetime, timedelta, timezone

    from src.config import config
    from src.enricher import Enricher
    from src.report import ReportGenerator
    from src.scanner import Scanner

    config.validate()

    since_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    logger.info(f"Starting scan: past 30 days from {since_date}")

    scanner = Scanner()
    raw_items = scanner.fetch_since(since_date)

    enricher = Enricher()
    enriched = enricher.enrich_all(raw_items)

    report = ReportGenerator()
    output_file = report.generate(enriched, since_date)
    logger.info(f"Report saved to {output_file}")


if __name__ == "__main__":
    from src.server import start_server

    start_server()

    if os.getenv("FORCE_RUN", "false").lower() == "true":
        run_scan()
        # Keep process alive so web server stays up after FORCE_RUN
        logger.info("FORCE_RUN complete. Web server still running — Ctrl+C to stop.")
        while True:
            time.sleep(3600)
    else:
        from src.scheduler import start_scheduler
        start_scheduler(run_scan)
