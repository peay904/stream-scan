import os
from unittest.mock import patch

import pytest

from src.scanner import NETWORK_MAP, _is_target_network, _target_networks
from src.enricher import (
    MediaItem,
    _get_us_streaming_services,
    _target_provider_names,
    poster_url,
)
from src.report import ReportGenerator, _ALIAS_TO_KEY, _KEY_LABEL


# ---------------------------------------------------------------------------
# scanner._target_networks
# ---------------------------------------------------------------------------

def test_target_networks_known_service():
    result = _target_networks(["netflix"])
    assert "Netflix" in result


def test_target_networks_multiple_services():
    result = _target_networks(["netflix", "disney"])
    assert "Netflix" in result
    assert "Disney+" in result
    assert "Disney Plus" in result


def test_target_networks_case_insensitive():
    assert _target_networks(["NETFLIX"]) == _target_networks(["netflix"])


def test_target_networks_unknown_service():
    result = _target_networks(["nonexistent_service"])
    assert len(result) == 0


def test_target_networks_empty():
    assert _target_networks([]) == set()


# ---------------------------------------------------------------------------
# scanner._is_target_network
# ---------------------------------------------------------------------------

def test_is_target_network_match():
    targets = {"Netflix", "Hulu"}
    assert _is_target_network("Netflix", targets) is True


def test_is_target_network_no_match():
    targets = {"Netflix"}
    assert _is_target_network("Hulu", targets) is False


def test_is_target_network_none():
    assert _is_target_network(None, {"Netflix"}) is False


def test_is_target_network_empty_targets():
    assert _is_target_network("Netflix", set()) is False


# ---------------------------------------------------------------------------
# enricher._target_provider_names
# ---------------------------------------------------------------------------

def test_target_provider_names_matches_network_map():
    result = _target_provider_names(["prime"])
    assert "Amazon Prime Video" in result
    assert "Prime Video" in result


def test_target_provider_names_all_services():
    all_services = list(NETWORK_MAP.keys())
    result = _target_provider_names(all_services)
    for aliases in NETWORK_MAP.values():
        for alias in aliases:
            assert alias in result


# ---------------------------------------------------------------------------
# enricher._get_us_streaming_services
# ---------------------------------------------------------------------------

def test_get_us_streaming_services_found():
    tmdb_data = {
        "watch/providers": {
            "results": {
                "US": {
                    "flatrate": [
                        {"provider_name": "Netflix"},
                        {"provider_name": "Hulu"},
                    ]
                }
            }
        }
    }
    result = _get_us_streaming_services(tmdb_data, {"Netflix"})
    assert result == ["Netflix"]


def test_get_us_streaming_services_none_match():
    tmdb_data = {
        "watch/providers": {
            "results": {
                "US": {
                    "flatrate": [{"provider_name": "Some Other Service"}]
                }
            }
        }
    }
    result = _get_us_streaming_services(tmdb_data, {"Netflix"})
    assert result == []


def test_get_us_streaming_services_missing_us():
    tmdb_data = {"watch/providers": {"results": {}}}
    result = _get_us_streaming_services(tmdb_data, {"Netflix"})
    assert result == []


def test_get_us_streaming_services_empty_data():
    result = _get_us_streaming_services({}, {"Netflix"})
    assert result == []


# ---------------------------------------------------------------------------
# enricher.poster_url
# ---------------------------------------------------------------------------

def test_poster_url_builds_correct_url():
    url = poster_url("/abc123.jpg")
    assert url == "https://image.tmdb.org/t/p/w500/abc123.jpg"


def test_poster_url_no_leading_slash():
    url = poster_url("abc123.jpg")
    assert url.startswith("https://image.tmdb.org/t/p/w500")


# ---------------------------------------------------------------------------
# enricher.MediaItem
# ---------------------------------------------------------------------------

def test_media_item_movie_defaults():
    item = MediaItem(
        title="Test Movie",
        type="movie",
        premiere_date="2024-01-15",
        overview="A test film.",
        poster_url="posters/test.jpg",
        services=["Netflix"],
        genres=["Action"],
        tmdb_id=12345,
        trakt_slug="test-movie",
    )
    assert item.title == "Test Movie"
    assert item.type == "movie"
    assert item.tmdb_rating == 0.0
    assert item.runtime_minutes == 0
    assert item.seasons == 0


def test_media_item_show_fields():
    item = MediaItem(
        title="Test Show",
        type="show",
        premiere_date="2024-03-01",
        overview="A test series.",
        poster_url="",
        services=["Max", "HBO Max"],
        genres=["Drama"],
        tmdb_id=99999,
        trakt_slug="test-show",
        tmdb_rating=8.5,
        seasons=3,
    )
    assert item.type == "show"
    assert item.seasons == 3
    assert item.tmdb_rating == 8.5
    assert len(item.services) == 2


# ---------------------------------------------------------------------------
# report._ALIAS_TO_KEY and _KEY_LABEL
# ---------------------------------------------------------------------------

def test_alias_to_key_covers_all_network_map_aliases():
    for key, aliases in NETWORK_MAP.items():
        for alias in aliases:
            assert alias in _ALIAS_TO_KEY
            assert _ALIAS_TO_KEY[alias] == key


def test_key_label_uses_first_alias():
    for key, aliases in NETWORK_MAP.items():
        assert _KEY_LABEL[key] == aliases[0]


# ---------------------------------------------------------------------------
# report.ReportGenerator._format_date
# ---------------------------------------------------------------------------

def test_format_date_valid():
    result = ReportGenerator._format_date("01-15-2024")
    assert result == "Jan 15, 2024"


def test_format_date_invalid_string():
    result = ReportGenerator._format_date("not-a-date")
    assert result == "not-a-date"


def test_format_date_none():
    result = ReportGenerator._format_date(None)
    assert result == "Unknown"


def test_format_date_empty_string():
    result = ReportGenerator._format_date("")
    assert result == "Unknown"


# ---------------------------------------------------------------------------
# report.ReportGenerator._group_by_service
# ---------------------------------------------------------------------------

def _make_item(title, type_, services, premiere_date="2024-01-01"):
    return MediaItem(
        title=title,
        type=type_,
        premiere_date=premiere_date,
        overview="",
        poster_url="",
        services=services,
        genres=[],
        tmdb_id=1,
        trakt_slug=title.lower().replace(" ", "-"),
    )


def test_group_by_service_single_service(tmp_path, monkeypatch):
    monkeypatch.setattr("src.report.TEMPLATE_DIR", tmp_path)
    rg = ReportGenerator.__new__(ReportGenerator)
    items = [
        _make_item("Movie A", "movie", ["Netflix"]),
        _make_item("Movie B", "movie", ["Netflix"]),
        _make_item("Show C", "show", ["Hulu"]),
    ]
    grouped = rg._group_by_service(items)
    assert "Netflix" in grouped
    assert len(grouped["Netflix"]) == 2
    assert "Hulu" in grouped
    assert len(grouped["Hulu"]) == 1


def test_group_by_service_alias_normalisation(tmp_path, monkeypatch):
    monkeypatch.setattr("src.report.TEMPLATE_DIR", tmp_path)
    rg = ReportGenerator.__new__(ReportGenerator)
    items = [
        _make_item("Movie A", "movie", ["Disney+"]),
        _make_item("Movie B", "movie", ["Disney Plus"]),
    ]
    grouped = rg._group_by_service(items)
    # Both aliases map to the "disney" key whose label is "Disney+"
    assert "Disney+" in grouped
    assert len(grouped["Disney+"]) == 2


def test_group_by_service_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("src.report.TEMPLATE_DIR", tmp_path)
    rg = ReportGenerator.__new__(ReportGenerator)
    assert rg._group_by_service([]) == {}


# ---------------------------------------------------------------------------
# config.Config
# ---------------------------------------------------------------------------

def test_config_defaults():
    from src.config import Config
    cfg = Config()
    assert cfg.SCAN_DAY == "friday"
    assert cfg.SCAN_HOUR == 6
    assert cfg.WEB_PORT == 7777
    assert isinstance(cfg.SERVICES, list)
    assert len(cfg.SERVICES) > 0


def test_config_validate_raises_without_trakt_id():
    from src.config import Config
    cfg = Config()
    cfg.TRAKT_CLIENT_ID = ""
    cfg.TMDB_API_KEY = "dummy"
    with pytest.raises(ValueError, match="TRAKT_CLIENT_ID"):
        cfg.validate()


def test_config_validate_raises_without_tmdb_key():
    from src.config import Config
    cfg = Config()
    cfg.TRAKT_CLIENT_ID = "dummy"
    cfg.TMDB_API_KEY = ""
    with pytest.raises(ValueError, match="TMDB_API_KEY"):
        cfg.validate()


def test_config_validate_passes_with_both_keys():
    from src.config import Config
    cfg = Config()
    cfg.TRAKT_CLIENT_ID = "fake_trakt_id"
    cfg.TMDB_API_KEY = "fake_tmdb_key"
    cfg.validate()  # should not raise


def test_config_services_env_override(monkeypatch):
    monkeypatch.setenv("SERVICES", "netflix,hulu")
    from importlib import reload
    import src.config as cfg_module
    reload(cfg_module)
    assert cfg_module.config.SERVICES == ["netflix", "hulu"]
