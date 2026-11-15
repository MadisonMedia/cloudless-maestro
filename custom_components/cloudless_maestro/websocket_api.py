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

from .check import async_light_check
from .const import CONF_PALETTE, CONF_TEMPLATE, DOMAIN
from .frontend import async_set_sidebar, sidebar_shown
from .helpers import rhythm_for_entity, rhythm_for_entry
from .model import PALETTE_HA, PALETTES, TEMPLATES, normalize_options, service_time, time_of_day_templates
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
        ws_rule_test,
        ws_rule_toggle,
        ws_action_test,
        ws_resume_fade,
        ws_forget,
        ws_light_check,
        ws_sidebar,
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
        vol.Optional("palette", default=PALETTE_HA): vol.In(PALETTES),
        vol.Optional("options"): dict,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_create(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Create a rhythm through the regular config flow, from a template or from imported settings."""
    options = None
    if msg.get("options") is not None:
        try:
            options = normalize_options(msg["options"])
        except vol.Invalid as err:
            connection.send_error(msg["id"], ERR_INVALID, str(err))
            return
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: msg["title"], CONF_TEMPLATE: msg["template"], CONF_PALETTE: msg["palette"]}
    )
    if result["type"] is not FlowResultType.CREATE_ENTRY:
        connection.send_error(msg["id"], "create_failed", str(result.get("errors")))
        return
    entry = result["result"]
    if options is not None:
        hass.config_entries.async_update_entry(entry, options=options)
    connection.send_result(msg["id"], {"entry_id": entry.entry_id})


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


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/templates",
        vol.Optional("language"): str,
        vol.Optional("palette", default=PALETTE_HA): vol.In(PALETTES),
    }
)
@websocket_api.require_admin
@callback
def ws_templates(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return the templates for new times of day."""
    language = (msg.get("language") or hass.config.language or "en").split("-")[0]
    connection.send_result(msg["id"], time_of_day_templates(language, msg["palette"]))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/refresh_calendars", vol.Required("entry_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_refresh_calendars(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Read the linked calendars again."""
    rhythm = _rhythm(hass, connection, msg)
    if rhythm is not None:
        await rhythm.async_refresh_calendars()
        connection.send_result(msg["id"], rhythm.diagnostics())


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/rule/test",
        vol.Required("entry_id"): str,
        vol.Required("rule"): str,
        vol.Required("time_of_day"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_rule_test(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Apply a rule's row for a time of day now, to see it on the lights."""
    rhythm = _rhythm(hass, connection, msg)
    if rhythm is None:
        return
    run = rhythm.rules.run_by(msg["rule"])
    if run is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Rule not found")
        return
    await _run(connection, msg, rhythm.rules.async_test(run, msg["time_of_day"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/rule/toggle",
        **TARGET,
        vol.Required("rule"): str,
        vol.Optional("mode", default="toggle"): vol.In(("toggle", "on", "off")),
    }
)
@websocket_api.async_response
async def ws_rule_toggle(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Switch a rule's lights, like a button of the rule would."""
    rhythm = _rhythm(hass, connection, msg)
    if rhythm is None:
        return
    run = rhythm.rules.run_by(msg["rule"])
    if run is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Rule not found")
        return
    await _run(connection, msg, rhythm.rules.async_toggle(run, msg["mode"]))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/forget", **TARGET, vol.Optional("lights"): [str]})
@websocket_api.async_response
async def ws_forget(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Forget what was set by hand, for some lights or all."""
    rhythm = _rhythm(hass, connection, msg)
    if rhythm is not None:
        await _run(connection, msg, rhythm.rules.async_forget(msg.get("lights")))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/light_check", vol.Required("entity_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_light_check(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Run the light check and return its protocol."""
    try:
        result = await async_light_check(hass, msg["entity_id"])
    except (ValueError, ServiceValidationError) as err:
        connection.send_error(msg["id"], ERR_INVALID, str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/sidebar", vol.Optional("show"): bool})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_sidebar(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Show whether the page is in the sidebar, or put it there or take it out."""
    if "show" in msg:
        await async_set_sidebar(hass, msg["show"])
    connection.send_result(msg["id"], {"sidebar": sidebar_shown(hass)})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/action/test",
        vol.Required("entry_id"): str,
        vol.Required("rule"): str,
        vol.Required("index"): vol.All(int, vol.Range(min=0)),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_action_test(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Carry out one action of a rule now."""
    rhythm = _rhythm(hass, connection, msg)
    if rhythm is None:
        return
    run = rhythm.rules.run_by(msg["rule"])
    if run is None or msg["index"] >= len(run.rule["actions"]):
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Action not found")
        return
    await _run(connection, msg, rhythm.rules.async_test_action(run, msg["index"]))


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/fade/resume", **TARGET, vol.Optional("lights"): [str]}
)
@websocket_api.async_response
async def ws_resume_fade(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Continue fades that were stopped by hand."""
    rhythm = _rhythm(hass, connection, msg)
    if rhythm is not None:
        await _run(connection, msg, rhythm.rules.async_resume_fades(msg.get("lights")))
