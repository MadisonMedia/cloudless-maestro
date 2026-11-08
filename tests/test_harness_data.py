"""What the card and the page receive is plain JSON. Optionally writes it for the frontend harness.

Run with MAESTRO_WRITE_HARNESS=1 to refresh tests/frontend/harness-data.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.cloudless_maestro.const import DOMAIN

from .conftest import local, sample_options

TARGET = Path(__file__).parent / "frontend" / "harness-data.json"


async def test_answers_are_plain_json(
    hass: HomeAssistant, setup_rhythm, hass_ws_client: WebSocketGenerator, freezer: FrozenDateTimeFactory
) -> None:
    hass.config.language = "de"
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
    options["times_of_day"][2]["color"] = "#7cc6e8"
    options["times_of_day"][3]["color"] = "#c46bae"
    options["times_of_day"][4]["color"] = "#6c63b5"
    options["times_of_day"][2]["icon"] = "mdi:white-balance-sunny"
    options["times_of_day"][3]["icon"] = "mdi:weather-sunset-down"
    options["times_of_day"][4]["icon"] = "mdi:bed-outline"
    options["base"]["color"] = "#2e3a6b"
    options["calendar_links"] = [{"calendar": "calendar.feiertage", "match": "", "model": "wochenende"}]
    rhythm = await setup_rhythm(options=options)
    await rhythm.async_adjust_day(None, times={"einschlafen": {"kind": "fixed", "time": "23:00"}})
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
        "templates": await ask({"type": f"{DOMAIN}/templates", "language": "de"}),
    }
    await rhythm.async_pin("einschlafen", "next_change")
    data["pinned"] = json.loads(json.dumps(rhythm.snapshot()))
    assert data["snapshot"]["state"]["key"] == "abend"
    if os.environ.get("MAESTRO_WRITE_HARNESS"):
        TARGET.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
