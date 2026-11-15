"""What the card and the page receive is plain JSON. Optionally writes it for the frontend harness.

Run with MAESTRO_WRITE_HARNESS=1 to refresh tests/frontend/harness-data.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_mock_service
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.cloudless_maestro.const import DOMAIN
from custom_components.cloudless_maestro.model import normalize_options

from .conftest import local, sample_options

TARGET = Path(__file__).parent / "frontend" / "harness-data.json"


async def test_answers_are_plain_json(
    hass: HomeAssistant, setup_rhythm, hass_ws_client: WebSocketGenerator, freezer: FrozenDateTimeFactory
) -> None:
    language = os.environ.get("MAESTRO_HARNESS_LANG", "de")
    hass.config.language = language
    client = await hass_ws_client(hass)
    freezer.move_to(local(2026, 11, 9, 19, 10))
    options = sample_options()
    options["models"][0]["entries"][3]["at"] = {
        "kind": "sun",
        "event": "sunset",
        "offset": 60,
        "earliest": "18:30",
        "latest": "21:00",
    }
    options["calendar_links"] = [{"calendar": "calendar.feiertage", "match": "", "model": "wochenende"}]
    options["rules"] = [
        {
            "id": "bad",
            "name": "Bad",
            "lights": ["light.bad"],
            "motion": ["binary_sensor.bewegung_bad"],
            "buttons": [{"entity": "event.taster_bad", "event": "single"}],
            "lux": {"sensor": "sensor.helligkeit_bad", "below": 20},
            "rows": {
                "nacht": {"react": "on", "brightness": 10, "after": 2},
                "aufstehen": {"react": "on", "brightness": 5, "fade": True},
                "morgen": {"react": "on", "brightness": 100, "after": 3},
                "mittag": {"react": "on", "brightness": 100, "after": 3},
                "abend": {"react": "on", "brightness": 20, "fade": True, "fade_to": 60},
                "einschlafen": {"react": "on", "brightness": 25, "after": 2, "begin": "follow"},
            },
            "actions": [
                {"entity": "climate.heizung_bad", "tod": "aufstehen", "edge": "start", "offset": -60, "value": 23},
                {"entity": "climate.heizung_bad", "tod": "morgen", "edge": "end", "offset": 0, "value": 19},
            ],
        },
        {
            "id": "wohnzimmer",
            "name": "Wohnzimmer",
            "lights": ["light.wohnzimmer", "light.regal"],
            "motion": [],
            "rows": {
                "nacht": {"react": "off_only", "begin": "off"},
                "aufstehen": {"react": "on", "brightness": 30, "color": {"kelvin": 2700}},
                "morgen": {"react": "on", "brightness": 70, "color": {"kelvin": 3500}},
                "mittag": {"react": "on", "brightness": 100, "color": {"kelvin": 4000}, "begin": "keep"},
                "abend": {"react": "on", "brightness": 45, "color": {"kelvin": 2700}, "begin": "follow"},
                "einschlafen": {"react": "on", "brightness": 15, "color": {"kelvin": 2200}, "begin": "follow"},
            },
            "actions": [
                {
                    "entity": "climate.heizung_wohnzimmer",
                    "tod": "aufstehen",
                    "edge": "start",
                    "offset": -60,
                    "value": 21,
                },
                {"entity": "cover.rollo_wohnzimmer", "tod": "aufstehen", "edge": "start", "offset": 0, "value": 100},
                {"entity": "scene.gemuetlich", "tod": "abend", "edge": "start", "offset": 0, "value": "on"},
                {"entity": "cover.rollo_wohnzimmer", "tod": "abend", "edge": "end", "offset": 0, "value": 0},
                {
                    "entity": "climate.heizung_wohnzimmer",
                    "tod": "einschlafen",
                    "edge": "start",
                    "offset": 15,
                    "value": 18,
                },
            ],
        },
    ]
    options = normalize_options(options)
    for entity_id, state, attrs in [
        (
            "light.bad",
            "on",
            {
                "friendly_name": "Bad",
                "crescendo": True,
                "crescendo_api": 1,
                "position": 60,
                "brightness": 153,
                "buttons": [
                    {"name": "Nacht", "position": 25},
                    {"name": "Morgen", "position": 50},
                    {"name": "Hell", "position": 100},
                ],
            },
        ),
        (
            "light.wohnzimmer",
            "off",
            {
                "friendly_name": "Wohnzimmer",
                "supported_color_modes": ["color_temp"],
                "entity_id": ["light.stehlampe", "light.decke"],
            },
        ),
        ("light.regal", "off", {"friendly_name": "Regal", "supported_color_modes": ["color_temp", "rgb"]}),
        ("binary_sensor.bewegung_bad", "off", {"friendly_name": "Bewegung Bad", "device_class": "motion"}),
        (
            "event.taster_bad",
            "2026-11-09T18:00:00+00:00",
            {"friendly_name": "Taster Bad", "event_type": "single", "event_types": ["single", "double"]},
        ),
        (
            "sensor.helligkeit_bad",
            "12",
            {"friendly_name": "Helligkeit Bad", "device_class": "illuminance", "unit_of_measurement": "lx"},
        ),
        ("cover.rollo_wohnzimmer", "open", {"friendly_name": "Rollo Wohnzimmer", "current_position": 100}),
        ("climate.heizung_bad", "heat", {"friendly_name": "Heizung Bad", "temperature": 19}),
        ("climate.heizung_wohnzimmer", "heat", {"friendly_name": "Heizung Wohnzimmer", "temperature": 21}),
        ("scene.gemuetlich", "unknown", {"friendly_name": "Gemütlich"}),
    ]:
        hass.states.async_set(entity_id, state, attrs)
    for service in ("fade_to", "stop", "set_on_position"):
        async_mock_service(hass, "cloudless_crescendo", service)
    rhythm = await setup_rhythm(options=options)
    rhythm.rules.tracks["light.regal"].memory = {
        "values": {"on": True, "brightness": 80, "kelvin": 3000, "rgb": None},
        "at": local(2026, 11, 9, 19, 0).isoformat(),
    }
    rhythm.rules.tracks["light.regal"].overridden = True
    await rhythm.async_adjust_day(None, times={"einschlafen": {"kind": "fixed", "time": "23:00"}})
    await hass.async_block_till_done()
    await rhythm.rules._start_fade(rhythm.rules.run_by("bad"), "light.bad", "abend")
    # As if the evening fade had started with the evening, from 20 %.
    fade = rhythm.rules.fades["light.bad"]
    fade.start, fade.begin = local(2026, 11, 9, 18, 30), 20.0
    rhythm.log({"kind": "calendar_error", "calendar": "calendar.feiertage", "error": "not loaded"})

    async def ask(msg: dict) -> object:
        await client.send_json_auto_id(msg)
        response = await client.receive_json()
        assert response["success"], response
        return response["result"]

    data = {
        "snapshot": json.loads(json.dumps(rhythm.snapshot())),
        "rhythms": await ask({"type": f"{DOMAIN}/rhythms"}),
        "month": await ask(
            {"type": f"{DOMAIN}/month", "entry_id": rhythm.entry.entry_id, "start": "2026-10-26", "days": 42}
        ),
        "preview": await ask(
            {
                "type": f"{DOMAIN}/preview",
                "entry_id": rhythm.entry.entry_id,
                "options": options,
                "model": "werktag",
                "dates": ["2026-11-09", "2026-06-21", "2026-12-21"],
            }
        ),
        "diagnostics": await ask({"type": f"{DOMAIN}/diagnostics", "entry_id": rhythm.entry.entry_id}),
        "templates": await ask({"type": f"{DOMAIN}/templates", "language": language}),
        "states": {
            e: {"entity_id": e, "state": hass.states.get(e).state, "attributes": dict(hass.states.get(e).attributes)}
            for e in hass.states.async_entity_ids()
            if e.split(".")[0] in ("light", "binary_sensor", "event", "sensor", "cover", "climate", "scene")
        },
    }
    await rhythm.async_pin("einschlafen", "next_change")
    data["pinned"] = json.loads(json.dumps(rhythm.snapshot()))
    assert data["snapshot"]["state"]["key"] == "abend"
    if os.environ.get("MAESTRO_WRITE_HARNESS"):
        target = TARGET if language == "de" else TARGET.with_name(f"harness-data-{language}.json")
        target.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
