"""Cloudless Maestro: one daily schedule of freely named times of day."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import target as target_helpers
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .const import (
    ATTR_DATE,
    ATTR_DURATION,
    ATTR_END,
    ATTR_MODEL,
    ATTR_TIME,
    ATTR_TIME_OF_DAY,
    ATTR_TIMES,
    ATTR_UNTIL,
    DOMAIN,
    PANEL_URL,
    SERVICE_ADJUST_DAY,
    SERVICE_CLEAR_DAY,
    SERVICE_PIN,
    SERVICE_REFRESH_CALENDARS,
    SERVICE_RESUME,
    STORAGE_VERSION,
)
from .frontend import async_register_frontend
from .model import KEY, service_time
from .rhythm import Rhythm
from .schedule import PIN_MODES, PIN_NEXT_CHANGE
from .websocket_api import async_register_websocket_commands

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SELECT, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type MaestroConfigEntry = ConfigEntry[Rhythm]


def rhythms_for_call(call: ServiceCall) -> list[Rhythm]:
    """Return the rhythms an action targets. Without a target, the only rhythm there is."""
    hass = call.hass
    loaded = {e.entry_id: e.runtime_data for e in hass.config_entries.async_loaded_entries(DOMAIN)}
    selection = target_helpers.TargetSelection(call.data)
    if not selection.has_any_target:
        if len(loaded) == 1:
            return list(loaded.values())
        raise ServiceValidationError("Choose a rhythm: there is more than one")
    referenced = target_helpers.async_extract_referenced_entity_ids(hass, selection, True)
    entries: set[str] = set()
    devices = dr.async_get(hass)
    for device_id in referenced.referenced_devices:
        device = devices.async_get(device_id)
        if device is not None:
            entries.update(device.config_entries)
    entities = er.async_get(hass)
    for entity_id in referenced.referenced | referenced.indirectly_referenced:
        item = entities.async_get(entity_id)
        if item is not None and item.config_entry_id:
            entries.add(item.config_entry_id)
    found = [loaded[e] for e in entries if e in loaded]
    if not found:
        raise ServiceValidationError("The target is not a Maestro rhythm")
    return found


def _times(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise vol.Invalid("times map a time of day to a time, for example einschlafen: 23:30")
    return {KEY(k): service_time(v) for k, v in value.items()}


SERVICES: dict[str, tuple[dict[Any, Any], Callable[[Rhythm, ServiceCall], Awaitable[None]]]] = {
    SERVICE_PIN: (
        {
            vol.Required(ATTR_TIME_OF_DAY): KEY,
            vol.Optional(ATTR_UNTIL, default=PIN_NEXT_CHANGE): vol.In(PIN_MODES),
            vol.Optional(ATTR_DURATION): cv.positive_time_period,
            vol.Optional(ATTR_TIME): cv.time,
        },
        lambda r, c: r.async_pin(
            c.data[ATTR_TIME_OF_DAY], c.data[ATTR_UNTIL], c.data.get(ATTR_DURATION), c.data.get(ATTR_TIME)
        ),
    ),
    SERVICE_RESUME: ({}, lambda r, c: r.async_resume()),
    SERVICE_ADJUST_DAY: (
        {
            vol.Optional(ATTR_DATE): cv.date,
            vol.Optional(ATTR_MODEL): KEY,
            vol.Optional(ATTR_TIMES): _times,
            vol.Optional(ATTR_END): service_time,
        },
        lambda r, c: r.async_adjust_day(
            c.data.get(ATTR_DATE), c.data.get(ATTR_MODEL), c.data.get(ATTR_TIMES), c.data.get(ATTR_END)
        ),
    ),
    SERVICE_CLEAR_DAY: ({vol.Optional(ATTR_DATE): cv.date}, lambda r, c: r.async_clear_day(c.data.get(ATTR_DATE))),
    SERVICE_REFRESH_CALENDARS: ({}, lambda r, c: r.async_refresh_calendars()),
}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register actions, the websocket API, the card and the settings page."""

    def handler(func: Callable[[Rhythm, ServiceCall], Awaitable[None]]):
        async def handle(call: ServiceCall) -> None:
            for rhythm in rhythms_for_call(call):
                await func(rhythm, call)

        return handle

    for name, (fields, func) in SERVICES.items():
        hass.services.async_register(
            DOMAIN, name, handler(func), schema=vol.Schema({**cv.ENTITY_SERVICE_FIELDS, **fields})
        )
    async_register_websocket_commands(hass)
    await async_register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MaestroConfigEntry) -> bool:
    """Set up a rhythm."""
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Cloudless",
        model="Maestro",
        entry_type=dr.DeviceEntryType.SERVICE,
        configuration_url=f"homeassistant://{PANEL_URL}",
    )
    rhythm = Rhythm(hass, entry, device.id)
    entry.runtime_data = rhythm
    await rhythm.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MaestroConfigEntry) -> bool:
    """Unload a rhythm."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete what a rhythm stored."""
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()


async def _async_entry_updated(hass: HomeAssistant, entry: MaestroConfigEntry) -> None:
    """Apply new settings without a reload."""
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if device.name != entry.title:
            registry.async_update_device(device.id, name=entry.title)
    rhythm = getattr(entry, "runtime_data", None)
    if rhythm is not None:
        rhythm.options_changed()
