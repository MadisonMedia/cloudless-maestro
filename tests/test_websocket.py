"""The websocket API that the card and the settings page use."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.cloudless_maestro.const import DOMAIN

from .conftest import local, sample_options


async def test_list_and_save_settings(
    hass: HomeAssistant, setup_rhythm, hass_ws_client: WebSocketGenerator, freezer: FrozenDateTimeFactory
) -> None:
    client = await hass_ws_client(hass)
    freezer.move_to(local(2026, 11, 9, 11, 30))
    rhythm = await setup_rhythm()
    await client.send_json_auto_id({"type": f"{DOMAIN}/rhythms"})
    result = (await client.receive_json())["result"]
    assert result[0]["title"] == "Wohnung"
    assert result[0]["entities"]["time_of_day"] == "sensor.wohnung_time_of_day"

    options = result[0]["options"]
    options["models"][0]["entries"][2]["at"] = {"kind": "fixed", "time": "11:00"}
    await client.send_json_auto_id(
        {"type": f"{DOMAIN}/rhythm/save", "entry_id": rhythm.entry.entry_id, "title": "Zuhause", "options": options}
    )
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done()
    assert rhythm.state.key == "mittag"
    assert rhythm.entry.title == "Zuhause"


async def test_invalid_settings_are_refused_with_a_message(
    hass: HomeAssistant, setup_rhythm, hass_ws_client: WebSocketGenerator
) -> None:
    rhythm = await setup_rhythm()
    client = await hass_ws_client(hass)
    options = sample_options()
    options["models"][0]["entries"].append({"tod": "morgen", "at": {"kind": "fixed", "time": "20:00"}})
    await client.send_json_auto_id(
        {"type": f"{DOMAIN}/rhythm/save", "entry_id": rhythm.entry.entry_id, "options": options}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert "twice" in response["error"]["message"]


async def test_subscribe_sends_the_state_and_every_change(
    hass: HomeAssistant, setup_rhythm, hass_ws_client: WebSocketGenerator, freezer: FrozenDateTimeFactory
) -> None:
    client = await hass_ws_client(hass)
    freezer.move_to(local(2026, 11, 9, 10))
    rhythm = await setup_rhythm()
    await client.send_json_auto_id({"type": f"{DOMAIN}/subscribe", "entity_id": "sensor.wohnung_time_of_day"})
    assert (await client.receive_json())["success"]
    snapshot = (await client.receive_json())["event"]
    assert snapshot["state"]["key"] == "morgen"
    assert snapshot["state"]["today"] == "2026-11-09"
    assert [d["model"] for d in snapshot["days"]] == ["werktag", "werktag"]
    assert snapshot["next_day_start"] == local(2026, 11, 10, 6, 30).isoformat()
    assert snapshot["segments"][0]["key"] in ("nacht", "aufstehen", "morgen")

    await client.send_json_auto_id(
        {
            "type": f"{DOMAIN}/pin",
            "entry_id": rhythm.entry.entry_id,
            "time_of_day": "abend",
            "until": "duration",
            "minutes": 90,
        }
    )
    messages = [await client.receive_json(), await client.receive_json()]
    event = next(m for m in messages if m["type"] == "event")["event"]
    assert event["state"]["key"] == "abend"
    assert event["state"]["pin_end"] == local(2026, 11, 9, 11, 30).isoformat()


async def test_adjust_and_clear_single_changes(
    hass: HomeAssistant, setup_rhythm, hass_ws_client: WebSocketGenerator, freezer: FrozenDateTimeFactory
) -> None:
    client = await hass_ws_client(hass)
    freezer.move_to(local(2026, 11, 9, 10))
    rhythm = await setup_rhythm()
    await client.send_json_auto_id(
        {
            "type": f"{DOMAIN}/adjust",
            "entry_id": rhythm.entry.entry_id,
            "times": {"einschlafen": "23:15"},
            "end": "00:15+1",
        }
    )
    assert (await client.receive_json())["success"]
    assert set(rhythm.data["adjustments"]["2026-11-09"]["times"]) == {"einschlafen"}
    await client.send_json_auto_id(
        {
            "type": f"{DOMAIN}/adjust",
            "entry_id": rhythm.entry.entry_id,
            "clear_times": ["einschlafen"],
            "clear_end": True,
        }
    )
    assert (await client.receive_json())["success"]
    assert "2026-11-09" not in rhythm.data["adjustments"]

    await client.send_json_auto_id(
        {
            "type": f"{DOMAIN}/adjust",
            "entry_id": rhythm.entry.entry_id,
            "times": {"mittag": "13:00"},
            "day": "2026-11-14",
        }
    )
    response = await client.receive_json()
    assert not response["success"]


async def test_preview_and_month(
    hass: HomeAssistant, setup_rhythm, hass_ws_client: WebSocketGenerator, freezer: FrozenDateTimeFactory
) -> None:
    client = await hass_ws_client(hass)
    freezer.move_to(local(2026, 11, 9, 10))
    rhythm = await setup_rhythm()
    options = sample_options()
    options["models"][0]["entries"][3]["at"] = {"kind": "sun", "event": "sunset", "offset": 0, "latest": "21:00"}
    await client.send_json_auto_id(
        {
            "type": f"{DOMAIN}/preview",
            "entry_id": rhythm.entry.entry_id,
            "options": options,
            "model": "werktag",
            "dates": ["2026-06-21", "2026-12-21"],
        }
    )
    summer, winter = (await client.receive_json())["result"]
    assert summer["entries"][3]["key"] == "abend"
    assert summer["entries"][3]["start"] != winter["entries"][3]["start"]

    await rhythm.async_adjust_day(None, model="wochenende")
    await client.send_json_auto_id(
        {"type": f"{DOMAIN}/month", "entry_id": rhythm.entry.entry_id, "start": "2026-11-09", "days": 7}
    )
    days = (await client.receive_json())["result"]
    assert [d["model"] for d in days] == [
        "wochenende",
        "werktag",
        "werktag",
        "werktag",
        "werktag",
        "wochenende",
        "wochenende",
    ]
    assert days[0]["source"] == "adjustment"


async def test_create_and_delete(hass: HomeAssistant, setup_rhythm, hass_ws_client: WebSocketGenerator) -> None:
    await setup_rhythm()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/rhythm/create", "title": "Terrarium", "template": "empty"})
    entry_id = (await client.receive_json())["result"]["entry_id"]
    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(entry_id).title == "Terrarium"
    await client.send_json_auto_id({"type": f"{DOMAIN}/rhythm/delete", "entry_id": entry_id})
    assert (await client.receive_json())["success"]
    assert hass.config_entries.async_get_entry(entry_id) is None


async def test_templates_and_diagnostics(hass: HomeAssistant, setup_rhythm, hass_ws_client: WebSocketGenerator) -> None:
    rhythm = await setup_rhythm()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/templates", "language": "de"})
    names = [t["name"] for t in (await client.receive_json())["result"]]
    assert names[0] == "Aufstehen"
    await rhythm.async_pin("nacht", "reset")
    await client.send_json_auto_id({"type": f"{DOMAIN}/diagnostics", "entry_id": rhythm.entry.entry_id})
    log = (await client.receive_json())["result"]["log"]
    assert log[0]["kind"] in ("change", "pin")
