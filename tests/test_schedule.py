"""The rules of the time calculation, one by one, without Home Assistant."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from custom_components.cloudless_maestro.model import normalize_options
from custom_components.cloudless_maestro.schedule import (
    PIN_DURATION,
    PIN_NEXT_CHANGE,
    PIN_NEXT_DAY,
    PIN_RESET,
    PIN_TIME,
    Missing,
    Pin,
    Plan,
    build_timeline,
    local_time,
    parse_clock,
    state_at,
    timeline_around,
)
from custom_components.cloudless_maestro.sun import make_sun

TZ = ZoneInfo("Europe/Berlin")
MONDAY = date(2026, 11, 9)


def at(day: date, clock: str, plus: int = 0) -> datetime:
    return local_time(day + timedelta(days=plus), parse_clock(clock), TZ)


def fixed(clock: str, next_day: bool = False) -> dict[str, Any]:
    return {"kind": "fixed", "time": clock, "next_day": next_day}


def sun(event: str, offset: int = 0, earliest: str | None = None, latest: str | None = None) -> dict[str, Any]:
    return {"kind": "sun", "event": event, "offset": offset, "earliest": earliest, "latest": latest}


class FakeSun:
    """Sun events at chosen local clock times, the same every day unless set per date."""

    def __init__(self, **events: str | Missing) -> None:
        self.events: dict[str, str | Missing] = {"sunset": "17:00", "sunrise": "07:30", **events}
        self.by_day: dict[tuple[str, date], str | Missing] = {}

    def __call__(self, event: str, day: date) -> datetime | Missing:
        value = self.by_day.get((event, day), self.events.get(event, "12:00"))
        if isinstance(value, Missing):
            return value
        return at(day, value).astimezone(UTC)


TODS = ["aufstehen", "morgen", "mittag", "abend", "einschlafen", "fruehschicht"]


def options(models: list[dict[str, Any]], week: dict[str, str] | None = None) -> dict[str, Any]:
    return normalize_options(
        {
            "base": {"key": "nacht", "name": "Nacht"},
            "times_of_day": [{"key": k, "name": k.title()} for k in TODS],
            "models": models,
            "week": week or dict.fromkeys(("mon", "tue", "wed", "thu", "fri", "sat", "sun"), models[0]["key"]),
        }
    )


WERKTAG = {
    "key": "werktag",
    "name": "Werktag",
    "entries": [
        {"tod": "aufstehen", "at": fixed("06:30")},
        {"tod": "morgen", "at": fixed("07:00")},
        {"tod": "mittag", "at": fixed("12:00")},
        {"tod": "abend", "at": fixed("19:00")},
        {"tod": "einschlafen", "at": fixed("22:30")},
    ],
    "end": fixed("23:30"),
}


def make_plan(models: list[dict[str, Any]] | None = None, week=None, sun_=None, **kwargs: Any) -> Plan:
    return Plan(options(models or [WERKTAG], week), TZ, sun_ or FakeSun(), **kwargs)


def key_at(plan: Plan, moment: datetime, pin: Pin | None = None) -> str:
    return state_at(plan, moment, pin)[0].key


# -- one day and the gaps between days ----------------------------------------------------------------


def test_a_time_of_day_lasts_until_the_next_one_starts() -> None:
    state, _ = state_at(make_plan(), at(MONDAY, "10:00"))
    assert state.key == "morgen"
    assert state.since == at(MONDAY, "07:00")
    assert state.until == at(MONDAY, "12:00")
    assert state.next_key == "mittag"
    assert state.today == MONDAY


def test_the_base_state_fills_the_gap_between_two_days() -> None:
    state, _ = state_at(make_plan(), at(MONDAY, "23:45"))
    assert state.key == "nacht"
    assert state.since == at(MONDAY, "23:30")
    assert state.until == at(MONDAY, "06:30", plus=1)
    assert state.next_key == "aufstehen"
    # In the base state, today is the coming day.
    assert state.today == MONDAY + timedelta(days=1)


def test_today_before_the_day_begins_is_that_day() -> None:
    assert state_at(make_plan(), at(MONDAY, "05:00"))[0].today == MONDAY


def test_times_after_midnight_belong_to_the_day_they_start_from() -> None:
    party = {
        "key": "party",
        "name": "Party",
        "entries": [{"tod": "abend", "at": fixed("19:00")}, {"tod": "einschlafen", "at": fixed("02:00", True)}],
        "end": fixed("06:00", True),
    }
    plan = make_plan([party])
    assert key_at(plan, at(MONDAY, "01:00", plus=1)) == "abend"
    assert key_at(plan, at(MONDAY, "03:00", plus=1)) == "einschlafen"
    assert key_at(plan, at(MONDAY, "06:30", plus=1)) == "nacht"
    assert state_at(plan, at(MONDAY, "01:00", plus=1))[0].today == MONDAY


def test_the_next_day_wins_when_two_days_overlap() -> None:
    friday = date(2026, 11, 13)
    party = {
        "key": "party",
        "name": "Party",
        "entries": [{"tod": "abend", "at": fixed("19:00")}, {"tod": "einschlafen", "at": fixed("02:00", True)}],
        "end": fixed("06:00", True),
    }
    early = {
        "key": "frueh",
        "name": "Frühschicht",
        "entries": [{"tod": "fruehschicht", "at": fixed("03:00")}, {"tod": "morgen", "at": fixed("05:00")}],
        "end": fixed("21:00"),
    }
    week = {"mon": "frueh", "tue": "frueh", "wed": "frueh", "thu": "frueh", "fri": "party", "sat": "frueh"}
    week["sun"] = "frueh"
    plan = make_plan([party, early], week)
    timeline = timeline_around(plan, at(friday, "20:00"))
    window = next(w for w in timeline.windows if w.day == friday)
    assert window.end == at(friday, "03:00", plus=1)
    assert key_at(plan, at(friday, "02:59", plus=1)) == "einschlafen"
    assert key_at(plan, at(friday, "03:00", plus=1)) == "fruehschicht"
    assert state_at(plan, at(friday, "02:30", plus=1))[0].until == at(friday, "03:00", plus=1)


def test_a_day_without_times_of_day_stays_in_the_base_state() -> None:
    away = {"key": "weg", "name": "Weg", "entries": [], "end": fixed("23:00")}
    week = dict.fromkeys(("mon", "tue", "wed", "thu", "fri", "sat", "sun"), "werktag") | {"tue": "weg"}
    plan = make_plan([WERKTAG, away], week)
    state, _ = state_at(plan, at(MONDAY, "23:45"))
    assert state.key == "nacht"
    assert state.until == at(MONDAY, "06:30", plus=2)


def test_a_day_is_at_most_24_hours_long() -> None:
    long = dict(WERKTAG, end=fixed("08:00", True))
    timeline = timeline_around(make_plan([long]), at(MONDAY, "12:00"))
    window = next(w for w in timeline.windows if w.day == MONDAY)
    # The next day starts at 06:30, which is also exactly 24 hours after the start.
    assert window.end == at(MONDAY, "06:30", plus=1)
    assert make_plan([long]).day(MONDAY).end == at(MONDAY, "06:30", plus=1)


def test_a_time_of_day_after_the_day_end_does_not_happen() -> None:
    short = dict(WERKTAG, end=fixed("22:00"))
    day = make_plan([short]).day(MONDAY)
    assert [e.key for e in day.entries] == ["aufstehen", "morgen", "mittag", "abend"]
    assert day.dropped == ("einschlafen",)


def test_the_same_time_of_day_on_both_sides_of_a_boundary_is_no_change() -> None:
    late = {
        "key": "spaet",
        "name": "Spät",
        "entries": [{"tod": "einschlafen", "at": fixed("21:00")}],
        "end": fixed("05:00", True),
    }
    early = {
        "key": "frueh",
        "name": "Früh",
        "entries": [{"tod": "einschlafen", "at": fixed("04:00")}],
        "end": fixed("06:00"),
    }
    week = {"mon": "spaet", "tue": "frueh"} | dict.fromkeys(("wed", "thu", "fri", "sat", "sun"), "frueh")
    state, _ = state_at(make_plan([late, early], week), at(MONDAY, "22:00"))
    assert state.key == "einschlafen"
    assert state.until == at(MONDAY, "06:00", plus=1)
    assert state.next_key == "nacht"


# -- sun ----------------------------------------------------------------------------------------------


def test_sun_times_respect_earliest_and_latest() -> None:
    model = dict(
        WERKTAG,
        entries=[
            {"tod": "morgen", "at": fixed("07:00")},
            {"tod": "abend", "at": sun("sunset", -30, earliest="18:00", latest="21:00")},
        ],
    )
    fake = FakeSun()
    fake.by_day[("sunset", MONDAY)] = "17:00"
    fake.by_day[("sunset", MONDAY + timedelta(days=1))] = "22:00"
    fake.by_day[("sunset", MONDAY + timedelta(days=2))] = "19:40"
    plan = make_plan([model], sun_=fake)
    assert plan.day(MONDAY).entries[1].start == at(MONDAY, "18:00")
    assert plan.day(MONDAY + timedelta(days=1)).entries[1].start == at(MONDAY, "21:00", plus=1)
    assert plan.day(MONDAY + timedelta(days=2)).entries[1].start == at(MONDAY, "19:10", plus=2)


def test_a_time_of_day_before_the_previous_one_does_not_happen() -> None:
    model = dict(
        WERKTAG,
        entries=[
            {"tod": "morgen", "at": fixed("07:00")},
            {"tod": "abend", "at": sun("sunset")},
            {"tod": "einschlafen", "at": fixed("21:00")},
        ],
    )
    fake = FakeSun(sunset="21:30")
    day = make_plan([model], sun_=fake).day(MONDAY)
    assert [e.key for e in day.entries] == ["morgen", "abend"]
    assert day.dropped == ("einschlafen",)


def test_a_missing_sun_event_uses_the_bound() -> None:
    model = dict(
        WERKTAG,
        entries=[
            {"tod": "aufstehen", "at": sun("sunrise", earliest="06:00", latest="09:00")},
            {"tod": "abend", "at": sun("sunset", latest="21:00")},
            {"tod": "einschlafen", "at": sun("dusk")},
        ],
    )
    # Polar day: sunrise lies behind, sunset never comes.
    fake = FakeSun(sunrise=Missing.EARLY, sunset=Missing.LATE, dusk=Missing.LATE)
    day = make_plan([model], sun_=fake).day(MONDAY)
    assert [(e.key, e.start) for e in day.entries] == [
        ("aufstehen", at(MONDAY, "06:00")),
        ("abend", at(MONDAY, "21:00")),
    ]
    # Without a bound the time of day does not happen.
    assert day.dropped == ("einschlafen",)


def test_real_sun_times_for_berlin() -> None:
    lookup = make_sun(52.52, 13.405, TZ)
    sunset = lookup("sunset", date(2026, 6, 21))
    assert isinstance(sunset, datetime)
    assert at(date(2026, 6, 21), "21:25") < sunset < at(date(2026, 6, 21), "21:40")
    assert isinstance(lookup("sunrise", date(2026, 12, 21)), datetime)


def test_real_sun_in_polar_regions() -> None:
    tromso = make_sun(69.65, 18.96, ZoneInfo("Europe/Oslo"))
    assert tromso("sunset", date(2026, 6, 21)) is Missing.LATE
    assert tromso("sunrise", date(2026, 6, 21)) is Missing.EARLY
    assert tromso("sunrise", date(2026, 12, 21)) is Missing.LATE
    assert tromso("sunset", date(2026, 12, 21)) is Missing.EARLY


# -- clock changes ------------------------------------------------------------------------------------


def test_a_time_that_does_not_exist_moves_to_the_next_valid_minute() -> None:
    spring = date(2026, 3, 29)
    moment = local_time(spring, parse_clock("02:30"), TZ)
    assert moment.astimezone(UTC) == datetime(2026, 3, 29, 1, 0, tzinfo=UTC)
    assert moment.strftime("%H:%M") == "03:00"


def test_a_doubled_time_counts_the_first_time() -> None:
    autumn = date(2026, 10, 25)
    moment = local_time(autumn, parse_clock("02:30"), TZ)
    assert moment.astimezone(UTC) == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)


def test_days_follow_local_time_across_a_clock_change() -> None:
    sunday = date(2026, 10, 25)
    plan = make_plan()
    assert plan.day(sunday).entries[0].start.astimezone(UTC) == datetime(2026, 10, 25, 5, 30, tzinfo=UTC)
    assert plan.day(sunday - timedelta(days=1)).entries[0].start.astimezone(UTC) == datetime(
        2026, 10, 24, 4, 30, tzinfo=UTC
    )


# -- day adjustments and calendar ---------------------------------------------------------------------


def test_a_day_adjustment_changes_only_what_it_names() -> None:
    adjustments = {MONDAY.isoformat(): {"times": {"einschlafen": fixed("23:30")}, "end": fixed("00:30", True)}}
    plan = make_plan(adjustments=adjustments)
    day = plan.day(MONDAY)
    assert day.adjusted
    assert dict((e.key, e.start) for e in day.entries)["einschlafen"] == at(MONDAY, "23:30")
    assert day.end == at(MONDAY, "00:30", plus=1)
    assert dict((e.key, e.start) for e in day.entries)["morgen"] == at(MONDAY, "07:00")
    # Other days keep the model.
    assert plan.day(MONDAY + timedelta(days=1)).end == at(MONDAY, "23:30", plus=1)


def test_a_model_change_reaches_a_day_with_an_adjustment() -> None:
    adjustments = {MONDAY.isoformat(): {"times": {"einschlafen": fixed("23:30")}, "end": fixed("00:30", True)}}
    changed = dict(WERKTAG, entries=[dict(e) for e in WERKTAG["entries"]])
    changed["entries"][1] = {"tod": "morgen", "at": fixed("07:15")}
    day = make_plan([changed], adjustments=adjustments).day(MONDAY)
    assert dict((e.key, e.start) for e in day.entries)["morgen"] == at(MONDAY, "07:15")


def test_order_of_model_sources() -> None:
    weekend = dict(WERKTAG, key="wochenende", name="Wochenende", entries=[{"tod": "morgen", "at": fixed("09:00")}])
    party = dict(WERKTAG, key="party", name="Party", entries=[{"tod": "abend", "at": fixed("18:00")}])
    calendar = {MONDAY.isoformat(): {"model": "wochenende", "summary": "Feiertag"}}
    plan = make_plan([WERKTAG, weekend, party], calendar=calendar)
    choice = plan.choice(MONDAY)
    assert (choice.model, choice.source, choice.detail) == ("wochenende", "calendar", "Feiertag")
    plan = make_plan([WERKTAG, weekend, party], calendar=calendar, adjustments={MONDAY.isoformat(): {"model": "party"}})
    assert (plan.choice(MONDAY).model, plan.choice(MONDAY).source) == ("party", "adjustment")
    # A deleted model in an adjustment falls back to the plan.
    plan = make_plan([WERKTAG], adjustments={MONDAY.isoformat(): {"model": "gone"}})
    assert plan.choice(MONDAY).model == "werktag"


# -- pins ---------------------------------------------------------------------------------------------


def pin(key: str, day: date, mode: str, set_at: datetime, until: datetime | None = None) -> Pin:
    return Pin(key, day, mode, set_at, until)


def test_pin_a_later_time_of_day_until_the_plan_catches_up() -> None:
    plan = make_plan()
    p = pin("einschlafen", MONDAY, PIN_NEXT_CHANGE, at(MONDAY, "18:00"))
    state, _ = state_at(plan, at(MONDAY, "18:00"), p)
    assert state.key == "einschlafen"
    assert state.pinned
    # Abend and Einschlafen do not lie after the chosen time of day, so it lasts until the day ends.
    assert state.pin_end == at(MONDAY, "23:30")
    assert state.until == at(MONDAY, "23:30")
    assert state.next_key == "nacht"
    assert key_at(plan, at(MONDAY, "19:30"), p) == "einschlafen"


def test_pin_a_time_of_day_until_a_later_one_begins() -> None:
    p = pin("aufstehen", MONDAY, PIN_NEXT_CHANGE, at(MONDAY, "05:00"))
    state, _ = state_at(make_plan(), at(MONDAY, "05:00"), p)
    assert state.key == "aufstehen"
    assert state.today == MONDAY
    # The planned start of Aufstehen at 06:30 does not end it, Morgen at 07:00 does.
    assert state.pin_end == at(MONDAY, "07:00")
    assert state.since == at(MONDAY, "05:00")


def test_pin_an_earlier_time_of_day() -> None:
    p = pin("abend", MONDAY, PIN_NEXT_CHANGE, at(MONDAY, "22:45"))
    state, _ = state_at(make_plan(), at(MONDAY, "22:45"), p)
    assert state.key == "abend"
    assert state.pin_end == at(MONDAY, "23:30")


def test_pin_the_base_state_until_the_next_day() -> None:
    p = pin("nacht", MONDAY, PIN_NEXT_CHANGE, at(MONDAY, "21:00"))
    state, _ = state_at(make_plan(), at(MONDAY, "21:00"), p)
    assert state.key == "nacht"
    assert state.pin_end == at(MONDAY, "06:30", plus=1)
    assert state.next_key == "aufstehen"


def test_a_duration_ends_when_the_next_day_begins_at_the_latest() -> None:
    p = pin("abend", MONDAY, PIN_DURATION, at(MONDAY, "22:00"), at(MONDAY, "22:00") + timedelta(hours=12))
    state, _ = state_at(make_plan(), at(MONDAY, "22:00"), p)
    assert state.pin_end == at(MONDAY, "06:30", plus=1)
    assert key_at(make_plan(), at(MONDAY, "06:30", plus=1), p) == "aufstehen"


def test_pin_until_a_clock_time() -> None:
    p = pin("abend", MONDAY, PIN_TIME, at(MONDAY, "22:00"), at(MONDAY, "01:00", plus=1))
    plan = make_plan()
    assert state_at(plan, at(MONDAY, "22:00"), p)[0].pin_end == at(MONDAY, "01:00", plus=1)
    assert key_at(plan, at(MONDAY, "00:59", plus=1), p) == "abend"
    assert key_at(plan, at(MONDAY, "01:00", plus=1), p) == "nacht"


def test_pin_until_the_next_day() -> None:
    p = pin("abend", MONDAY, PIN_NEXT_DAY, at(MONDAY, "20:00"))
    state, _ = state_at(make_plan(), at(MONDAY, "20:00"), p)
    assert state.pin_end == at(MONDAY, "06:30", plus=1)
    assert state.next_key == "aufstehen"


def test_pin_until_reset_has_no_end() -> None:
    p = pin("abend", MONDAY, PIN_RESET, at(MONDAY, "20:00"))
    plan = make_plan()
    state, _ = state_at(plan, at(MONDAY, "20:00"), p)
    assert state.pin_end is None
    assert state.until is None
    assert key_at(plan, at(MONDAY, "08:00", plus=1), p) == "abend"


def test_holding_the_current_time_of_day_keeps_its_start() -> None:
    p = pin("abend", MONDAY, PIN_DURATION, at(MONDAY, "20:00"), at(MONDAY, "23:00"))
    state, _ = state_at(make_plan(), at(MONDAY, "22:45"), p)
    assert state.key == "abend"
    assert state.since == at(MONDAY, "19:00")
    assert state.until == at(MONDAY, "23:00")
    assert state.next_key == "einschlafen"
    assert state.planned == "einschlafen"


@pytest.mark.parametrize("hour", range(24))
def test_the_timeline_covers_every_moment_without_gaps(hour: int) -> None:
    plan = make_plan()
    moment = at(MONDAY, f"{hour:02d}:17")
    timeline = build_timeline(plan, moment - timedelta(days=1), moment + timedelta(days=2))
    for a, b in zip(timeline.segments, timeline.segments[1:], strict=False):
        assert a.end == b.start
        assert a.start < a.end
    assert timeline.segments[0].start == timeline.start
    assert timeline.segments[-1].end == timeline.end
