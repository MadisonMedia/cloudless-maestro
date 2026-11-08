"""Sensors of a rhythm: the time of day, today's model, the next change and the progress."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .entity import MaestroEntity
from .rhythm import Rhythm


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up a rhythm's sensors."""
    rhythm: Rhythm = entry.runtime_data
    async_add_entities([TimeOfDaySensor(rhythm), ModelSensor(rhythm), NextChangeSensor(rhythm), ProgressSensor(rhythm)])


class TimeOfDaySensor(MaestroEntity, SensorEntity):
    """The time of day that applies now. Its state is the stable key."""

    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, rhythm: Rhythm) -> None:
        """Initialize."""
        super().__init__(rhythm, "time_of_day")

    @property
    def options(self) -> list[str]:
        """Return all keys: the base state and every time of day."""
        options = self.rhythm.options
        return [options["base"]["key"], *(t["key"] for t in options["times_of_day"])]

    @property
    def native_value(self) -> str | None:
        """Return the key of the current time of day."""
        return self.rhythm.state.key if self.rhythm.state else None

    @property
    def icon(self) -> str | None:
        """Return the icon of the current time of day."""
        item = self.rhythm.time_of_day(self.native_value)
        return item["icon"] if item else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Name, look and times of the current time of day."""
        rhythm, state = self.rhythm, self.rhythm.state
        if state is None:
            return {}
        item = rhythm.time_of_day(state.key) or {}
        return {
            "name": item.get("name"),
            "color": item.get("color"),
            "since": state.since.isoformat(),
            "until": state.until.isoformat() if state.until else None,
            "next": state.next_key,
            "next_name": rhythm.name_of(state.next_key),
            "today": state.today.isoformat(),
            "pinned": state.pinned,
            "planned": state.planned,
            "rhythm": rhythm.entry.entry_id,
        }


class ModelSensor(MaestroEntity, SensorEntity):
    """Today's day model and where it comes from."""

    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, rhythm: Rhythm) -> None:
        """Initialize."""
        super().__init__(rhythm, "model")

    @property
    def options(self) -> list[str]:
        """Return all model keys."""
        return [m["key"] for m in self.rhythm.options["models"]]

    @property
    def native_value(self) -> str | None:
        """Return the key of today's model."""
        state = self.rhythm.state
        return self.rhythm.plan.day(state.today).model if state else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Name and source of the model."""
        state = self.rhythm.state
        if state is None:
            return {}
        day = self.rhythm.plan.day(state.today)
        model = self.rhythm.plan.model(day.model) or {}
        return {
            "name": model.get("name"),
            "source": day.source,
            "detail": day.detail,
            "adjusted": day.adjusted,
            "today": state.today.isoformat(),
        }


class NextChangeSensor(MaestroEntity, SensorEntity):
    """When the time of day changes next."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, rhythm: Rhythm) -> None:
        """Initialize."""
        super().__init__(rhythm, "next_change")

    @property
    def native_value(self) -> datetime | None:
        """Return the moment of the next change."""
        state = self.rhythm.state
        return state.until if state else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The time of day that comes next."""
        state = self.rhythm.state
        if state is None:
            return {}
        return {"next": state.next_key, "next_name": self.rhythm.name_of(state.next_key)}


class ProgressSensor(MaestroEntity, SensorEntity):
    """How far the current time of day has run, so other devices can follow it."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0

    def __init__(self, rhythm: Rhythm) -> None:
        """Initialize."""
        super().__init__(rhythm, "progress")

    @property
    def native_value(self) -> float | None:
        """Return the share of the current time of day that has passed."""
        state = self.rhythm.state
        if state is None or state.until is None:
            return None
        total = (state.until - state.since).total_seconds()
        if total <= 0:
            return None
        done = (dt_util.now() - state.since).total_seconds()
        return round(max(0.0, min(100.0, done * 100 / total)), 1)
