"""A rhythm in Home Assistant: entities, changes on time, pins, day adjustments, restarts and calendars."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import async_capture_events, async_fire_time_changed

from custom_components.cloudless_maestro.const import DOMAIN, EVENT_CHANGED

from .conftest import local, sample_options

SENSOR = "sensor.wohnung_tageszeit"
MODEL = "sensor.wohnung_tagesmodell"
NEXT = "sensor.wohnung_nachster_wechsel"
SELECT = "select.wohnung_tageszeit_wahlen"
OVERRIDDEN = "binary_sensor.wohnung_ubersteuert"


@pytest.fixture(autouse=True)
def _german(hass: HomeAssistant) -> None:
    hass.config.language = "de"


async def move_to(hass: HomeAssistant, freezer: FrozenDateTimeFactory, moment) -> None:
    freezer.move_to(moment)
    async_fire_time_changed(hass, moment)
    await hass.async_block_till_done()


async def test_entities_show_the_current_time_of_day(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(local(2026, 11, 9, 10))
    await setup_rhythm()
    state = hass.states.get(SENSOR)
    assert state.state == "morgen"
    assert state.attributes["name"] == "Morgen"
    assert state.attributes["next"] == "mittag"
    assert state.attributes["icon"] == "mdi:coffee-outline"
    assert hass.states.get(MODEL).state == "werktag"
    assert hass.states.get(MODEL).attributes["source"] == "week"
    assert hass.states.get(NEXT).state == "2026-11-09T11:00:00+00:00"
    assert hass.states.get(SELECT).state == "morgen"
    assert hass.states.get(SELECT).attributes["options"] == [
        "aufstehen",
        "morgen",
        "mittag",
        "abend",
        "einschlafen",
        "nacht",
    ]
    assert hass.states.get(OVERRIDDEN).state == "off"


async def test_the_time_of_day_changes_on_time_with_one_event(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(local(2026, 11, 9, 11, 59))
    rhythm = await setup_rhythm()
    events = async_capture_events(hass, EVENT_CHANGED)
    await move_to(hass, freezer, local(2026, 11, 9, 12))
    assert hass.states.get(SENSOR).state == "mittag"
    assert len(events) == 1
    assert events[0].data == {
        "entry_id": rhythm.entry.entry_id,
        "device_id": rhythm.device_id,
        "rhythm": "Wohnung",
        "from": "morgen",
        "to": "mittag",
        "reason": "plan",
    }
    # Minute ticks in between do not fire again.
    await move_to(hass, freezer, local(2026, 11, 9, 12, 5))
    assert len(events) == 1


async def test_pin_and_resume(hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(local(2026, 11, 9, 18))
    await setup_rhythm()
    events = async_capture_events(hass, EVENT_CHANGED)
    await hass.services.async_call(DOMAIN, "pin", {"time_of_day": "einschlafen", "entity_id": SENSOR}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(SENSOR).state == "einschlafen"
    assert hass.states.get(OVERRIDDEN).state == "on"
    assert hass.states.get(OVERRIDDEN).attributes["pin_end"] == local(2026, 11, 9, 23, 30).isoformat()
    assert events[-1].data["reason"] == "pin"
    # The plan's Abend at 19:00 does not end the pin.
    await move_to(hass, freezer, local(2026, 11, 9, 19, 1))
    assert hass.states.get(SENSOR).state == "einschlafen"
    await hass.services.async_call(DOMAIN, "resume", {"entity_id": SENSOR}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(SENSOR).state == "abend"
    assert events[-1].data["reason"] == "resume"
    assert hass.states.get(OVERRIDDEN).state == "off"


async def test_a_pin_ends_on_time(hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(local(2026, 11, 9, 22))
    rhythm = await setup_rhythm()
    await hass.services.async_call(
        DOMAIN, "pin", {"time_of_day": "abend", "until": "duration", "duration": {"hours": 1}}, blocking=True
    )
    await move_to(hass, freezer, local(2026, 11, 9, 22, 45))
    assert hass.states.get(SENSOR).state == "abend"
    await move_to(hass, freezer, local(2026, 11, 9, 23))
    assert hass.states.get(SENSOR).state == "einschlafen"
    assert rhythm.data["pin"] is None


async def test_choosing_in_the_select_pins(hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(local(2026, 11, 9, 5))
    await setup_rhythm()
    assert hass.states.get(SENSOR).state == "nacht"
    await hass.services.async_call(
        "select", "select_option", {"entity_id": SELECT, "option": "aufstehen"}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(SENSOR).state == "aufstehen"
    await move_to(hass, freezer, local(2026, 11, 9, 6, 30))
    assert hass.states.get(SENSOR).state == "aufstehen"
    await move_to(hass, freezer, local(2026, 11, 9, 7))
    assert hass.states.get(SENSOR).state == "morgen"
    assert hass.states.get(OVERRIDDEN).state == "off"


async def test_only_times_of_day_of_today_can_be_pinned(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(local(2026, 11, 14, 10))
    await setup_rhythm()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "pin", {"time_of_day": "mittag"}, blocking=True)


async def test_adjust_a_day_in_advance(hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(local(2026, 11, 9, 10))
    rhythm = await setup_rhythm()
    await hass.services.async_call(
        DOMAIN, "adjust_day", {"times": {"einschlafen": "23:30"}, "end": "00:30+1"}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(OVERRIDDEN).state == "on"
    assert hass.states.get(OVERRIDDEN).attributes["kinds"] == ["adjustment"]
    assert rhythm.data["adjustments"]["2026-11-09"]["times"]["einschlafen"]["time"] == "23:30"
    await move_to(hass, freezer, local(2026, 11, 9, 22, 45))
    assert hass.states.get(SENSOR).state == "abend"
    await move_to(hass, freezer, local(2026, 11, 9, 23, 45))
    assert hass.states.get(SENSOR).state == "einschlafen"
    await move_to(hass, freezer, local(2026, 11, 10, 0, 30))
    assert hass.states.get(SENSOR).state == "nacht"


async def test_another_model_for_a_date_and_back(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(local(2026, 11, 9, 7, 30))
    await setup_rhythm()
    await hass.services.async_call(DOMAIN, "adjust_day", {"date": "2026-11-09", "model": "wochenende"}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(MODEL).state == "wochenende"
    assert hass.states.get(MODEL).attributes["source"] == "adjustment"
    assert hass.states.get(SENSOR).state == "nacht"
    await hass.services.async_call(DOMAIN, "clear_day", {"date": "2026-11-09"}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(MODEL).state == "werktag"
    assert hass.states.get(SENSOR).state == "morgen"


async def test_an_unknown_time_of_day_in_an_adjustment_is_refused(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(local(2026, 11, 14, 10))
    await setup_rhythm()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "adjust_day", {"times": {"mittag": "12:00"}}, blocking=True)


async def test_exactly_one_change_after_a_restart(
    hass: HomeAssistant, hass_storage: dict[str, Any], setup_rhythm, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(local(2026, 11, 9, 12, 30))
    hass_storage[f"{DOMAIN}.restart"] = {
        "version": 1,
        "key": f"{DOMAIN}.restart",
        "data": {"pin": None, "adjustments": {}, "calendar": {}, "last": {"key": "aufstehen"}, "log": []},
    }
    events = async_capture_events(hass, EVENT_CHANGED)
    await setup_rhythm(entry_id="restart")
    assert [(e.data["from"], e.data["to"], e.data["reason"]) for e in events] == [("aufstehen", "mittag", "restart")]


async def test_no_change_after_a_restart_with_the_same_time_of_day(
    hass: HomeAssistant, hass_storage: dict[str, Any], setup_rhythm, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(local(2026, 11, 9, 12, 30))
    pin = {"key": "abend", "day": "2026-11-09", "mode": "reset", "set_at": local(2026, 11, 9, 12).isoformat()}
    hass_storage[f"{DOMAIN}.same"] = {
        "version": 1,
        "key": f"{DOMAIN}.same",
        "data": {"pin": pin, "adjustments": {}, "calendar": {}, "last": {"key": "abend"}, "log": []},
    }
    events = async_capture_events(hass, EVENT_CHANGED)
    await setup_rhythm(entry_id="same")
    assert hass.states.get(SENSOR).state == "abend"
    assert not events


async def test_new_settings_apply_at_once(hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(local(2026, 11, 9, 11, 30))
    rhythm = await setup_rhythm()
    options = sample_options()
    options["models"][0]["entries"][2]["at"] = {"kind": "fixed", "time": "11:00"}
    hass.config_entries.async_update_entry(rhythm.entry, options=options)
    await hass.async_block_till_done()
    assert hass.states.get(SENSOR).state == "mittag"


async def test_a_calendar_decides_the_model(hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(local(2026, 12, 24, 9))
    calls: list[dict[str, Any]] = []

    async def get_events(call: ServiceCall) -> ServiceResponse:
        calls.append(dict(call.data))
        return {
            "calendar.feiertage": {
                "events": [
                    {"start": "2026-12-25", "end": "2026-12-27", "summary": "Weihnachten"},
                    {"start": "2026-12-24T14:00:00+01:00", "end": "2026-12-24T20:00:00+01:00", "summary": "Bescherung"},
                ]
            }
        }

    hass.services.async_register("calendar", "get_events", get_events, supports_response=SupportsResponse.ONLY)
    options = sample_options(
        calendar_links=[
            {"calendar": "calendar.feiertage", "match": "weihnacht", "model": "wochenende"},
        ]
    )
    rhythm = await setup_rhythm(options=options)
    await rhythm.async_refresh_calendars()
    await hass.async_block_till_done()
    assert calls
    assert rhythm.plan.choice(local(2026, 12, 24, 0).date()).model == "werktag"
    assert rhythm.plan.choice(local(2026, 12, 25, 0).date()).source == "calendar"
    assert rhythm.plan.choice(local(2026, 12, 26, 0).date()).detail == "Weihnachten"
    assert rhythm.plan.choice(local(2026, 12, 27, 0).date()).model == "wochenende"
    assert rhythm.plan.choice(local(2026, 12, 27, 0).date()).source == "week"


async def test_an_unreachable_calendar_keeps_the_last_events(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(local(2026, 12, 24, 9))
    answer: dict[str, Any] = {"fail": False}

    async def get_events(call: ServiceCall) -> ServiceResponse:
        if answer["fail"]:
            raise RuntimeError("calendar offline")
        return {
            "calendar.feiertage": {"events": [{"start": "2026-12-25", "end": "2026-12-26", "summary": "Weihnachten"}]}
        }

    hass.services.async_register("calendar", "get_events", get_events, supports_response=SupportsResponse.ONLY)
    rhythm = await setup_rhythm(
        options=sample_options(calendar_links=[{"calendar": "calendar.feiertage", "model": "wochenende"}])
    )
    await rhythm.async_refresh_calendars()
    answer["fail"] = True
    await rhythm.async_refresh_calendars()
    assert rhythm.plan.choice(local(2026, 12, 25, 0).date()).source == "calendar"
    assert rhythm.diagnostics()["calendars"]["calendar.feiertage"]["error"] == "calendar offline"


async def test_the_device_carries_the_rhythm_name(hass: HomeAssistant, setup_rhythm) -> None:
    rhythm = await setup_rhythm()
    device = dr.async_get(hass).async_get(rhythm.device_id)
    assert device.name == "Wohnung"
    hass.config_entries.async_update_entry(rhythm.entry, title="Zuhause")
    await hass.async_block_till_done()
    assert dr.async_get(hass).async_get(rhythm.device_id).name == "Zuhause"


async def test_progress_follows_the_time_of_day(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(local(2026, 11, 9, 9, 30))
    await setup_rhythm()
    assert float(hass.states.get("sensor.wohnung_fortschritt").state) == 50.0
    await move_to(hass, freezer, local(2026, 11, 9, 10, 45))
    assert float(hass.states.get("sensor.wohnung_fortschritt").state) == 75.0
    assert timedelta(hours=1)
