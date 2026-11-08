"""Fixtures for Cloudless Maestro: a rhythm with fixed times in Berlin."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cloudless_maestro.const import DOMAIN
from custom_components.cloudless_maestro.model import normalize_options

pytest_plugins = "pytest_homeassistant_custom_component"

TZ = ZoneInfo("Europe/Berlin")
ALL_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@pytest.fixture(autouse=True)
def _enable(enable_custom_integrations: None) -> None:
    """Allow the custom integration to load."""


@pytest.fixture(autouse=True)
def _no_frontend():
    """The card and the page are not needed in the tests."""
    with patch("custom_components.cloudless_maestro.async_register_frontend", return_value=None):
        yield


def fixed(clock: str, next_day: bool = False) -> dict[str, Any]:
    return {"kind": "fixed", "time": clock, "next_day": next_day}


def local(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=TZ)


def sample_options(**extra: Any) -> dict[str, Any]:
    """Werktag on weekdays, Wochenende on weekends, all with fixed times."""
    tods = [
        {"key": "aufstehen", "name": "Aufstehen", "icon": "mdi:weather-sunset-up", "color": "#f2a65a"},
        {"key": "morgen", "name": "Morgen", "icon": "mdi:coffee-outline", "color": "#f2c94c"},
        {"key": "mittag", "name": "Mittag"},
        {"key": "abend", "name": "Abend"},
        {"key": "einschlafen", "name": "Einschlafen"},
    ]
    werktag = {
        "key": "werktag",
        "name": "Werktag",
        "entries": [
            {"tod": "aufstehen", "at": fixed("06:30")},
            {"tod": "morgen", "at": fixed("07:00")},
            {"tod": "mittag", "at": fixed("12:00")},
            {"tod": "abend", "at": fixed("19:00")},
            {"tod": "einschlafen", "at": fixed("22:30")},
        ],
        "end": fixed("23:30"),
    }
    wochenende = {
        "key": "wochenende",
        "name": "Wochenende",
        "entries": [
            {"tod": "aufstehen", "at": fixed("08:00")},
            {"tod": "morgen", "at": fixed("08:30")},
            {"tod": "abend", "at": fixed("19:00")},
            {"tod": "einschlafen", "at": fixed("23:00")},
        ],
        "end": fixed("00:30", True),
    }
    week = dict.fromkeys(ALL_DAYS[:5], "werktag") | dict.fromkeys(ALL_DAYS[5:], "wochenende")
    return normalize_options(
        {
            "base": {"key": "nacht", "name": "Nacht"},
            "times_of_day": tods,
            "models": [werktag, wochenende],
            "week": week,
            **extra,
        }
    )


@pytest.fixture
async def setup_rhythm(hass: HomeAssistant):
    """Return a helper that sets up a rhythm and returns it."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    hass.config.latitude, hass.config.longitude = 52.52, 13.405
    for component in ("frontend", "panel_custom", "lovelace"):
        hass.config.components.add(component)
    await async_setup_component(hass, "homeassistant", {})
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "websocket_api", {})

    async def _setup(title: str = "Wohnung", options: dict[str, Any] | None = None, entry_id: str | None = None):
        entry = MockConfigEntry(
            domain=DOMAIN, title=title, data={}, options=options or sample_options(), entry_id=entry_id
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry.runtime_data

    return _setup
