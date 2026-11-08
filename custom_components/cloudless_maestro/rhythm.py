"""One rhythm at runtime: what applies now, when it changes, and what has been set by hand."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import copy
from datetime import date, datetime, time, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.event import async_track_point_in_utc_time, async_track_time_interval
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .const import (
    ADJUSTMENT_KEEP_DAYS,
    CALENDAR_DAYS_AHEAD,
    CALENDAR_DAYS_BACK,
    CALENDAR_REFRESH_MINUTES,
    DOMAIN,
    EVENT_CHANGED,
    LOG_SIZE,
    REASON_ADJUSTMENT,
    REASON_CALENDAR,
    REASON_CONFIG,
    REASON_PIN,
    REASON_PLAN,
    REASON_RESTART,
    REASON_RESUME,
    STORAGE_VERSION,
)
from .model import normalize_adjustment, normalize_options
from .schedule import (
    PIN_DURATION,
    PIN_MODES,
    PIN_TIME,
    DayPlan,
    Pin,
    Plan,
    State,
    Timeline,
    local_time,
    next_day_start,
    segments_between,
    state_at,
)
from .sun import make_sun

_LOGGER = logging.getLogger(__name__)

TICK = timedelta(minutes=1)


def calendar_dates(links: list[Mapping[str, Any]], events: Mapping[str, Mapping[str, Any]], tz) -> dict[str, Any]:
    """Map dates to models from calendar events. The first matching link in the list wins.

    All-day events count for each of their dates, events with a time for the date they start on.
    """
    found: dict[str, Any] = {}
    for index, link in enumerate(links):
        cached = events.get(link["calendar"]) or {}
        needle = link.get("match", "").casefold()
        for event in cached.get("events", ()):
            summary = str(event.get("summary") or "")
            if needle and needle not in summary.casefold():
                continue
            for day in _event_dates(event, tz):
                found.setdefault(day.isoformat(), {"model": link["model"], "summary": summary, "link": index})
    return found


def _event_dates(event: Mapping[str, Any], tz) -> list[date]:
    start, end = str(event.get("start", "")), str(event.get("end", ""))
    try:
        if len(start) == 10:
            first = date.fromisoformat(start)
            last = date.fromisoformat(end) if len(end) == 10 else first + timedelta(days=1)
            return [first + timedelta(days=n) for n in range(max(1, (last - first).days))]
        moment = datetime.fromisoformat(start)
    except ValueError:
        return []
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=tz)
    return [moment.astimezone(tz).date()]


class Rhythm:
    """Keeps a rhythm's state up to date and fires an event at every change."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, device_id: str | None = None) -> None:
        self.hass = hass
        self.entry = entry
        self.device_id = device_id
        self.options: dict[str, Any] = normalize_options(entry.options)
        self.store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.data: dict[str, Any] = {"pin": None, "adjustments": {}, "calendar": {}, "last": None, "log": []}
        self.plan: Plan = self._make_plan()
        self.state: State | None = None
        self.timeline: Timeline | None = None
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._timer: CALLBACK_TYPE | None = None
        self._calendar_errors: dict[str, str] = {}

    # -- lifecycle ------------------------------------------------------------------------------------

    async def async_start(self) -> None:
        """Load what was set by hand, work out the current state and start the timers."""
        stored = await self.store.async_load()
        if isinstance(stored, dict):
            for key in self.data:
                if key in stored:
                    self.data[key] = stored[key]
        self._prune()
        self.plan = self._make_plan()
        self._evaluate(REASON_RESTART)
        self._unsubs.append(async_track_time_interval(self.hass, self._tick, TICK))
        self._unsubs.append(
            async_track_time_interval(self.hass, self._calendar_tick, timedelta(minutes=CALENDAR_REFRESH_MINUTES))
        )
        self._unsubs.append(self.hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, self._core_config_updated))
        self._unsubs.append(async_at_started(self.hass, self._started))

    async def async_stop(self) -> None:
        """Stop the timers and store everything."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._timer is not None:
            self._timer()
            self._timer = None
        await self.store.async_save(self.data)

    @callback
    def _started(self, _hass: HomeAssistant) -> None:
        if self.options["calendar_links"]:
            self.hass.async_create_task(self.async_refresh_calendars(), eager_start=True)

    @callback
    def _tick(self, _now: datetime) -> None:
        self._evaluate(REASON_PLAN)

    @callback
    def _calendar_tick(self, _now: datetime) -> None:
        if self.options["calendar_links"]:
            self.hass.async_create_task(self.async_refresh_calendars(), eager_start=True)

    @callback
    def _core_config_updated(self, _event: Event) -> None:
        self.plan = self._make_plan()
        self._evaluate(REASON_CONFIG)

    @callback
    def options_changed(self) -> None:
        """Use new settings at once, also for the running day."""
        old_links = self.options.get("calendar_links")
        self.options = normalize_options(self.entry.options)
        self._prune()
        self.plan = self._make_plan()
        self._evaluate(REASON_CONFIG)
        if self.options["calendar_links"] != old_links:
            self.hass.async_create_task(self.async_refresh_calendars(), eager_start=True)

    # -- listeners ------------------------------------------------------------------------------------

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Call back after every evaluation."""
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    # -- the plan -------------------------------------------------------------------------------------

    @property
    def tz(self):
        """Return the time zone of Home Assistant."""
        return dt_util.get_time_zone(self.hass.config.time_zone) or dt_util.get_default_time_zone()

    @property
    def title(self) -> str:
        """Return the rhythm's name."""
        return self.entry.title

    def make_sun(self, options: Mapping[str, Any] | None = None):
        """Return sun times for the rhythm's location, or Home Assistant's."""
        location = (options or self.options).get("location") or {}
        return make_sun(
            float(location.get("latitude", self.hass.config.latitude)),
            float(location.get("longitude", self.hass.config.longitude)),
            self.tz,
        )

    def _make_plan(self) -> Plan:
        dates = calendar_dates(self.options["calendar_links"], self.data["calendar"], self.tz)
        return Plan(self.options, self.tz, self.make_sun(), self.data["adjustments"], dates)

    def _prune(self) -> None:
        """Forget old day adjustments and anything that refers to deleted keys."""
        today = dt_util.now(self.tz).date()
        tods = {t["key"] for t in self.options["times_of_day"]}
        models = {m["key"] for m in self.options["models"]}
        kept: dict[str, Any] = {}
        for day, adjustment in self.data["adjustments"].items():
            try:
                if date.fromisoformat(day) < today - timedelta(days=ADJUSTMENT_KEEP_DAYS):
                    continue
            except ValueError:
                continue
            cleaned = dict(adjustment)
            if cleaned.get("model") not in models:
                cleaned["model"] = None
            cleaned["times"] = {k: v for k, v in (cleaned.get("times") or {}).items() if k in tods}
            if cleaned["model"] or cleaned["times"] or cleaned.get("end"):
                kept[day] = cleaned
        self.data["adjustments"] = kept
        pin = self.data.get("pin")
        if pin and pin.get("key") not in tods | {self.options["base"]["key"]}:
            self.data["pin"] = None

    # -- evaluation -----------------------------------------------------------------------------------

    @property
    def pin(self) -> Pin | None:
        """Return the stored pin."""
        raw = self.data.get("pin")
        try:
            return Pin.from_dict(raw) if raw else None
        except (KeyError, ValueError):
            return None

    @callback
    def _evaluate(self, reason: str) -> None:
        now = dt_util.now(self.tz)
        pin = self.pin
        state, timeline = state_at(self.plan, now, pin)
        if pin is not None and not state.pinned and pin.set_at <= now:
            # The pin has ended. The plan applies again.
            self.data["pin"] = None
            self.log({"kind": "pin_ended"})
            if reason == REASON_PIN:
                reason = REASON_PLAN
        previous = self.state.key if self.state is not None else (self.data.get("last") or {}).get("key")
        first = self.state is None
        self.state = state
        self.timeline = timeline
        if previous != state.key and (previous is not None or not first):
            self._fire(previous, state.key, REASON_RESTART if first else reason)
        if previous != state.key or not self.data.get("last"):
            self.data["last"] = {"key": state.key, "at": now.isoformat()}
            self._save()
        self._schedule(state)
        for listener in list(self._listeners):
            listener()

    def _schedule(self, state: State) -> None:
        if self._timer is not None:
            self._timer()
            self._timer = None
        moments = [m for m in (state.until, state.pin_end) if m is not None]
        if not moments:
            return
        self._timer = async_track_point_in_utc_time(self.hass, self._due, min(moments))

    @callback
    def _due(self, _now: datetime) -> None:
        self._timer = None
        self._evaluate(REASON_PLAN)

    def _fire(self, old: str | None, new: str, reason: str) -> None:
        self.hass.bus.async_fire(
            EVENT_CHANGED,
            {
                "entry_id": self.entry.entry_id,
                "device_id": self.device_id,
                "rhythm": self.title,
                "from": old,
                "to": new,
                "reason": reason,
            },
        )
        self.log({"kind": "change", "from": old, "to": new, "reason": reason})

    def log(self, item: dict[str, Any]) -> None:
        """Remember a change or decision for the diagnostics."""
        self.data["log"] = [*self.data["log"], {"at": dt_util.now(self.tz).isoformat(), **item}][-LOG_SIZE:]
        self._save()

    def _save(self) -> None:
        self.store.async_delay_save(lambda: self.data, 1)

    # -- names ----------------------------------------------------------------------------------------

    def time_of_day(self, key: str | None) -> dict[str, Any] | None:
        """Return a time of day or the base state by its key."""
        if key is None:
            return None
        if key == self.options["base"]["key"]:
            return self.options["base"]
        return next((t for t in self.options["times_of_day"] if t["key"] == key), None)

    def name_of(self, key: str | None) -> str | None:
        """Return the name of a time of day."""
        item = self.time_of_day(key)
        return item["name"] if item else key

    def choosable(self) -> list[str]:
        """Return what can be pinned now: the times of day in today's model and the base state."""
        assert self.state is not None
        return [*self.plan.day(self.state.today).order, self.options["base"]["key"]]

    # -- actions --------------------------------------------------------------------------------------

    async def async_pin(
        self, key: str, mode: str, duration: timedelta | None = None, until: time | None = None
    ) -> None:
        """Set a time of day by hand until a chosen end."""
        assert self.state is not None
        if mode not in PIN_MODES:
            raise ServiceValidationError(f"Unknown end: {mode}")
        if key not in self.choosable():
            names = ", ".join(self.choosable())
            raise ServiceValidationError(f"{key} is not part of today's day model. Possible: {names}")
        now = dt_util.now(self.tz)
        end: datetime | None = None
        if mode == PIN_DURATION:
            if duration is None or duration <= timedelta(0):
                raise ServiceValidationError("A pin for a duration needs a duration")
            end = now + duration
        elif mode == PIN_TIME:
            if until is None:
                raise ServiceValidationError("A pin until a time needs a time")
            end = local_time(now.date(), until, self.tz)
            if end <= now:
                end = local_time(now.date() + timedelta(days=1), until, self.tz)
        pin = Pin(key, self.state.today, mode, now, end)
        self.data["pin"] = pin.as_dict()
        self.log({"kind": "pin", "to": key, "mode": mode, "until": end.isoformat() if end else None})
        self._evaluate(REASON_PIN)

    async def async_resume(self) -> None:
        """Return to the plan. Day adjustments stay."""
        if self.data.get("pin") is None:
            return
        self.data["pin"] = None
        self.log({"kind": "resume"})
        self._evaluate(REASON_RESUME)

    def resolve_day(self, day: date | None) -> date:
        """Return the date an action means, today if none is given."""
        if day is not None:
            return day
        assert self.state is not None
        return self.state.today

    async def async_adjust_day(
        self,
        day: date | None,
        model: str | None = None,
        times: Mapping[str, Any] | None = None,
        end: Mapping[str, Any] | None = None,
        clear_times: list[str] | None = None,
        clear_end: bool = False,
        clear_model: bool = False,
    ) -> None:
        """Change a single date. Only what deviates is stored; the rest follows the model."""
        day = self.resolve_day(day)
        current = copy.deepcopy(self.data["adjustments"].get(day.isoformat()) or {})
        merged = {
            "model": model if model is not None else current.get("model"),
            "times": {**(current.get("times") or {}), **(times or {})},
            "end": end if end is not None else current.get("end"),
        }
        for key in clear_times or ():
            merged["times"].pop(key, None)
        if clear_end:
            merged["end"] = None
        if clear_model:
            merged["model"] = None
        try:
            adjustment = normalize_adjustment(merged, self.options)
        except vol.Invalid as err:
            raise ServiceValidationError(str(err)) from err
        if adjustment is not None:
            chosen = adjustment["model"] or self.plan.choice(day).model
            order = next((m for m in self.options["models"] if m["key"] == chosen), {"entries": []})
            in_model = {e["tod"] for e in order["entries"]}
            for key in adjustment["times"]:
                if key not in in_model:
                    raise ServiceValidationError(f"{key} is not part of the day model on {day.isoformat()}")
            self.data["adjustments"] = {**self.data["adjustments"], day.isoformat(): adjustment}
        else:
            self.data["adjustments"] = {k: v for k, v in self.data["adjustments"].items() if k != day.isoformat()}
        self.log({"kind": "adjust", "day": day.isoformat(), "adjustment": adjustment})
        self.plan = self._make_plan()
        self._evaluate(REASON_ADJUSTMENT)

    async def async_clear_day(self, day: date | None) -> None:
        """Remove a day adjustment."""
        day = self.resolve_day(day)
        if day.isoformat() not in self.data["adjustments"]:
            return
        self.data["adjustments"] = {k: v for k, v in self.data["adjustments"].items() if k != day.isoformat()}
        self.log({"kind": "adjust", "day": day.isoformat(), "adjustment": None})
        self.plan = self._make_plan()
        self._evaluate(REASON_ADJUSTMENT)

    async def async_refresh_calendars(self) -> None:
        """Read the events of all linked calendars for the coming weeks."""
        links = self.options["calendar_links"]
        today = dt_util.now(self.tz).date()
        start = local_time(today - timedelta(days=CALENDAR_DAYS_BACK), time(0, 0), self.tz)
        end = local_time(today + timedelta(days=CALENDAR_DAYS_AHEAD), time(0, 0), self.tz)
        cached = dict(self.data["calendar"])
        wanted = {link["calendar"] for link in links}
        for calendar in sorted(wanted):
            try:
                response = await self.hass.services.async_call(
                    "calendar",
                    "get_events",
                    {"entity_id": calendar, "start_date_time": start, "end_date_time": end},
                    blocking=True,
                    return_response=True,
                )
                events = (response or {}).get(calendar, {}).get("events", [])
                cached[calendar] = {
                    "fetched": dt_util.now(self.tz).isoformat(),
                    "events": [
                        {"start": str(e.get("start")), "end": str(e.get("end")), "summary": e.get("summary")}
                        for e in events
                    ],
                }
                if calendar in self._calendar_errors:
                    del self._calendar_errors[calendar]
            except Exception as err:
                message = str(err) or type(err).__name__
                if self._calendar_errors.get(calendar) != message:
                    self._calendar_errors[calendar] = message
                    self.log({"kind": "calendar_error", "calendar": calendar, "error": message})
                    _LOGGER.warning("Could not read calendar %s: %s", calendar, message)
        self.data["calendar"] = {k: v for k, v in cached.items() if k in wanted}
        self._save()
        self.plan = self._make_plan()
        self._evaluate(REASON_CALENDAR)

    # -- describing -----------------------------------------------------------------------------------

    def describe_day(self, plan: DayPlan) -> dict[str, Any]:
        """Return a date as the card and the page show it."""
        assert self.timeline is not None
        window = next((w for w in self.timeline.windows if w.day == plan.day), None)
        return {
            "day": plan.day.isoformat(),
            "model": plan.model,
            "source": plan.source,
            "detail": plan.detail,
            "adjusted": plan.adjusted,
            "adjustment": self.data["adjustments"].get(plan.day.isoformat()),
            "order": list(plan.order),
            "entries": [{"key": e.key, "start": e.start.isoformat()} for e in plan.entries],
            "end": plan.end.isoformat() if plan.end else None,
            "dropped": list(plan.dropped),
            "window": {"start": window.start.isoformat(), "end": window.end.isoformat()} if window else None,
        }

    def snapshot(self) -> dict[str, Any]:
        """Return everything a card needs to draw the rhythm."""
        assert self.state is not None and self.timeline is not None
        state = self.state
        now = dt_util.now(self.tz)
        today = self.plan.day(state.today)
        tomorrow = self.plan.day(state.today + timedelta(days=1))
        starts = [now - timedelta(hours=3)]
        ends = [now + timedelta(hours=3)]
        for plan in (today, tomorrow):
            if plan.start is not None and plan.end is not None:
                starts.append(plan.start - timedelta(hours=1))
                ends.append(plan.end + timedelta(hours=1))
        span_start, span_end = min(starts), min(max(ends), self.timeline.end)
        following = next_day_start(self.timeline, state.today, now)
        pin = self.data.get("pin")
        return {
            "entry_id": self.entry.entry_id,
            "title": self.title,
            "device_id": self.device_id,
            "now": now.isoformat(),
            "base": self.options["base"],
            "times_of_day": self.options["times_of_day"],
            "models": [{"key": m["key"], "name": m["name"]} for m in self.options["models"]],
            "state": {
                "key": state.key,
                "since": state.since.isoformat(),
                "until": state.until.isoformat() if state.until else None,
                "next_key": state.next_key,
                "today": state.today.isoformat(),
                "pinned": state.pinned,
                "pin_end": state.pin_end.isoformat() if state.pin_end else None,
                "planned": state.planned,
                "pin": pin if state.pinned else None,
            },
            "choosable": self.choosable(),
            "next_day_start": following.isoformat() if following else None,
            "days": [self.describe_day(today), self.describe_day(tomorrow)],
            "segments": [
                {
                    "key": s.key,
                    "start": s.start.isoformat(),
                    "end": s.end.isoformat(),
                    "day": s.day.isoformat() if s.day else None,
                }
                for s in segments_between(self.timeline, span_start, span_end)
            ],
        }

    def diagnostics(self) -> dict[str, Any]:
        """Return the log and the calendar status."""
        return {
            "log": list(reversed(self.data["log"])),
            "calendars": {
                cal: {
                    "fetched": item.get("fetched"),
                    "events": len(item.get("events", ())),
                    "error": self._calendar_errors.get(cal),
                }
                for cal, item in self.data["calendar"].items()
            }
            | {
                cal: {"fetched": None, "events": 0, "error": err}
                for cal, err in self._calendar_errors.items()
                if cal not in self.data["calendar"]
            },
        }
