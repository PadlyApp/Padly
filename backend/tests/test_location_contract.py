"""Tests for metro-aware location contract and validation."""

import pytest
import app.services.controlled_vocab as cv
from app.services.location_matching import cities_match, get_metro_options


def _fake_vocab_cache():
    return {
        "states_by_country": {
            "US": {
                "NY": "New York",
                "CA": "California",
            },
            "CA": {
                "ON": "Ontario",
            },
        },
        "city_entries": [],
        "city_name_index": {
            ("US", "NY"): {"new york": "New York"},
            ("US", "CA"): {"san francisco": "San Francisco"},
            ("CA", "ON"): {"toronto": "Toronto"},
        },
        "city_global_map": {
            "new york": "New York",
            "san francisco": "San Francisco",
            "toronto": "Toronto",
        },
        "company_map": {},
        "school_map": {},
        "role_map": {},
    }


def test_get_metro_options_region_filters():
    assert {"value": "NYC", "label": "NYC (New York City Metro)"} in get_metro_options(
        country_code="US", state_code="NY"
    )
    assert {"value": "Bay Area", "label": "Bay Area (San Francisco Metro)"} in get_metro_options(
        country_code="US", state_code="CA"
    )
    assert {"value": "GTA", "label": "GTA (Greater Toronto Area)"} in get_metro_options(
        country_code="CA", state_code="ON"
    )


def test_cities_match_metro_and_canonical():
    assert cities_match("NYC", "New York") is True
    assert cities_match("New York", "NYC") is True
    assert cities_match("Bay Area", "Oakland") is True
    assert cities_match("Toronto", "GTA") is True
    assert cities_match("NYC", "San Francisco") is False


def test_validate_location_accepts_supported_metros(monkeypatch):
    monkeypatch.setattr(cv, "_build_vocab_cache", lambda: _fake_vocab_cache())

    assert cv.validate_location("US", "NY", "NYC") == ("US", "NY", "NYC")
    assert cv.validate_location("US", "CA", "Bay Area") == ("US", "CA", "Bay Area")
    assert cv.validate_location("CA", "ON", "GTA") == ("CA", "ON", "GTA")


def test_validate_location_rejects_invalid_metro_combo(monkeypatch):
    monkeypatch.setattr(cv, "_build_vocab_cache", lambda: _fake_vocab_cache())

    with pytest.raises(ValueError):
        cv.validate_location("US", "NY", "Bay Area")


def test_validate_city_name_accepts_metro(monkeypatch):
    monkeypatch.setattr(cv, "_build_vocab_cache", lambda: _fake_vocab_cache())
    assert cv.validate_city_name("NYC") == "NYC"
    assert cv.validate_city_name("Bay Area") == "Bay Area"


def test_search_cities_global_includes_metro_options(monkeypatch):
    monkeypatch.setattr(cv, "_build_vocab_cache", lambda: _fake_vocab_cache())
    values = [item["value"] for item in cv.search_cities_global("", limit=20)]
    assert "NYC" in values
    assert "Bay Area" in values
    assert "GTA" in values


def test_metro_neighborhoods_map_to_curated_city():
    names = [item["value"] for item in cv.search_neighborhoods("NYC", limit=500)]
    assert "Astoria" in names
    assert cv.validate_neighborhoods("NYC", ["Astoria"]) == ["Astoria"]
