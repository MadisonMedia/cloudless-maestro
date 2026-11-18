"""The websocket API that the card and the settings page use."""

from __future__ import annotations

from unittest.mock import patch

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


async def test_rules_are_tested_forgotten_and_the_sidebar_toggles(
    hass: HomeAssistant, setup_rhythm, hass_ws_client: WebSocketGenerator, freezer: FrozenDateTimeFactory
) -> None:
    from pytest_homeassistant_custom_component.common import async_mock_service

    from .test_rules import BAD, FakeLights, rule_options

    lights = FakeLights(hass, [BAD])
    client = await hass_ws_client(hass)
    freezer.move_to(local(2026, 11, 9, 10))
    rhythm = await setup_rhythm(options=rule_options())
    async_mock_service(hass, "cloudless_crescendo", "set_on_position")

    async def ask(msg: dict) -> dict:
        await client.send_json_auto_id(msg)
        return await client.receive_json()

    res = await ask(
        {"type": f"{DOMAIN}/rule/test", "entry_id": rhythm.entry.entry_id, "rule": "bad", "time_of_day": "abend"}
    )
    assert res["success"]
    assert lights.pct(BAD) == 60
    res = await ask(
        {"type": f"{DOMAIN}/rule/test", "entry_id": rhythm.entry.entry_id, "rule": "nope", "time_of_day": "abend"}
    )
    assert not res["success"]
    lights.by_hand(BAD, "on", brightness=255)
    await hass.async_block_till_done()
    assert rhythm.rules.overridden()
    res = await ask({"type": f"{DOMAIN}/forget", "entry_id": rhythm.entry.entry_id})
    assert res["success"] and not rhythm.rules.overridden()
    res = await ask({"type": f"{DOMAIN}/rule/toggle", "entry_id": rhythm.entry.entry_id, "rule": "Bad"})
    assert res["success"] and hass.states.get(BAD).state == "off"
    res = await ask({"type": f"{DOMAIN}/diagnostics", "entry_id": rhythm.entry.entry_id})
    assert res["result"]["rules"][0]["id"] == "bad"
    assert res["result"]["state"]["key"] == "morgen"
    # The sidebar flag is stored; the frontend itself is patched away in the tests.
    with (
        patch("custom_components.cloudless_maestro.websocket_api.async_set_sidebar") as set_sidebar,
        patch("custom_components.cloudless_maestro.websocket_api.sidebar_shown", return_value=False),
    ):
        res = await ask({"type": f"{DOMAIN}/sidebar", "show": False})
    assert res["result"] == {"sidebar": False}
    set_sidebar.assert_awaited_once_with(hass, False)


async def test_a_rhythm_can_be_created_from_imported_settings(
    hass: HomeAssistant, setup_rhythm, hass_ws_client: WebSocketGenerator
) -> None:
    client = await hass_ws_client(hass)
    await setup_rhythm()
    options = sample_options()
    options["base"]["name"] = "Ruhe"
    await client.send_json_auto_id(
        {"type": f"{DOMAIN}/rhythm/create", "title": "Import", "options": options, "palette": "earth"}
    )
    res = await client.receive_json()
    assert res["success"]
    entry = hass.config_entries.async_get_entry(res["result"]["entry_id"])
    assert entry.title == "Import"
    assert entry.options["base"]["name"] == "Ruhe"
    await client.send_json_auto_id({"type": f"{DOMAIN}/rhythm/create", "title": "Broken", "options": {"base": {}}})
    res = await client.receive_json()
    assert not res["success"]


async def test_a_save_from_an_old_page_does_not_overwrite_changes_made_elsewhere(
    hass: HomeAssistant, setup_rhythm, hass_ws_client: WebSocketGenerator, freezer: FrozenDateTimeFactory
) -> None:
    client = await hass_ws_client(hass)
    freezer.move_to(local(2026, 11, 9, 11, 30))
    rhythm = await setup_rhythm(options=sample_options(rules=[{"id": "bad", "name": "Bad"}]))
    await client.send_json_auto_id({"type": f"{DOMAIN}/rhythms"})
    page = (await client.receive_json())["result"][0]
    # The rule is paused with its switch while the page is open.
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.wohnung_rule_bad"}, blocking=True)
    await hass.async_block_till_done()
    assert rhythm.options["rules"][0]["active"] is False
    options = page["options"]
    options["times_of_day"][0]["name"] = "Wach werden"
    await client.send_json_auto_id(
        {"type": f"{DOMAIN}/rhythm/save", "entry_id": rhythm.entry.entry_id, "options": options, "rev": page["rev"]}
    )
    response = await client.receive_json()
    assert not response["success"] and response["error"]["code"] == "changed_elsewhere"
    assert rhythm.options["rules"][0]["active"] is False
    # With the current revision it saves, and the answer carries the next one.
    await client.send_json_auto_id({"type": f"{DOMAIN}/rhythms"})
    page = (await client.receive_json())["result"][0]
    page["options"]["times_of_day"][0]["name"] = "Wach werden"
    await client.send_json_auto_id(
        {
            "type": f"{DOMAIN}/rhythm/save",
            "entry_id": rhythm.entry.entry_id,
            "options": page["options"],
            "rev": page["rev"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await hass.async_block_till_done()
    await client.send_json_auto_id({"type": f"{DOMAIN}/rhythms"})
    assert (await client.receive_json())["result"][0]["rev"] == response["result"]["rev"]
