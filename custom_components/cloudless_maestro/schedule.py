"""How a rhythm's plan turns into times: day windows, times of day and the base state.

Pure functions without Home Assistant, so the rules of the requirements can be tested exactly.

- A day runs from the start of its first time of day to its day end. Outside every day the base state applies.
- If the next day starts before a day ends, the next day wins and the earlier day ends there.
- A time of day whose computed start lies before the previous one, or at or after the day end, does not happen.
- Times are local wall-clock times. A time that does not exist moves to the next valid minute, a doubled time
  counts the first time.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from enum import Enum
from typing import Any

SUN_EVENTS = ("dawn", "sunrise", "noon", "sunset", "dusk")
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

MAX_DAY = timedelta(hours=24)
LOOKBACK_DAYS = 2
LOOKAHEAD_DAYS = 8

PIN_NEXT_CHANGE = "next_change"
PIN_DURATION = "duration"
PIN_TIME = "time"
PIN_NEXT_DAY = "next_day"
PIN_RESET = "reset"
PIN_MODES = (PIN_NEXT_CHANGE, PIN_DURATION, PIN_TIME, PIN_NEXT_DAY, PIN_RESET)

SOURCE_WEEK = "week"
SOURCE_CALENDAR = "calendar"
SOURCE_ADJUSTMENT = "adjustment"


class Missing(Enum):
    """A sun event that does not happen on a date, for example sunset in polar day."""

    EARLY = "early"
    LATE = "late"


type SunLookup = Callable[[str, date], datetime | Missing]


# -- time specs ----------------------------------------------------------------------------------------


def parse_clock(value: str) -> time:
    """Read HH:MM."""
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


@dataclass(frozen=True)
class TimeSpec:
    """A start time or day end: fixed or relative to the sun, optionally on the following day."""

    kind: str
    clock: time | None = None
    event: str | None = None
    offset: int = 0
    earliest: time | None = None
    latest: time | None = None
    next_day: bool = False

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TimeSpec:
        """Read a normalized spec, see model.TIME_SPEC."""
        if data["kind"] == "fixed":
            return cls("fixed", clock=parse_clock(data["time"]), next_day=bool(data.get("next_day")))
        return cls(
            "sun",
            event=data["event"],
            offset=int(data.get("offset", 0)),
            earliest=parse_clock(data["earliest"]) if data.get("earliest") else None,
            latest=parse_clock(data["latest"]) if data.get("latest") else None,
            next_day=bool(data.get("next_day")),
        )


def local_time(day: date, clock: time, tz: tzinfo) -> datetime:
    """Return a wall-clock time on a date. A time that does not exist moves to the next valid minute."""
    naive = datetime.combine(day, clock)
    for _ in range(24 * 60):
        aware = naive.replace(tzinfo=tz, fold=0)
        if aware.astimezone(UTC).astimezone(tz).replace(tzinfo=None) == naive:
            return aware
        naive += timedelta(minutes=1)
    return naive.replace(tzinfo=tz)


def resolve(spec: TimeSpec, day: date, tz: tzinfo, sun: SunLookup) -> datetime | None:
    """Return the moment of a spec on a date, or None if it does not happen that day."""
    on = day + timedelta(days=1) if spec.next_day else day
    if spec.kind == "fixed":
        assert spec.clock is not None
        return local_time(on, spec.clock, tz)
    assert spec.event is not None
    earliest = local_time(on, spec.earliest, tz) if spec.earliest else None
    latest = local_time(on, spec.latest, tz) if spec.latest else None
    found = sun(spec.event, on)
    if found is Missing.EARLY:
        return earliest
    if found is Missing.LATE:
        return latest
    assert isinstance(found, datetime)
    moment = (found + timedelta(minutes=spec.offset)).astimezone(tz)
    if earliest is not None and moment < earliest:
        moment = earliest
    if latest is not None and moment > latest:
        moment = latest
    return moment


# -- one day ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    """A time of day as it happens on one date."""

    key: str
    start: datetime


@dataclass(frozen=True)
class DayPlan:
    """What one date looks like on its own, before the neighboring days are considered."""

    day: date
    model: str | None
    source: str
    detail: str | None
    order: tuple[str, ...]
    entries: tuple[Entry, ...]
    end: datetime | None
    dropped: tuple[str, ...] = ()
    adjusted: bool = False

    @property
    def start(self) -> datetime | None:
        """Return when the day begins, or None if it has no window."""
        return self.entries[0].start if self.entries and self.end is not None else None


@dataclass(frozen=True)
class Choice:
    """Which model a date gets, and why."""

    model: str | None
    source: str
    detail: str | None = None


@dataclass
class Plan:
    """A rhythm's configuration together with its day adjustments and calendar results."""

    options: Mapping[str, Any]
    tz: tzinfo
    sun: SunLookup
    adjustments: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    calendar: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._models = {m["key"]: m for m in self.options.get("models", ())}
        self._cache: dict[date, DayPlan] = {}

    @property
    def base(self) -> str:
        """Return the key of the base state."""
        return self.options["base"]["key"]

    def model(self, key: str | None) -> Mapping[str, Any] | None:
        """Return a model by its key."""
        return self._models.get(key) if key else None

    def choice(self, day: date) -> Choice:
        """Return the model of a date: a day adjustment beats the calendar, the calendar beats the week."""
        adjustment = self.adjustments.get(day.isoformat()) or {}
        if adjustment.get("model") in self._models:
            return Choice(adjustment["model"], SOURCE_ADJUSTMENT)
        found = self.calendar.get(day.isoformat())
        if found and found.get("model") in self._models:
            return Choice(found["model"], SOURCE_CALENDAR, found.get("summary"))
        model = self.options.get("week", {}).get(WEEKDAYS[day.weekday()])
        return Choice(model if model in self._models else None, SOURCE_WEEK)

    def day(self, day: date) -> DayPlan:
        """Return a date's times of day and day end."""
        if day not in self._cache:
            self._cache[day] = self._compute_day(day)
        return self._cache[day]

    def _compute_day(self, day: date) -> DayPlan:
        choice = self.choice(day)
        model = self.model(choice.model)
        adjustment = self.adjustments.get(day.isoformat()) or {}
        if model is None:
            return DayPlan(day, None, choice.source, choice.detail, (), (), None, adjusted=bool(adjustment))
        times = adjustment.get("times") or {}
        order = tuple(e["tod"] for e in model["entries"])
        kept: list[Entry] = []
        dropped: list[str] = []
        for item in model["entries"]:
            spec = TimeSpec.from_dict(times.get(item["tod"]) or item["at"])
            moment = resolve(spec, day, self.tz, self.sun)
            if moment is None or (kept and moment < kept[-1].start):
                dropped.append(item["tod"])
                continue
            kept.append(Entry(item["tod"], moment))
        end = resolve(TimeSpec.from_dict(adjustment.get("end") or model["end"]), day, self.tz, self.sun)
        if kept and end is None:
            end = kept[0].start + MAX_DAY
        if end is not None:
            while kept and kept[-1].start >= end:
                dropped.append(kept.pop().key)
        if kept and end is not None:
            end = min(end, kept[0].start + MAX_DAY)
        dropped.sort(key=order.index)
        return DayPlan(
            day, choice.model, choice.source, choice.detail, order, tuple(kept), end, tuple(dropped), bool(adjustment)
        )


# -- many days ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Segment:
    """A stretch of time with one time of day, or the base state when day is None."""

    key: str
    start: datetime
    end: datetime
    day: date | None


@dataclass(frozen=True)
class Window:
    """A day as it really happens, cut short where the next day already begins."""

    day: date
    start: datetime
    end: datetime


@dataclass(frozen=True)
class Timeline:
    """Contiguous segments from start to end, and the day windows within."""

    start: datetime
    end: datetime
    segments: tuple[Segment, ...]
    windows: tuple[Window, ...]
    base: str

    def index_at(self, moment: datetime) -> int:
        """Return the index of the segment containing a moment."""
        for i, seg in enumerate(self.segments):
            if seg.start <= moment < seg.end:
                return i
        return len(self.segments) - 1 if moment >= self.end else 0

    def at(self, moment: datetime) -> Segment:
        """Return the segment containing a moment."""
        return self.segments[self.index_at(moment)]

    def since(self, moment: datetime) -> datetime:
        """Return when the key at a moment began, across boundaries that keep the key."""
        i = self.index_at(moment)
        key = self.segments[i].key
        while i > 0 and self.segments[i - 1].key == key:
            i -= 1
        return self.segments[i].start

    def change_after(self, moment: datetime) -> tuple[datetime, str] | None:
        """Return the next moment the key changes, with the new key."""
        i = self.index_at(moment)
        key = self.segments[i].key
        for seg in self.segments[i + 1 :]:
            if seg.key != key:
                return seg.start, seg.key
        return None

    def window_at(self, moment: datetime) -> Window | None:
        """Return the day window containing a moment."""
        return next((w for w in self.windows if w.start <= moment < w.end), None)

    def window_after(self, moment: datetime, after_day: date | None = None) -> Window | None:
        """Return the first window that begins after a moment, optionally only of a later date."""
        for w in self.windows:
            if w.start > moment and (after_day is None or w.day > after_day):
                return w
        return None

    def today(self, moment: datetime) -> date:
        """Return the date that counts as today: the running day, or the coming one in the base state."""
        running = self.window_at(moment)
        if running is not None:
            return running.day
        coming = self.window_after(moment)
        return coming.day if coming is not None else moment.astimezone(self.start.tzinfo).date()


def build_timeline(plan: Plan, start: datetime, end: datetime) -> Timeline:
    """Lay out all days that touch a range, with the base state in between."""
    tz = plan.tz
    first = start.astimezone(tz).date() - timedelta(days=LOOKBACK_DAYS)
    last = end.astimezone(tz).date() + timedelta(days=1)
    days = [plan.day(first + timedelta(days=n)) for n in range((last - first).days + 1)]
    starts = [d.start for d in days]
    windows: list[Window] = []
    segments: list[Segment] = []
    for i, day in enumerate(days):
        if day.start is None or day.end is None:
            continue
        cut = day.end
        for later in starts[i + 1 :]:
            if later is not None and later < cut:
                cut = later
        if cut <= day.start:
            continue
        windows.append(Window(day.day, day.start, cut))
        for n, entry in enumerate(day.entries):
            seg_end = min(day.entries[n + 1].start, cut) if n + 1 < len(day.entries) else cut
            if seg_end > entry.start:
                segments.append(Segment(entry.key, entry.start, seg_end, day.day))
    return Timeline(start, end, tuple(_fill(segments, start, end, plan.base)), tuple(windows), plan.base)


def _fill(segments: Sequence[Segment], start: datetime, end: datetime, base: str) -> list[Segment]:
    """Clip to the range and put the base state into every gap."""
    out: list[Segment] = []
    cursor = start
    for seg in sorted(segments, key=lambda s: s.start):
        if seg.end <= start or seg.start >= end:
            continue
        seg_start, seg_end = max(seg.start, start), min(seg.end, end)
        if seg_start > cursor:
            out.append(Segment(base, cursor, seg_start, None))
        out.append(Segment(seg.key, seg_start, seg_end, seg.day))
        cursor = seg_end
    if cursor < end:
        out.append(Segment(base, cursor, end, None))
    return out


def timeline_around(plan: Plan, moment: datetime) -> Timeline:
    """Return a timeline wide enough for everything a moment needs: since, until, today and tomorrow."""
    return build_timeline(plan, moment - timedelta(days=LOOKBACK_DAYS), moment + timedelta(days=LOOKAHEAD_DAYS))


# -- pins ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Pin:
    """A time of day set by hand, independent of the plan, until a chosen end."""

    key: str
    day: date
    mode: str
    set_at: datetime
    until: datetime | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Pin:
        """Read a stored pin."""
        until = data.get("until")
        return cls(
            data["key"],
            date.fromisoformat(data["day"]),
            data["mode"],
            datetime.fromisoformat(data["set_at"]),
            datetime.fromisoformat(until) if until else None,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return what is stored."""
        return {
            "key": self.key,
            "day": self.day.isoformat(),
            "mode": self.mode,
            "set_at": self.set_at.isoformat(),
            "until": self.until.isoformat() if self.until else None,
        }


def next_day_start(timeline: Timeline, pin_day: date, moment: datetime) -> datetime | None:
    """Return when the day after a pin's day begins: the latest end of a duration or a clock time."""
    window = timeline.window_after(moment, after_day=pin_day)
    return window.start if window else None


def pin_end(pin: Pin, timeline: Timeline, plan: Plan) -> datetime | None:
    """Return when a pin ends, or None if it lasts until it is reset."""
    if pin.mode == PIN_RESET:
        return None
    following = next_day_start(timeline, pin.day, pin.set_at)
    if pin.mode == PIN_NEXT_DAY:
        return following
    if pin.mode in (PIN_DURATION, PIN_TIME):
        assert pin.until is not None
        return min(pin.until, following) if following is not None else pin.until
    # Until the next change: the plan catches up with a later time of day, or the day ends.
    if pin.key == plan.base:
        window = timeline.window_after(pin.set_at)
        return window.start if window else None
    order = plan.day(pin.day).order
    rank = order.index(pin.key) if pin.key in order else -1
    started = False
    for seg in timeline.segments:
        if seg.end <= pin.set_at:
            continue
        if seg.day == pin.day:
            started = True
            if seg.start > pin.set_at and seg.key in order and order.index(seg.key) > rank:
                return seg.start
        elif started or (seg.day is not None and seg.day > pin.day):
            return max(seg.start, pin.set_at)
    return None


@dataclass(frozen=True)
class State:
    """What applies at a moment, after pins."""

    key: str
    since: datetime
    until: datetime | None
    next_key: str | None
    today: date
    pinned: bool
    pin_end: datetime | None
    planned: str


def overlay(timeline: Timeline, pin: Pin, end: datetime | None) -> Timeline:
    """Return the timeline with a pin laid over the plan."""
    stop = min(end, timeline.end) if end is not None else timeline.end
    if stop <= pin.set_at:
        return timeline
    before = [Segment(s.key, s.start, min(s.end, pin.set_at), s.day) for s in timeline.segments if s.start < pin.set_at]
    after = [Segment(s.key, max(s.start, stop), s.end, s.day) for s in timeline.segments if s.end > stop]
    pinned = Segment(pin.key, max(pin.set_at, timeline.start), stop, pin.day)
    return Timeline(timeline.start, timeline.end, (*before, pinned, *after), timeline.windows, timeline.base)


def state_at(plan: Plan, moment: datetime, pin: Pin | None = None) -> tuple[State, Timeline]:
    """Return what applies at a moment, and the timeline with the pin laid over it."""
    timeline = timeline_around(plan, moment)
    planned = timeline.at(moment).key
    end = pin_end(pin, timeline, plan) if pin is not None else None
    active = pin is not None and pin.set_at <= moment and (end is None or moment < end)
    effective = overlay(timeline, pin, end) if active and pin is not None else timeline
    key = effective.at(moment).key
    change = effective.change_after(moment)
    return (
        State(
            key=key,
            since=effective.since(moment),
            until=change[0] if change else None,
            next_key=change[1] if change else None,
            today=timeline.today(moment),
            pinned=active,
            pin_end=end if active else None,
            planned=planned,
        ),
        effective,
    )


def segments_between(timeline: Timeline, start: datetime, end: datetime) -> Iterable[Segment]:
    """Return the merged segments that touch a range, for drawing."""
    merged: list[Segment] = []
    for seg in timeline.segments:
        if seg.end <= start or seg.start >= end:
            continue
        if merged and merged[-1].key == seg.key and merged[-1].end == seg.start and merged[-1].day == seg.day:
            last = merged.pop()
            seg = Segment(seg.key, last.start, seg.end, seg.day)
        merged.append(seg)
    return merged
