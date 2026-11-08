"""Whether the plan is overridden: by a pin or a day adjustment for today."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MaestroEntity
from .rhythm import Rhythm


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up a rhythm's binary sensor."""
    async_add_entities([OverriddenSensor(entry.runtime_data)])


class OverriddenSensor(MaestroEntity, BinarySensorEntity):
    """On while a time of day is pinned or today is adjusted."""

    def __init__(self, rhythm: Rhythm) -> None:
        """Initialize."""
        super().__init__(rhythm, "overridden")

    def _kinds(self) -> list[str]:
        state = self.rhythm.state
        if state is None:
            return []
        kinds = []
        if state.pinned:
            kinds.append("pin")
        if self.rhythm.plan.day(state.today).adjusted:
            kinds.append("adjustment")
        return kinds

    @property
    def is_on(self) -> bool:
        """Return whether anything overrides the plan."""
        return bool(self._kinds())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """What overrides the plan, and until when."""
        state = self.rhythm.state
        return {
            "kinds": self._kinds(),
            "pinned": state.key if state and state.pinned else None,
            "pin_end": state.pin_end.isoformat() if state and state.pin_end else None,
        }
