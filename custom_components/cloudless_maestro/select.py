"""Choose a time of day: the choice pins it until the next change."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MaestroEntity
from .rhythm import Rhythm
from .schedule import PIN_NEXT_CHANGE


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up a rhythm's select."""
    async_add_entities([TimeOfDaySelect(entry.runtime_data)])


class TimeOfDaySelect(MaestroEntity, SelectEntity):
    """The current time of day. Choosing one pins it until the plan catches up."""

    def __init__(self, rhythm: Rhythm) -> None:
        """Initialize."""
        super().__init__(rhythm, "choose")

    @property
    def options(self) -> list[str]:
        """Return the times of day of today's model and the base state."""
        if self.rhythm.state is None:
            return [self.rhythm.options["base"]["key"]]
        options = self.rhythm.choosable()
        current = self.rhythm.state.key
        return options if current in options else [*options, current]

    @property
    def current_option(self) -> str | None:
        """Return the current time of day."""
        return self.rhythm.state.key if self.rhythm.state else None

    @property
    def icon(self) -> str | None:
        """Return the icon of the current time of day."""
        item = self.rhythm.time_of_day(self.current_option)
        return item["icon"] if item else None

    async def async_select_option(self, option: str) -> None:
        """Pin the chosen time of day until the next change."""
        await self.rhythm.async_pin(option, PIN_NEXT_CHANGE)
