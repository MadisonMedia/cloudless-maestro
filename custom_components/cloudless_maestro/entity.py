"""Shared base of all of a rhythm's entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, PANEL_URL
from .rhythm import Rhythm


def device_info(rhythm: Rhythm) -> DeviceInfo:
    """Return the device that stands for a rhythm."""
    return DeviceInfo(
        identifiers={(DOMAIN, rhythm.entry.entry_id)},
        name=rhythm.title,
        manufacturer="Cloudless",
        model="Maestro",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=f"homeassistant://{PANEL_URL}",
    )


class MaestroEntity(Entity):
    """An entity that follows its rhythm."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, rhythm: Rhythm, key: str) -> None:
        """Initialize."""
        self.rhythm = rhythm
        self._attr_unique_id = f"{rhythm.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = device_info(rhythm)

    async def async_added_to_hass(self) -> None:
        """Follow the rhythm."""
        self.async_on_remove(self.rhythm.async_add_listener(self._rhythm_changed))

    def _rhythm_changed(self) -> None:
        if self.hass is not None and self.entity_id and self._state_differs():
            self.async_write_ha_state()

    def _state_differs(self) -> bool:
        """Write the state only when something visible changed."""
        fingerprint = (
            self.state,
            sorted((self.extra_state_attributes or {}).items(), key=str),
            self.icon,
            getattr(self, "options", None),
        )
        if fingerprint == getattr(self, "_last_fingerprint", None):
            return False
        self._last_fingerprint = fingerprint
        return True
