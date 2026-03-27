import os
from dotenv import load_dotenv

load_dotenv()

# Set timezone early so schedule library picks it up
os.environ.setdefault("TZ", "UTC")


class Config:
    TRAKT_CLIENT_ID: str = os.getenv("TRAKT_CLIENT_ID", "")
    TMDB_API_KEY: str = os.getenv("TMDB_API_KEY", "")
    SCAN_DAY: str = os.getenv("SCAN_DAY", "friday").lower()
    SCAN_HOUR: int = int(os.getenv("SCAN_HOUR", "6"))
    SERVICES: list[str] = [
        s.strip().lower()
        for s in os.getenv(
            "SERVICES",
            "netflix,hulu,prime,max,peacock,paramount,apple,disney",
        ).split(",")
        if s.strip()
    ]
    WEB_PORT: int = int(os.getenv("WEB_PORT", "7777"))
    FORCE_RUN: bool = os.getenv("FORCE_RUN", "false").lower() == "true"

    def validate(self) -> None:
        if not self.TRAKT_CLIENT_ID:
            raise ValueError("TRAKT_CLIENT_ID environment variable is required")
        if not self.TMDB_API_KEY:
            raise ValueError("TMDB_API_KEY environment variable is required")


config = Config()
