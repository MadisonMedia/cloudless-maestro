"""One switch per rule: off means paused."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import MaestroEntity
from .rhythm import Rhythm


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up a switch for every rule, and follow rules that come and go."""
    rhythm: Rhythm = entry.runtime_data
    known: dict[str, RuleSwitch] = {}

    @callback
    def sync() -> None:
        rules = {r["id"]: r for r in rhythm.options.get("rules", ())}
        new = [RuleSwitch(rhythm, rule_id) for rule_id in rules if rule_id not in known]
        for item in new:
            known[item.rule_id] = item
        if new:
            async_add_entities(new)
        registry = er.async_get(hass)
        for rule_id in [k for k in known if k not in rules]:
            item = known.pop(rule_id)
            if item.entity_id and registry.async_get(item.entity_id):
                registry.async_remove(item.entity_id)

    sync()
    entry.async_on_unload(rhythm.async_add_listener(sync))


class RuleSwitch(MaestroEntity, SwitchEntity):
    """Whether a rule acts. Off: it switches nothing on or off and follows no change."""

    _attr_translation_key = "rule_active"

    def __init__(self, rhythm: Rhythm, rule_id: str) -> None:
        """Initialize."""
        super().__init__(rhythm, f"rule_{rule_id}")
        self.rule_id = rule_id
        self._attr_translation_key = "rule_active"
        self._attr_translation_placeholders = {"name": self._rule().get("name", rule_id)}

    def _rule(self) -> dict[str, Any]:
        return next((r for r in self.rhythm.options.get("rules", ()) if r["id"] == self.rule_id), {})

    @property
    def available(self) -> bool:
        """The switch goes away with its rule."""
        return bool(self._rule())

    @property
    def is_on(self) -> bool:
        """Return whether the rule is active."""
        return bool(self._rule().get("active", True))

    @property
    def icon(self) -> str:
        """Return an icon for the rule."""
        return "mdi:motion-sensor" if self._rule().get("motion") else "mdi:lightbulb-auto-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The lights of the rule and which of them are on."""
        run = self.rhythm.rules.run_by(self.rule_id)
        return {
            "rule": self.rule_id,
            "lights": self._rule().get("lights", []),
            "on": [e for e in self._rule().get("lights", []) if self.hass.states.is_state(e, "on")],
            "pending": {e: d.isoformat() for e, d in run.pending.items()} if run else {},
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Let the rule act again."""
        await self._set_active(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Pause the rule."""
        await self._set_active(False)

    async def _set_active(self, active: bool) -> None:
        entry = self.rhythm.entry
        rules = [{**r, "active": active} if r["id"] == self.rule_id else r for r in entry.options.get("rules", ())]
        self.hass.config_entries.async_update_entry(entry, options={**entry.options, "rules": rules})
        self.rhythm.log(
            {
                "kind": "rule",
                "rule": self.rule_id,
                "name": self._rule().get("name"),
                "what": "active" if active else "paused",
            }
        )


__all__ = ["DOMAIN", "RuleSwitch", "async_setup_entry"]
