"""Triggers in the automation editor: a time of day begins or ends, or the time of day changes."""

from __future__ import annotations

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .const import ATTR_TIME_OF_DAY, DOMAIN, EVENT_CHANGED
from .helpers import rhythm_for_device, time_of_day_choices
from .model import KEY

TRIGGER_BEGINS = "begins"
TRIGGER_ENDS = "ends"
TRIGGER_CHANGES = "changes"

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In((TRIGGER_BEGINS, TRIGGER_ENDS, TRIGGER_CHANGES)),
        vol.Optional(ATTR_TIME_OF_DAY): KEY,
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, str]]:
    """List the triggers of a rhythm."""
    if rhythm_for_device(hass, device_id) is None:
        return []
    base = {CONF_PLATFORM: "device", CONF_DOMAIN: DOMAIN, CONF_DEVICE_ID: device_id}
    return [{**base, CONF_TYPE: kind} for kind in (TRIGGER_BEGINS, TRIGGER_ENDS, TRIGGER_CHANGES)]


async def async_get_trigger_capabilities(hass: HomeAssistant, config: ConfigType) -> dict[str, vol.Schema]:
    """Offer the times of day of the rhythm for begins and ends."""
    if config.get(CONF_TYPE) == TRIGGER_CHANGES:
        return {}
    rhythm = rhythm_for_device(hass, config[CONF_DEVICE_ID])
    if rhythm is None:
        return {}
    return {"extra_fields": vol.Schema({vol.Required(ATTR_TIME_OF_DAY): vol.In(time_of_day_choices(rhythm))})}


async def async_attach_trigger(
    hass: HomeAssistant, config: ConfigType, action: TriggerActionType, trigger_info: TriggerInfo
) -> CALLBACK_TYPE:
    """Listen for the change event of the rhythm."""
    data = {CONF_DEVICE_ID: config[CONF_DEVICE_ID]}
    if config[CONF_TYPE] == TRIGGER_BEGINS:
        data["to"] = config[ATTR_TIME_OF_DAY]
    elif config[CONF_TYPE] == TRIGGER_ENDS:
        data["from"] = config[ATTR_TIME_OF_DAY]
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: EVENT_CHANGED,
            event_trigger.CONF_EVENT_DATA: data,
        }
    )
    return await event_trigger.async_attach_trigger(hass, event_config, action, trigger_info, platform_type="device")
