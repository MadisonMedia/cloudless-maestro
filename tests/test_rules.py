"""Rules: motion, buttons, switching on by hand, memory, changes of the time of day and devices."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

from custom_components.cloudless_maestro.model import normalize_options

from .conftest import TZ, sample_options

BAD = "light.bad"
REGAL = "light.regal"
MOTION = "binary_sensor.bewegung_bad"
BUTTON = "event.taster_bad"
LUX = "sensor.helligkeit_bad"
COVER = "cover.rollo"

LIGHT_ATTRS = {
    "supported_color_modes": ["color_temp", "rgb"],
    "min_color_temp_kelvin": 2000,
    "max_color_temp_kelvin": 6500,
    "supported_features": 32,
}


class FakeLights:
    """Lights that answer like real ones: the state follows every command, with the caller's context or a new one."""

    def __init__(self, hass: HomeAssistant, ids: list[str], feedback: str = "same") -> None:
        self.hass = hass
        self.feedback = feedback
        self.calls: list[ServiceCall] = []
        for entity_id in ids:
            hass.states.async_set(entity_id, "off", {**LIGHT_ATTRS, "friendly_name": entity_id.split(".")[1].title()})
        hass.services.async_register("light", "turn_on", self._turn_on)
        hass.services.async_register("light", "turn_off", self._turn_off)

    def _context(self, call: ServiceCall) -> Context:
        return call.context if self.feedback == "same" else Context()

    async def _turn_on(self, call: ServiceCall) -> None:
        self.calls.append(call)
        for entity_id in cv.ensure_list(call.data["entity_id"]):
            prev = self.hass.states.get(entity_id)
            attrs = dict(prev.attributes) if prev else dict(LIGHT_ATTRS)
            if "brightness_pct" in call.data:
                attrs["brightness"] = round(call.data["brightness_pct"] * 255 / 100)
            elif "brightness" in call.data:
                attrs["brightness"] = call.data["brightness"]
            elif prev is None or prev.state != "on":
                attrs.setdefault("brightness", 255)
            if "color_temp_kelvin" in call.data:
                attrs["color_temp_kelvin"] = call.data["color_temp_kelvin"]
                attrs["color_mode"] = "color_temp"
                attrs.pop("rgb_color", None)
            elif "rgb_color" in call.data:
                attrs["rgb_color"] = list(call.data["rgb_color"])
                attrs["color_mode"] = "rgb"
                attrs.pop("color_temp_kelvin", None)
            else:
                attrs.setdefault("color_mode", "color_temp")
                attrs.setdefault("color_temp_kelvin", 3000)
            self.hass.states.async_set(entity_id, "on", attrs, context=self._context(call))

    async def _turn_off(self, call: ServiceCall) -> None:
        self.calls.append(call)
        for entity_id in cv.ensure_list(call.data["entity_id"]):
            prev = self.hass.states.get(entity_id)
            attrs = {
                k: v for k, v in (prev.attributes if prev else {}).items() if k in LIGHT_ATTRS or k == "friendly_name"
            }
            self.hass.states.async_set(entity_id, "off", attrs, context=self._context(call))

    def by_hand(self, entity_id: str, state: str, **attrs: Any) -> None:
        """Somebody changes the light outside Home Assistant: a new state with a foreign context."""
        prev = self.hass.states.get(entity_id)
        base = dict(prev.attributes) if prev else dict(LIGHT_ATTRS)
        if state == "off":
            base = {k: v for k, v in base.items() if k in LIGHT_ATTRS or k == "friendly_name"}
        self.hass.states.async_set(entity_id, state, {**base, **attrs}, context=Context())

    def pct(self, entity_id: str) -> int | None:
        state = self.hass.states.get(entity_id)
        if state is None or state.state != "on":
            return None
        return round(state.attributes["brightness"] * 100 / 255)


def rule_options(**rule: Any) -> dict[str, Any]:
    """A rhythm with one motion rule for the bathroom, 40 % during the morning, 10 % at night."""
    base = {
        "id": "bad",
        "name": "Bad",
        "lights": [BAD],
        "motion": [MOTION],
        "manual": True,
        "rows": {
            "aufstehen": {"react": "on", "brightness": 50, "after": 3},
            "morgen": {"react": "on", "brightness": 40, "color": {"kelvin": 3000}, "after": 3},
            "mittag": {"react": "on", "brightness": 100, "after": 3, "begin": "follow"},
            "abend": {"react": "on", "brightness": 60, "after": 3},
            "einschlafen": {"react": "on", "brightness": 20, "after": 2, "begin": "off"},
            "nacht": {"react": "on", "brightness": 10, "after": 1},
        },
    }
    return sample_options(rules=[{**base, **rule}], defaults={"transition": 2, "warn_seconds": 20, "lock": 30})


def local(year: int, month: int, day: int, hour: int, minute: int = 0, second: int = 0):
    return datetime(year, month, day, hour, minute, second, tzinfo=TZ)


async def move_to(hass: HomeAssistant, freezer: FrozenDateTimeFactory, moment) -> None:
    freezer.move_to(moment)
    async_fire_time_changed(hass, moment)
    await hass.async_block_till_done()


async def motion(hass: HomeAssistant, on: bool) -> None:
    hass.states.async_set(MOTION, "on" if on else "off")
    await hass.async_block_till_done()


@pytest.fixture
def lights(hass: HomeAssistant) -> FakeLights:
    return FakeLights(hass, [BAD, REGAL])


async def test_motion_switches_on_with_the_row_and_off_after_the_time(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory, lights: FakeLights
) -> None:
    freezer.move_to(local(2026, 11, 9, 10))
    rhythm = await setup_rhythm(options=rule_options())
    await motion(hass, True)
    assert lights.pct(BAD) == 40
    assert hass.states.get(BAD).attributes["color_temp_kelvin"] == 3000
    assert lights.calls[-1].data["transition"] == 2
    await motion(hass, False)
    # After three minutes the light dims to half as a warning.
    await move_to(hass, freezer, local(2026, 11, 9, 10, 2, 59))
    assert lights.pct(BAD) == 40
    await move_to(hass, freezer, local(2026, 11, 9, 10, 3, 1))
    assert lights.pct(BAD) == 20
    # Twenty seconds later it is off.
    await move_to(hass, freezer, local(2026, 11, 9, 10, 3, 25))
    assert hass.states.get(BAD).state == "off"
    whats = [i["what"] for i in rhythm.data["log"] if i["kind"] == "rule"]
    assert whats == ["motion_on", "prewarn", "off"]
    assert not rhythm.rules.overridden()


async def test_motion_during_the_warning_brings_the_light_back(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory, lights: FakeLights
) -> None:
    freezer.move_to(local(2026, 11, 9, 10))
    await setup_rhythm(options=rule_options())
    await motion(hass, True)
    await motion(hass, False)
    await move_to(hass, freezer, local(2026, 11, 9, 10, 3, 1))
    assert lights.pct(BAD) == 20
    await motion(hass, True)
    assert lights.pct(BAD) == 40
    await move_to(hass, freezer, local(2026, 11, 9, 10, 4))
    assert lights.pct(BAD) == 40
    await motion(hass, False)
    await move_to(hass, freezer, local(2026, 11, 9, 10, 7, 1))
    assert lights.pct(BAD) == 20
    await move_to(hass, freezer, local(2026, 11, 9, 10, 7, 25))
    assert hass.states.get(BAD).state == "off"


async def test_a_value_set_by_hand_is_remembered_and_the_lock_holds_motion_off(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory, lights: FakeLights
) -> None:
    freezer.move_to(local(2026, 11, 9, 10))
    rhythm = await setup_rhythm(options=rule_options())
    await motion(hass, True)
    assert lights.pct(BAD) == 40
    # Somebody turns it up at the wall, then off.
    lights.by_hand(BAD, "on", brightness=255)
    await hass.async_block_till_done()
    assert rhythm.rules.overridden()[0]["overridden"] is True
    await motion(hass, False)
    lights.by_hand(BAD, "off")
    await hass.async_block_till_done()
    assert hass.states.get(BAD).state == "off"
    # Within the lock time motion does nothing.
    await move_to(hass, freezer, local(2026, 11, 9, 10, 0, 20))
    await motion(hass, True)
    assert hass.states.get(BAD).state == "off"
    await motion(hass, False)
    # After it, the light comes back with the remembered value, not the row.
    await move_to(hass, freezer, local(2026, 11, 9, 10, 1))
    await motion(hass, True)
    assert lights.pct(BAD) == 100
    await motion(hass, False)
    lights.by_hand(BAD, "off")
    await hass.async_block_till_done()
    # Once the memory has expired the row applies again.
    await move_to(hass, freezer, local(2026, 11, 9, 10, 20))
    await motion(hass, True)
    assert lights.pct(BAD) == 40
    assert not rhythm.rules.overridden()


async def test_switching_on_by_hand_without_a_value_gets_the_row(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory, lights: FakeLights
) -> None:
    freezer.move_to(local(2026, 11, 9, 10))
    rhythm = await setup_rhythm(options=rule_options())
    # A tile: light.turn_on without data, from a context that is not Maestro's.
    await hass.services.async_call("light", "turn_on", {"entity_id": BAD}, blocking=True, context=Context())
    await hass.async_block_till_done()
    assert lights.pct(BAD) == 40
    assert not rhythm.rules.overridden()
    await hass.services.async_call("light", "turn_off", {"entity_id": BAD}, blocking=True, context=Context())
    await hass.async_block_till_done()
    # "Light to 80 %": a value is chosen, the row does not apply.
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": BAD, "brightness_pct": 80}, blocking=True, context=Context()
    )
    await hass.async_block_till_done()
    assert lights.pct(BAD) == 80
    assert rhythm.rules.overridden()[0]["overridden"] is True


async def test_a_change_of_the_time_of_day_lets_lights_follow_and_switches_off(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory, lights: FakeLights
) -> None:
    freezer.move_to(local(2026, 11, 9, 11, 59))
    options = rule_options(lights=[BAD, REGAL])
    cover_calls = async_mock_service(hass, "cover", "set_cover_position")
    options["rules"][0]["devices"] = [{"entity": COVER, "values": {"mittag": 100, "einschlafen": 0}}]
    rhythm = await setup_rhythm(options=options)
    await motion(hass, True)
    assert lights.pct(BAD) == 40 and lights.pct(REGAL) == 40
    lights.by_hand(REGAL, "on", brightness=128)
    await hass.async_block_till_done()
    # Midday: "follow" takes every light along, also the one changed by hand.
    await move_to(hass, freezer, local(2026, 11, 9, 12, 0, 1))
    assert lights.pct(BAD) == 100 and lights.pct(REGAL) == 100
    assert not rhythm.rules.overridden()
    assert cover_calls[-1].data == {"entity_id": COVER, "position": 100}
    # Evening: "follow, except overridden" leaves a light changed by hand alone.
    lights.by_hand(REGAL, "on", brightness=128)
    await hass.async_block_till_done()
    await move_to(hass, freezer, local(2026, 11, 9, 19, 0, 1))
    assert lights.pct(BAD) == 60 and lights.pct(REGAL) == 50
    # Bedtime switches the lights off.
    await move_to(hass, freezer, local(2026, 11, 9, 22, 30, 1))
    assert hass.states.get(BAD).state == "off" and hass.states.get(REGAL).state == "off"
    assert cover_calls[-1].data == {"entity_id": COVER, "position": 0}


async def test_a_button_toggles_and_the_row_time_switches_off_again(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory, lights: FakeLights
) -> None:
    freezer.move_to(local(2026, 11, 9, 10))
    hass.states.async_set(
        BUTTON, "2026-11-09T08:00:00+00:00", {"event_type": "single", "event_types": ["single", "double"]}
    )
    options = rule_options(motion=[], buttons=[{"entity": BUTTON, "event": "single"}])
    await setup_rhythm(options=options)

    async def press(event_type: str, at: str) -> None:
        hass.states.async_set(BUTTON, at, {"event_type": event_type, "event_types": ["single", "double"]})
        await hass.async_block_till_done()

    await press("double", "2026-11-09T09:00:01+00:00")
    assert hass.states.get(BAD).state == "off"
    await press("single", "2026-11-09T09:00:02+00:00")
    assert lights.pct(BAD) == 40
    await press("single", "2026-11-09T09:00:03+00:00")
    assert hass.states.get(BAD).state == "off"
    await press("single", "2026-11-09T09:00:04+00:00")
    assert lights.pct(BAD) == 40
    # Without motion, the row's time counts from the press: the warning, then off.
    await move_to(hass, freezer, local(2026, 11, 9, 10, 3, 1))
    assert lights.pct(BAD) == 20
    await move_to(hass, freezer, local(2026, 11, 9, 10, 3, 25))
    assert hass.states.get(BAD).state == "off"


async def test_too_bright_means_no_light_and_a_paused_rule_does_nothing(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory, lights: FakeLights
) -> None:
    freezer.move_to(local(2026, 11, 9, 10))
    hass.states.async_set(LUX, "250")
    rhythm = await setup_rhythm(options=rule_options(lux={"sensor": LUX, "below": 20}))
    await motion(hass, True)
    assert hass.states.get(BAD).state == "off"
    await motion(hass, False)
    hass.states.async_set(LUX, "5")
    await motion(hass, True)
    assert lights.pct(BAD) == 40
    await motion(hass, False)
    lights.by_hand(BAD, "off")
    await hass.async_block_till_done()
    switch = next(e for e in hass.states.async_entity_ids("switch") if e.startswith("switch."))
    assert hass.states.get(switch).state == "on"
    await hass.services.async_call("switch", "turn_off", {"entity_id": switch}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(switch).state == "off"
    assert rhythm.options["rules"][0]["active"] is False
    await move_to(hass, freezer, local(2026, 11, 9, 10, 5))
    await motion(hass, True)
    assert hass.states.get(BAD).state == "off"


async def test_a_light_switched_on_by_another_rule_counts_as_manual(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory, lights: FakeLights
) -> None:
    freezer.move_to(local(2026, 11, 9, 10))
    options = rule_options(manual_after="never")
    bright = {
        "id": "bad_hell",
        "name": "Bad hell",
        "lights": [BAD],
        "motion": [],
        "buttons": [{"entity": BUTTON, "event": None}],
        "rows": {"morgen": {"react": "on", "brightness": 100}},
    }
    options["rules"].append(bright)
    hass.states.async_set(BUTTON, "2026-11-09T08:00:00+00:00", {"event_type": "single"})
    rhythm = await setup_rhythm(options=options)
    hass.states.async_set(BUTTON, "2026-11-09T09:00:01+00:00", {"event_type": "single"})
    await hass.async_block_till_done()
    assert lights.pct(BAD) == 100
    # The motion rule sees a light it did not switch on and, with "never", leaves it alone.
    await motion(hass, True)
    await motion(hass, False)
    await move_to(hass, freezer, local(2026, 11, 9, 10, 10))
    assert lights.pct(BAD) == 100
    assert rhythm.rules.run_by("Bad hell") is not None
    # The action toggles the bright rule off again.
    await hass.services.async_call("cloudless_maestro", "toggle_rule", {"rule": "bad_hell"}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(BAD).state == "off"


async def test_feedback_with_a_foreign_context_is_still_recognized_as_own(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory
) -> None:
    lights = FakeLights(hass, [BAD, REGAL], feedback="new")
    freezer.move_to(local(2026, 11, 9, 10))
    rhythm = await setup_rhythm(options=rule_options())
    await motion(hass, True)
    assert lights.pct(BAD) == 40
    assert not rhythm.rules.overridden()
    # A rounded report during the transition is no override either.
    lights.by_hand(BAD, "on", brightness=99)
    await hass.async_block_till_done()
    assert not rhythm.rules.overridden()


async def test_memory_survives_a_restart(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory, lights: FakeLights
) -> None:
    freezer.move_to(local(2026, 11, 9, 10))
    rhythm = await setup_rhythm(options=rule_options(), entry_id="r1")
    await motion(hass, True)
    lights.by_hand(BAD, "on", brightness=255)
    await hass.async_block_till_done()
    await motion(hass, False)
    lights.by_hand(BAD, "off")
    await hass.async_block_till_done()
    assert rhythm.rules.overridden()
    await hass.config_entries.async_unload("r1")
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup("r1")
    await hass.async_block_till_done()
    rhythm = hass.config_entries.async_get_entry("r1").runtime_data
    assert rhythm.rules.overridden()[0]["memory"]["values"]["brightness"] == 100
    await hass.services.async_call("cloudless_maestro", "forget", {}, blocking=True)
    await hass.async_block_till_done()
    assert not rhythm.rules.overridden()


async def test_the_light_check_reads_delay_and_rounding(hass: HomeAssistant, setup_rhythm, lights: FakeLights) -> None:
    from custom_components.cloudless_maestro.check import async_light_check

    await setup_rhythm(options=rule_options())
    result = await async_light_check(hass, BAD, waits=(0, 0, 0))
    assert result["summary"]["answered"] is True
    assert result["summary"]["rounding"] == pytest.approx(-0.2, abs=0.5)
    assert [i["text"] for i in result["log"] if i["kind"] == "command"] == ["on_30", "fade_80", "off"]
    assert hass.states.get(BAD).state == "off"


async def test_a_trigger_with_an_offset_fires_before_the_planned_begin(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory
) -> None:
    from homeassistant.setup import async_setup_component

    freezer.move_to(local(2026, 11, 9, 11))
    rhythm = await setup_rhythm(options=rule_options())
    calls = async_mock_service(hass, "test", "automation")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "device",
                    "domain": "cloudless_maestro",
                    "device_id": rhythm.device_id,
                    "type": "begins",
                    "time_of_day": "abend",
                    "offset": -15,
                },
                "action": {"service": "test.automation", "data": {"at": "{{ trigger.at }}"}},
            }
        },
    )
    await hass.async_block_till_done()
    await move_to(hass, freezer, local(2026, 11, 9, 18, 44))
    assert not calls
    await move_to(hass, freezer, local(2026, 11, 9, 18, 45, 1))
    assert len(calls) == 1
    assert calls[0].data["at"].startswith("2026-11-09T18:45")
    await move_to(hass, freezer, local(2026, 11, 9, 19, 1))
    assert len(calls) == 1


def wake_options(**rule: Any) -> dict[str, Any]:
    """Aufstehen 06:30 to 07:00 fades from 5 % to the 40 % of Morgen."""
    options = rule_options(**rule)
    options["rules"][0]["rows"]["aufstehen"] = {"react": "on", "brightness": 5, "fade": True}
    return normalize_options(options)


def last_on(lights: FakeLights, entity_id: str = BAD) -> dict[str, Any]:
    return next(
        c.data
        for c in reversed(lights.calls)
        if c.service == "turn_on" and entity_id in cv.ensure_list(c.data["entity_id"])
    )


async def test_a_wake_up_fade_runs_over_the_time_of_day_and_can_be_resumed(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory, lights: FakeLights
) -> None:
    freezer.move_to(local(2026, 11, 9, 6, 20))
    rhythm = await setup_rhythm(options=wake_options())
    await move_to(hass, freezer, local(2026, 11, 9, 6, 30, 1))
    data = last_on(lights)
    assert data["brightness_pct"] == 40
    assert data["color_temp_kelvin"] == 3000
    assert 1790 <= data["transition"] <= 1800
    starts = [c.data for c in lights.calls if c.service == "turn_on"]
    assert starts[0]["brightness_pct"] == 5 and starts[0]["transition"] == 0
    assert rhythm.rules.describe_fades()[0]["state"] == "running"
    assert not rhythm.rules.overridden()
    # Somebody turns it up by hand: the fade stops, the light keeps the value.
    await move_to(hass, freezer, local(2026, 11, 9, 6, 40))
    lights.by_hand(BAD, "on", brightness=255)
    await hass.async_block_till_done()
    assert rhythm.rules.describe_fades()[0]["state"] == "cancelled"
    assert rhythm.rules.overridden()
    # Resume: to where the fade would be by now, then on to the end.
    await move_to(hass, freezer, local(2026, 11, 9, 6, 45))
    await hass.services.async_call("cloudless_maestro", "resume_fade", {}, blocking=True)
    await hass.async_block_till_done()
    data = last_on(lights)
    assert data["transition"] == 2 and 21 <= data["brightness_pct"] <= 24
    await move_to(hass, freezer, local(2026, 11, 9, 6, 45, 3))
    data = last_on(lights)
    assert data["brightness_pct"] == 40 and 890 <= data["transition"] <= 900
    assert not rhythm.rules.overridden()
    # Morgen begins: the fade is over.
    await move_to(hass, freezer, local(2026, 11, 9, 7, 0, 1))
    assert rhythm.rules.describe_fades() == []


async def test_motion_does_not_end_a_fade_and_pinning_holds_it(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory, lights: FakeLights
) -> None:
    freezer.move_to(local(2026, 11, 9, 6, 20))
    rhythm = await setup_rhythm(options=wake_options())
    await move_to(hass, freezer, local(2026, 11, 9, 6, 30, 1))
    await motion(hass, True)
    await motion(hass, False)
    await move_to(hass, freezer, local(2026, 11, 9, 6, 36))
    assert hass.states.get(BAD).state == "on"
    # Holding Aufstehen holds the fade; when the hold ends, the fade runs on.
    await rhythm.async_pin("aufstehen", "duration", timedelta(minutes=5))
    await hass.async_block_till_done()
    assert rhythm.rules.describe_fades()[0]["state"] == "paused"
    assert last_on(lights)["transition"] == 1
    await move_to(hass, freezer, local(2026, 11, 9, 6, 41, 30))
    assert rhythm.rules.describe_fades()[0]["state"] == "running"
    data = last_on(lights)
    assert data["brightness_pct"] == 40 and 1000 <= data["transition"] <= 1110


async def test_a_fade_goes_on_after_a_restart(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory, lights: FakeLights
) -> None:
    freezer.move_to(local(2026, 11, 9, 6, 20))
    await setup_rhythm(options=wake_options(), entry_id="r1")
    await move_to(hass, freezer, local(2026, 11, 9, 6, 30, 1))
    await hass.config_entries.async_unload("r1")
    await hass.async_block_till_done()
    freezer.move_to(local(2026, 11, 9, 6, 45))
    lights.calls.clear()
    assert await hass.config_entries.async_setup("r1")
    await hass.async_block_till_done()
    data = last_on(lights)
    assert data["brightness_pct"] == 40 and 890 <= data["transition"] <= 900


async def test_long_fades_go_in_parts_and_plain_lights_in_steps(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory, lights: FakeLights
) -> None:
    attrs = dict(hass.states.get(REGAL).attributes)
    attrs["supported_features"] = 0
    hass.states.async_set(REGAL, "off", attrs)
    freezer.move_to(local(2026, 11, 9, 11, 50))
    options = rule_options(lights=[BAD, REGAL])
    options["rules"][0]["rows"]["mittag"] = {"react": "on", "brightness": 10, "fade": True, "fade_to": 80}
    await setup_rhythm(options=normalize_options(options))
    await move_to(hass, freezer, local(2026, 11, 9, 12, 0, 1))
    # Midday lasts seven hours, longer than one transition may take.
    data = last_on(lights, BAD)
    assert data["transition"] == 6000
    assert 25 <= data["brightness_pct"] <= 27
    plain = last_on(lights, REGAL)
    assert "transition" not in plain and plain["brightness_pct"] == 10
    await move_to(hass, freezer, local(2026, 11, 9, 12, 5))
    assert 10 <= last_on(lights, REGAL)["brightness_pct"] <= 11
    await move_to(hass, freezer, local(2026, 11, 9, 13, 40, 2))
    data = last_on(lights, BAD)
    assert 6000 - 5 <= data["transition"] <= 6000 and 42 <= data["brightness_pct"] <= 44


async def test_actions_before_a_begin_and_at_an_end(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory, lights: FakeLights
) -> None:
    climate = async_mock_service(hass, "climate", "set_temperature")
    cover = async_mock_service(hass, "cover", "set_cover_position")
    switch_off = async_mock_service(hass, "homeassistant", "turn_off")
    freezer.move_to(local(2026, 11, 9, 5, 0))
    options = rule_options(
        actions=[
            {"entity": "climate.bad", "tod": "aufstehen", "edge": "start", "offset": -60, "value": 22},
            {"entity": COVER, "tod": "abend", "edge": "end", "offset": 0, "value": 0},
            {"entity": "switch.heizdecke", "tod": "abend", "edge": "end", "offset": 10, "value": "off"},
        ]
    )
    rhythm = await setup_rhythm(options=options)
    await move_to(hass, freezer, local(2026, 11, 9, 5, 29))
    assert not climate
    await move_to(hass, freezer, local(2026, 11, 9, 5, 30, 1))
    assert climate[-1].data == {"entity_id": "climate.bad", "temperature": 22.0}
    await move_to(hass, freezer, local(2026, 11, 9, 5, 32))
    assert len(climate) == 1
    await move_to(hass, freezer, local(2026, 11, 9, 19, 0, 1))
    await move_to(hass, freezer, local(2026, 11, 9, 22, 30, 1))
    assert cover[-1].data == {"entity_id": COVER, "position": 0}
    assert not switch_off
    await move_to(hass, freezer, local(2026, 11, 9, 22, 40, 1))
    assert switch_off[-1].data == {"entity_id": "switch.heizdecke"}
    coming = {a["entity"]: a["next"] for a in rhythm.rules.describe_actions()}
    assert coming["climate.bad"].startswith("2026-11-10T05:30")


def test_devices_of_0_1_0b2_become_actions() -> None:
    options = sample_options(
        rules=[
            {
                "id": "wz",
                "name": "Wohnzimmer",
                "devices": [{"entity": COVER, "values": {"aufstehen": 100, "einschlafen": 0, "weg": 5}}],
            }
        ]
    )
    actions = options["rules"][0]["actions"]
    assert {(a["tod"], a["value"], a["edge"], a["offset"]) for a in actions} == {
        ("aufstehen", 100.0, "start", 0),
        ("einschlafen", 0.0, "start", 0),
    }
    assert "devices" not in options["rules"][0]
