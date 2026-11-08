"""Websocket API for the settings page and the card."""

from __future__ import annotations

from datetime import date, timedelta
import json
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
import voluptuous as vol

from .const import CONF_TEMPLATE, DOMAIN
from .helpers import rhythm_for_entity, rhythm_for_entry
from .model import TEMPLATES, normalize_options, service_time, time_of_day_templates
from .rhythm import Rhythm
from .schedule import PIN_MODES, Plan

ERR_INVALID = "invalid"


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register all commands."""
    for command in (
        ws_rhythms,
        ws_save,
        ws_create,
        ws_delete,
        ws_preview,
        ws_month,
        ws_subscribe,
        ws_pin,
        ws_resume,
        ws_adjust,
        ws_clear_day,
        ws_diagnostics,
        ws_templates,
        ws_refresh_calendars,
    ):
        websocket_api.async_register_command(hass, command)


def _entities(hass: HomeAssistant, entry_id: str) -> dict[str, str]:
    """Return the rhythm's entity ids by their key."""
    out = {}
    for item in er.async_entries_for_config_entry(er.async_get(hass), entry_id):
        out[item.unique_id.removeprefix(f"{entry_id}_")] = item.entity_id
    return out


def _describe(hass: HomeAssistant, rhythm: Rhythm) -> dict[str, Any]:
    return {
        "entry_id": rhythm.entry.entry_id,
        "title": rhythm.title,
        "device_id": rhythm.device_id,
        "options": rhythm.options,
        "entities": _entities(hass, rhythm.entry.entry_id),
    }


def _rhythm(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> Rhythm | None:
    rhythm = None
    if msg.get("entry_id"):
        rhythm = rhythm_for_entry(hass, msg["entry_id"])
    elif msg.get("entity_id"):
        rhythm = rhythm_for_entity(hass, msg["entity_id"])
    if rhythm is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Rhythm not found")
    return rhythm


TARGET = {vol.Exclusive("entry_id", "target"): str, vol.Exclusive("entity_id", "target"): str}


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/rhythms"})
@websocket_api.require_admin
@callback
def ws_rhythms(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """List all rhythms with their settings."""
    rhythms = [e.runtime_data for e in hass.config_entries.async_loaded_entries(DOMAIN)]
    connection.send_result(msg["id"], [_describe(hass, r) for r in sorted(rhythms, key=lambda r: r.title.casefold())])


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/rhythm/save",
        vol.Required("entry_id"): str,
        vol.Optional("title"): vol.All(str, vol.Strip, vol.Length(min=1, max=60)),
        vol.Required("options"): dict,
    }
)
@websocket_api.require_admin
@callback
def ws_save(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Validate and store a rhythm's settings. They apply at once."""
    rhythm = _rhythm(hass, connection, msg)
    if rhythm is None:
        return
    try:
        options = normalize_options(msg["options"])
    except vol.Invalid as err:
        connection.send_error(msg["id"], ERR_INVALID, str(err))
        return
    entry = rhythm.entry
    hass.config_entries.async_update_entry(entry, title=msg.get("title", entry.title), options=options)
    connection.send_result(msg["id"], {"options": options})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/rhythm/create",
        vol.Required("title"): vol.All(str, vol.Strip, vol.Length(min=1, max=60)),
        vol.Optional("template", default=TEMPLATES[0]): vol.In(TEMPLATES),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_create(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Create a rhythm through the regular config flow."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: msg["title"], CONF_TEMPLATE: msg["template"]}
    )
    if result["type"] is not FlowResultType.CREATE_ENTRY:
        connection.send_error(msg["id"], "create_failed", str(result.get("errors")))
        return
    connection.send_result(msg["id"], {"entry_id": result["result"].entry_id})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/rhythm/delete", vol.Required("entry_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_delete(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Delete a rhythm."""
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Rhythm not found")
        return
    await hass.config_entries.async_remove(entry.entry_id)
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/preview",
        vol.Required("entry_id"): str,
        vol.Required("options"): dict,
        vol.Required("model"): str,
        vol.Required("dates"): vol.All([cv.date], vol.Length(min=1, max=14)),
    }
)
@websocket_api.require_admin
@callback
def ws_preview(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Compute a day model for chosen dates with unsaved settings, to compare summer and winter."""
    rhythm = _rhythm(hass, connection, msg)
    if rhythm is None:
        return
    try:
        options = normalize_options(msg["options"])
    except vol.Invalid as err:
        connection.send_error(msg["id"], ERR_INVALID, str(err))
        return
    week = dict.fromkeys(options["week"], msg["model"])
    plan = Plan({**options, "week": week}, rhythm.tz, rhythm.make_sun(options))
    result = []
    for day in msg["dates"]:
        item = plan.day(day)
        result.append(
            {
                "day": day.isoformat(),
                "entries": [{"key": e.key, "start": e.start.isoformat()} for e in item.entries],
                "end": item.end.isoformat() if item.end else None,
                "dropped": list(item.dropped),
            }
        )
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/month",
        **TARGET,
        vol.Required("start"): cv.date,
        vol.Optional("days", default=42): vol.All(int, vol.Range(min=1, max=62)),
    }
)
@callback
def ws_month(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return the model of each date in a range, and where it comes from."""
    rhythm = _rhythm(hass, connection, msg)
    if rhythm is None:
        return
    out = []
    start: date = msg["start"]
    for n in range(msg["days"]):
        day = start + timedelta(days=n)
        choice = rhythm.plan.choice(day)
        out.append(
            {
                "day": day.isoformat(),
                "model": choice.model,
                "source": choice.source,
                "detail": choice.detail,
                "adjustment": rhythm.data["adjustments"].get(day.isoformat()),
            }
        )
    connection.send_result(msg["id"], out)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe", **TARGET})
@callback
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Send the rhythm's state now and after every change."""
    rhythm = _rhythm(hass, connection, msg)
    if rhythm is None:
        return
    last: list[str] = [""]

    @callback
    def send() -> None:
        snapshot = rhythm.snapshot()
        fingerprint = json.dumps({k: v for k, v in snapshot.items() if k != "now"}, sort_keys=True, default=str)
        if fingerprint == last[0]:
            return
        last[0] = fingerprint
        connection.send_message(websocket_api.event_message(msg["id"], snapshot))

    connection.subscriptions[msg["id"]] = rhythm.async_add_listener(send)
    connection.send_result(msg["id"])
    send()


async def _run(connection: websocket_api.ActiveConnection, msg: dict, coro) -> None:
    try:
        await coro
    except (ServiceValidationError, vol.Invalid) as err:
        connection.send_error(msg["id"], ERR_INVALID, str(err))
        return
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/pin",
        **TARGET,
        vol.Required("time_of_day"): str,
        vol.Optional("until", default="next_change"): vol.In(PIN_MODES),
        vol.Optional("minutes"): vol.All(int, vol.Range(min=1, max=7 * 24 * 60)),
        vol.Optional("time"): cv.time,
    }
)
@websocket_api.async_response
async def ws_pin(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Pin a time of day."""
    rhythm = _rhythm(hass, connection, msg)
    if rhythm is None:
        return
    minutes = msg.get("minutes")
    duration = timedelta(minutes=minutes) if minutes else None
    await _run(connection, msg, rhythm.async_pin(msg["time_of_day"], msg["until"], duration, msg.get("time")))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/resume", **TARGET})
@websocket_api.async_response
async def ws_resume(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return to the plan."""
    rhythm = _rhythm(hass, connection, msg)
    if rhythm is not None:
        await _run(connection, msg, rhythm.async_resume())


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/adjust",
        **TARGET,
        vol.Optional("day"): cv.date,
        vol.Optional("model"): vol.Any(None, str),
        vol.Optional("times"): {str: service_time},
        vol.Optional("end"): service_time,
        vol.Optional("clear_times"): [str],
        vol.Optional("clear_end", default=False): bool,
        vol.Optional("clear_model", default=False): bool,
    }
)
@websocket_api.async_response
async def ws_adjust(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Change a single date: another model, other times, or remove single changes again."""
    rhythm = _rhythm(hass, connection, msg)
    if rhythm is None:
        return
    day = rhythm.resolve_day(msg.get("day"))
    await _run(
        connection,
        msg,
        rhythm.async_adjust_day(
            day,
            msg.get("model"),
            msg.get("times"),
            msg.get("end"),
            clear_times=msg.get("clear_times"),
            clear_end=msg["clear_end"],
            clear_model=msg["clear_model"],
        ),
    )


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/clear_day", **TARGET, vol.Optional("day"): cv.date})
@websocket_api.async_response
async def ws_clear_day(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Remove a day adjustment."""
    rhythm = _rhythm(hass, connection, msg)
    if rhythm is not None:
        await _run(connection, msg, rhythm.async_clear_day(msg.get("day")))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/diagnostics", vol.Required("entry_id"): str})
@websocket_api.require_admin
@callback
def ws_diagnostics(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return the log of changes and decisions."""
    rhythm = _rhythm(hass, connection, msg)
    if rhythm is not None:
        connection.send_result(msg["id"], rhythm.diagnostics())


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/templates", vol.Optional("language"): str})
@websocket_api.require_admin
@callback
def ws_templates(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return the templates for new times of day."""
    language = (msg.get("language") or hass.config.language or "en").split("-")[0]
    connection.send_result(msg["id"], time_of_day_templates(language))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/refresh_calendars", vol.Required("entry_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_refresh_calendars(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Read the linked calendars again."""
    rhythm = _rhythm(hass, connection, msg)
    if rhythm is not None:
        await rhythm.async_refresh_calendars()
        connection.send_result(msg["id"], rhythm.diagnostics())
