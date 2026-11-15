"""The light check: how fast, how exactly and how often a light answers Maestro's commands."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .rules import CRESCENDO_DOMAIN, SOURCE, is_crescendo, is_dimmable, values_of

# Pauses after each command, in seconds: after switching on, during the fade, after switching off.
WAITS = (3.0, 15.0, 3.0)
FADE_SECONDS = 10


async def async_light_check(
    hass: HomeAssistant, entity_id: str, waits: tuple[float, float, float] = WAITS
) -> dict[str, Any]:
    """Switch a light on to 30 %, fade it to 80 % in ten seconds, switch it off, and record every answer.

    The light is brought back to how it was. Returns the protocol and a short reading of it.
    """
    before = hass.states.get(entity_id)
    if before is None:
        raise ValueError(f"{entity_id} does not exist")
    crescendo = is_crescendo(before)
    dimmable = is_dimmable(before)
    started = dt_util.utcnow()
    log: list[dict[str, Any]] = []

    def note(kind: str, text: str, values: dict[str, Any] | None = None) -> None:
        log.append(
            {
                "t": round((dt_util.utcnow() - started).total_seconds(), 2),
                "kind": kind,
                "text": text,
                "values": values,
            }
        )

    @callback
    def changed(event: Event) -> None:
        new = event.data.get("new_state")
        if new is None:
            return
        note("report", new.state, values_of(new))

    unsub = async_track_state_change_event(hass, [entity_id], changed)

    async def send_on(pct: int, transition: int | None) -> None:
        if crescendo:
            data: dict[str, Any] = {ATTR_ENTITY_ID: entity_id, "position": pct, "source": SOURCE}
            if transition is not None:
                data["duration"] = {"seconds": transition}
            await hass.services.async_call(CRESCENDO_DOMAIN, "fade_to", data, blocking=True)
        elif dimmable:
            data = {ATTR_ENTITY_ID: entity_id, "brightness_pct": pct}
            if transition is not None:
                data["transition"] = transition
            await hass.services.async_call("light", "turn_on", data, blocking=True)
        else:
            await hass.services.async_call("light", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True)

    try:
        note("command", "on_30")
        await send_on(30, 0)
        await asyncio.sleep(waits[0])
        if dimmable:
            note("command", "fade_80")
            await send_on(80, FADE_SECONDS)
            await asyncio.sleep(waits[1])
        note("command", "off")
        if crescendo:
            await hass.services.async_call(
                CRESCENDO_DOMAIN, "fade_to", {ATTR_ENTITY_ID: entity_id, "position": 0, "source": SOURCE}, blocking=True
            )
        else:
            await hass.services.async_call("light", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True)
        await asyncio.sleep(waits[2])
    finally:
        unsub()
        await _restore(hass, entity_id, before)

    return {
        "entity_id": entity_id,
        "crescendo": crescendo,
        "dimmable": dimmable,
        "log": log,
        "summary": _read(log, dimmable),
    }


async def _restore(hass: HomeAssistant, entity_id: str, before: Any) -> None:
    values = values_of(before)
    if not values.get("on"):
        return
    if is_crescendo(before):
        await hass.services.async_call(
            CRESCENDO_DOMAIN,
            "fade_to",
            {ATTR_ENTITY_ID: entity_id, "position": values.get("brightness") or 100, "source": SOURCE},
            blocking=True,
        )
        return
    data: dict[str, Any] = {ATTR_ENTITY_ID: entity_id}
    if is_dimmable(before):
        data["brightness_pct"] = round(values.get("brightness") or 100)
        if values.get("kelvin"):
            data["color_temp_kelvin"] = int(values["kelvin"])
        elif values.get("rgb"):
            data["rgb_color"] = [int(c) for c in values["rgb"]]
    await hass.services.async_call("light", "turn_on", data, blocking=True)


def _read(log: list[dict[str, Any]], dimmable: bool) -> dict[str, Any]:
    """Turn the protocol into a few numbers: delay, rounding, intermediate reports."""
    phases: dict[str, list[dict[str, Any]]] = {}
    starts: dict[str, float] = {}
    current = None
    for item in log:
        if item["kind"] == "command":
            current = item["text"]
            starts[current] = item["t"]
            phases[current] = []
        elif current is not None:
            phases[current].append(item)

    def on_reports(phase: str) -> list[dict[str, Any]]:
        return [r for r in phases.get(phase, []) if r["values"] and r["values"].get("on")]

    first = phases.get("on_30", [])
    on_values = [r["values"] for r in on_reports("on_30")]
    fade = on_reports("fade_80")
    reached = [r for r in fade if float(r["values"].get("brightness") or 0) >= 77]
    intermediate = [r for r in fade if 33 < float(r["values"].get("brightness") or 0) < 77]
    off_reports = [r for r in phases.get("off", []) if not (r["values"] or {}).get("on")]
    return {
        "answered": bool(first),
        "delay": round(first[0]["t"] - starts["on_30"], 2) if first else None,
        "rounding": round(float(on_values[-1]["brightness"]) - 30, 1) if on_values and dimmable else None,
        "intermediate": len(intermediate),
        "fade_done_after": round(reached[0]["t"] - starts["fade_80"], 2) if reached else None,
        "off_delay": round(off_reports[0]["t"] - starts["off"], 2) if off_reports else None,
        "reports": sum(1 for i in log if i["kind"] == "report"),
    }


__all__ = ["STATE_ON", "async_light_check"]
