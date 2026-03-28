import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.enricher import MediaItem

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
IMAGES_DIR = Path(__file__).parent.parent / "images"
OUTPUT_DIR = Path("/output")


class ReportGenerator:
    def __init__(self) -> None:
        self.env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

    def generate(self, items: list[MediaItem], since_date: str) -> Path:
        template = self.env.get_template("digest.html.jinja")

        movies = sorted(
            [i for i in items if i.type == "movie"],
            key=lambda x: x.premiere_date,
            reverse=True,
        )
        shows = sorted(
            [i for i in items if i.type == "show"],
            key=lambda x: x.premiere_date,
            reverse=True,
        )
        by_service = self._group_by_service(items)

        # Display-friendly date from ISO since_date
        try:
            since_display = datetime.strptime(since_date, "%Y-%m-%d").strftime("%B %d, %Y")
        except ValueError:
            since_display = since_date

        run_date = datetime.now().strftime("%B %d, %Y")
        def _read_svg(name: str, prefix: str) -> str:
            p = IMAGES_DIR / name
            if not p.exists():
                return ""
            content = p.read_text(encoding="utf-8")
            start_index = content.find("<svg")
            if start_index != -1:
                content = content[start_index:]
            # Prevent class name collisions when both SVGs are inlined on the same page
            content = content.replace("cls-", f"{prefix}-cls-")
            return content

        html = template.render(
            movies=movies,
            shows=shows,
            by_service=by_service,
            since_date=since_display,
            run_date=run_date,
            total_count=len(items),
            svg1=_read_svg("1.svg", "svg1"),
            svg2=_read_svg("2.svg", "svg2"),
        )

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_file = OUTPUT_DIR / f"digest_{datetime.now().strftime('%m-%d-%Y')}.html"
        output_file.write_text(html, encoding="utf-8")
        logger.info(f"Digest written to {output_file}")

        latest = OUTPUT_DIR / "latest.html"
        latest.write_text(html, encoding="utf-8")

        self._prune_old_digests(keep=12)
        return output_file

    def _group_by_service(self, items: list[MediaItem]) -> dict[str, list[MediaItem]]:
        services: dict[str, list[MediaItem]] = {}
        for item in items:
            for svc in item.services:
                services.setdefault(svc, []).append(item)
        return dict(sorted(services.items()))

    def _prune_old_digests(self, keep: int) -> None:
        digests = sorted(OUTPUT_DIR.glob("digest_*.html"), reverse=True)
        for old in digests[keep:]:
            old.unlink()
            logger.info(f"Pruned old digest: {old.name}")
