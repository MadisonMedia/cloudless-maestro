"""Triggers in the automation editor: a time of day begins or ends, with an offset, or the time of day changes."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .const import ATTR_OFFSET, ATTR_TIME_OF_DAY, DOMAIN, EVENT_CHANGED
from .helpers import rhythm_for_device, time_of_day_choices
from .model import KEY
from .rhythm import Rhythm

TRIGGER_BEGINS = "begins"
TRIGGER_ENDS = "ends"
TRIGGER_CHANGES = "changes"

OFFSET = vol.All(vol.Coerce(int), vol.Range(min=-720, max=720))

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In((TRIGGER_BEGINS, TRIGGER_ENDS, TRIGGER_CHANGES)),
        vol.Optional(ATTR_TIME_OF_DAY): KEY,
        vol.Optional(ATTR_OFFSET, default=0): OFFSET,
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, str]]:
    """List the triggers of a rhythm."""
    if rhythm_for_device(hass, device_id) is None:
        return []
    base = {CONF_PLATFORM: "device", CONF_DOMAIN: DOMAIN, CONF_DEVICE_ID: device_id}
    return [{**base, CONF_TYPE: kind} for kind in (TRIGGER_BEGINS, TRIGGER_ENDS, TRIGGER_CHANGES)]


async def async_get_trigger_capabilities(hass: HomeAssistant, config: ConfigType) -> dict[str, vol.Schema]:
    """Offer the times of day of the rhythm and an offset in minutes for begins and ends."""
    if config.get(CONF_TYPE) == TRIGGER_CHANGES:
        return {}
    rhythm = rhythm_for_device(hass, config[CONF_DEVICE_ID])
    if rhythm is None:
        return {}
    return {
        "extra_fields": vol.Schema(
            {
                vol.Required(ATTR_TIME_OF_DAY): vol.In(time_of_day_choices(rhythm)),
                vol.Optional(ATTR_OFFSET, default=0): OFFSET,
            }
        )
    }


async def async_attach_trigger(
    hass: HomeAssistant, config: ConfigType, action: TriggerActionType, trigger_info: TriggerInfo
) -> CALLBACK_TYPE:
    """Listen for the change event of the rhythm, or for a moment before or after a planned change."""
    offset = int(config.get(ATTR_OFFSET) or 0)
    if offset and config[CONF_TYPE] in (TRIGGER_BEGINS, TRIGGER_ENDS):
        rhythm = rhythm_for_device(hass, config[CONF_DEVICE_ID])
        if rhythm is None:
            return lambda: None
        return _attach_offset(hass, rhythm, config, action, trigger_info, offset)
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


def _next_moment(rhythm: Rhythm, key: str, kind: str, offset: timedelta, now: datetime) -> datetime | None:
    """Return the next moment the trigger fires: a planned begin or end of the time of day, shifted."""
    timeline = rhythm.timeline
    if timeline is None:
        return None
    for segment in timeline.segments:
        if segment.key != key:
            continue
        moment = (segment.start if kind == TRIGGER_BEGINS else segment.end) + offset
        if moment > now:
            return moment
    return None


@callback
def _attach_offset(
    hass: HomeAssistant,
    rhythm: Rhythm,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
    offset_minutes: int,
) -> CALLBACK_TYPE:
    key = config[ATTR_TIME_OF_DAY]
    kind = config[CONF_TYPE]
    offset = timedelta(minutes=offset_minutes)
    timer: list[CALLBACK_TYPE | None] = [None]
    planned: list[datetime | None] = [None]
    fired: list[datetime | None] = [None]
    job = HassJob(action)
    trigger_data = trigger_info["trigger_data"]

    @callback
    def fire(_now: datetime) -> None:
        timer[0] = None
        moment = planned[0]
        if moment is None or moment == fired[0]:
            return
        fired[0] = moment
        hass.async_run_hass_job(
            job,
            {
                "trigger": {
                    **trigger_data,
                    "platform": "device",
                    "type": kind,
                    "time_of_day": key,
                    "offset": offset_minutes,
                    "at": moment.isoformat(),
                    "description": f"{key} {kind} {offset_minutes:+d} min",
                }
            },
        )
        schedule()

    @callback
    def schedule() -> None:
        # A moment that just passed may still be waiting to fire in the same loop turn; keep its timer.
        now = dt_util.utcnow() - timedelta(seconds=30)
        moment = _next_moment(rhythm, key, kind, offset, now)
        if moment == fired[0]:
            moment = _next_moment(rhythm, key, kind, offset, fired[0]) if fired[0] else None
        if moment == planned[0] and timer[0] is not None:
            return
        if timer[0] is not None:
            timer[0]()
            timer[0] = None
        planned[0] = moment
        if moment is not None:
            timer[0] = async_track_point_in_utc_time(hass, fire, moment)

    schedule()
    unsub_listener = rhythm.async_add_listener(schedule)

    @callback
    def remove(*_args: object) -> None:
        unsub_listener()
        unsub_stop()
        if timer[0] is not None:
            timer[0]()
            timer[0] = None

    unsub_stop = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, remove)
    return remove
