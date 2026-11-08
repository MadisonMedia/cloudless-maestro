"""Small lookups shared by triggers, conditions and the websocket API."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .rhythm import Rhythm


def rhythm_for_entry(hass: HomeAssistant, entry_id: str) -> Rhythm | None:
    """Return the running rhythm of a config entry."""
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        return None
    return getattr(entry, "runtime_data", None)


def rhythm_for_device(hass: HomeAssistant, device_id: str) -> Rhythm | None:
    """Return the running rhythm of a device."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return None
    for entry_id in device.config_entries:
        if (rhythm := rhythm_for_entry(hass, entry_id)) is not None:
            return rhythm
    return None


def rhythm_for_entity(hass: HomeAssistant, entity_id: str) -> Rhythm | None:
    """Return the running rhythm of one of its entities."""
    item = er.async_get(hass).async_get(entity_id)
    if item is None or item.platform != DOMAIN or item.config_entry_id is None:
        return None
    return rhythm_for_entry(hass, item.config_entry_id)


def time_of_day_choices(rhythm: Rhythm) -> dict[str, str]:
    """Return keys and names of the base state and all times of day."""
    items = [rhythm.options["base"], *rhythm.options["times_of_day"]]
    return {t["key"]: t["name"] for t in items}
