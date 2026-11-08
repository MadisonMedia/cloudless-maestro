"""Triggers and conditions in the automation editor, and the setup dialog."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from homeassistant import config_entries
from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_get_device_automation_capabilities,
    async_get_device_automations,
    async_mock_service,
)

from custom_components.cloudless_maestro.const import DOMAIN

from .conftest import local


async def _automation(hass: HomeAssistant, trigger: dict, condition: list | None = None) -> list[ServiceCall]:
    calls = async_mock_service(hass, "test", "automation")
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": trigger,
                "condition": condition or [],
                "action": {"service": "test.automation", "data": {"to": "{{ trigger.event.data.to }}"}},
            }
        },
    )
    await hass.async_block_till_done()
    return calls


async def test_triggers_are_offered(hass: HomeAssistant, setup_rhythm) -> None:
    rhythm = await setup_rhythm()
    triggers = await async_get_device_automations(hass, DeviceAutomationType.TRIGGER, rhythm.device_id)
    assert {t["type"] for t in triggers if t["domain"] == DOMAIN} == {"begins", "ends", "changes"}
    begins = next(t for t in triggers if t.get("type") == "begins")
    capabilities = await async_get_device_automation_capabilities(hass, DeviceAutomationType.TRIGGER, begins)
    field = capabilities["extra_fields"][0]
    assert field["name"] == "time_of_day"
    assert ("mittag", "Mittag") in [tuple(o) for o in field["options"]]


async def test_a_trigger_fires_when_its_time_of_day_begins(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(local(2026, 11, 9, 11, 59))
    rhythm = await setup_rhythm()
    calls = await _automation(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": rhythm.device_id,
            "type": "begins",
            "time_of_day": "mittag",
        },
    )
    for moment in (local(2026, 11, 9, 12), local(2026, 11, 9, 19)):
        freezer.move_to(moment)
        async_fire_time_changed(hass, moment)
        await hass.async_block_till_done()
    assert [c.data["to"] for c in calls] == ["mittag"]


async def test_a_trigger_fires_when_its_time_of_day_ends(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(local(2026, 11, 9, 18, 59))
    rhythm = await setup_rhythm()
    calls = await _automation(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": rhythm.device_id,
            "type": "ends",
            "time_of_day": "mittag",
        },
    )
    freezer.move_to(local(2026, 11, 9, 19))
    async_fire_time_changed(hass, local(2026, 11, 9, 19))
    await hass.async_block_till_done()
    assert [c.data["to"] for c in calls] == ["abend"]


async def test_a_condition_checks_the_time_of_day(
    hass: HomeAssistant, setup_rhythm, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(local(2026, 11, 9, 10))
    rhythm = await setup_rhythm()
    conditions = await async_get_device_automations(hass, DeviceAutomationType.CONDITION, rhythm.device_id)
    assert {c["type"] for c in conditions if c["domain"] == DOMAIN} == {"is", "is_overridden"}
    calls = await _automation(
        hass,
        {"platform": "event", "event_type": "test_event"},
        [
            {
                "condition": "device",
                "domain": DOMAIN,
                "device_id": rhythm.device_id,
                "type": "is",
                "times_of_day": ["morgen", "mittag"],
            }
        ],
    )
    hass.bus.async_fire("test_event", {"to": "x"})
    await hass.async_block_till_done()
    assert len(calls) == 1
    await rhythm.async_pin("abend", "reset")
    hass.bus.async_fire("test_event", {"to": "x"})
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_setup_dialog_creates_a_rhythm_from_a_template(hass: HomeAssistant, setup_rhythm) -> None:
    hass.config.language = "de"
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Kinderzimmer", "template": "day"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    options = result["result"].options
    assert [t["key"] for t in options["times_of_day"]] == [
        "aufstehen",
        "morgen",
        "mittag",
        "nachmittag",
        "abend",
        "einschlafen",
    ]
    assert options["base"]["key"] == "nacht"
    assert options["week"]["sat"] == "wochenende"
    await hass.async_block_till_done()
    assert hass.states.get("sensor.kinderzimmer_tageszeit") is not None


async def test_setup_dialog_in_english_with_an_empty_template(hass: HomeAssistant, setup_rhythm) -> None:
    hass.config.language = "en"
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Terrarium", "template": "empty"}
    )
    options = result["result"].options
    assert [t["name"] for t in options["times_of_day"]] == ["Day"]
    assert options["base"]["name"] == "Night"
