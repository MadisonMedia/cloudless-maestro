"""Conditions in the automation editor: the time of day is one of several, or the plan is overridden."""

from __future__ import annotations

from homeassistant.const import CONF_CONDITION, CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import ConditionCheckerType
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
import voluptuous as vol

from .const import DOMAIN
from .helpers import rhythm_for_device, time_of_day_choices
from .model import KEY

CONDITION_IS = "is"
CONDITION_OVERRIDDEN = "is_overridden"
ATTR_TIMES_OF_DAY = "times_of_day"

CONDITION_SCHEMA = cv.DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In((CONDITION_IS, CONDITION_OVERRIDDEN)),
        vol.Optional(ATTR_TIMES_OF_DAY): vol.All(cv.ensure_list, [KEY]),
    }
)


async def async_get_conditions(hass: HomeAssistant, device_id: str) -> list[dict[str, str]]:
    """List the conditions of a rhythm."""
    if rhythm_for_device(hass, device_id) is None:
        return []
    base = {CONF_CONDITION: "device", CONF_DOMAIN: DOMAIN, CONF_DEVICE_ID: device_id}
    return [{**base, CONF_TYPE: kind} for kind in (CONDITION_IS, CONDITION_OVERRIDDEN)]


async def async_get_condition_capabilities(hass: HomeAssistant, config: ConfigType) -> dict[str, vol.Schema]:
    """Offer the times of day of the rhythm."""
    if config.get(CONF_TYPE) != CONDITION_IS:
        return {}
    rhythm = rhythm_for_device(hass, config[CONF_DEVICE_ID])
    if rhythm is None:
        return {}
    return {"extra_fields": vol.Schema({vol.Required(ATTR_TIMES_OF_DAY): cv.multi_select(time_of_day_choices(rhythm))})}


@callback
def async_condition_from_config(hass: HomeAssistant, config: ConfigType) -> ConditionCheckerType:
    """Check the current state of the rhythm."""
    device_id = config[CONF_DEVICE_ID]
    kind = config[CONF_TYPE]
    wanted = set(config.get(ATTR_TIMES_OF_DAY) or ())

    @callback
    def check(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        rhythm = rhythm_for_device(hass, device_id)
        if rhythm is None or rhythm.state is None:
            return False
        if kind == CONDITION_OVERRIDDEN:
            return rhythm.state.pinned or rhythm.plan.day(rhythm.state.today).adjusted
        return rhythm.state.key in wanted

    return check
