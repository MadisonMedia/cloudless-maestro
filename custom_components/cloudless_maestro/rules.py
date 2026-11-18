"""Rules: what a rhythm's lights and devices do in each time of day.

A rule has lights, triggers (motion, buttons, switching on by hand) and one row of values per time of day.
The engine turns lights on and off, remembers what people set by hand, tells its own commands from
changes made elsewhere, and gives devices their values when a time of day begins.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_CALL_SERVICE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Context, Event, State, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .model import (
    BEGIN_FOLLOW,
    BEGIN_FOLLOW_FREE,
    BEGIN_OFF,
    EDGE_END,
    EDGE_START,
    EXTERNAL_ON_KEEP,
    MANUAL_AFTER_NEVER,
    MANUAL_AFTER_SAME,
    REACT_NONE,
    REACT_ON,
)

if TYPE_CHECKING:
    from .rhythm import Rhythm

_LOGGER = logging.getLogger(__name__)

SOURCE = DOMAIN
CRESCENDO_DOMAIN = "cloudless_crescendo"
BRIGHTNESS_TOLERANCE = 3  # percent
KELVIN_TOLERANCE = 100
RGB_TOLERANCE = 24
EXPECT_GRACE = timedelta(seconds=5)
CONTEXT_KEEP = timedelta(seconds=90)
PREWARN_TRANSITION = 1
QUICK_TRANSITION = 1
RESUME_TRANSITION = 2
# Zigbee and Matter limit one transition to about 1 h 49 min; longer fades go in parts.
MAX_CHUNK = timedelta(seconds=6000)
LONG_TRANSITION = 300  # seconds; from here on a report must also be near where the fade is by now
ACTION_GRACE = timedelta(seconds=60)  # an action this late still counts as on time
ACTION_KEEP_DAYS = 4
FADE_RUNNING = "running"
FADE_PAUSED = "paused"
FADE_CANCELLED = "cancelled"
TRANSITION_FEATURE = 32  # LightEntityFeature.TRANSITION

# How Crescendo names what happened last on an object (crescendo_api 1).
CRESCENDO_SWITCH_ON = "switch_on"


# -- reading lights -----------------------------------------------------------------------------------


def is_crescendo(state: State | None) -> bool:
    """Return whether a light is a Crescendo object with the interface Maestro uses."""
    if state is None:
        return False
    attrs = state.attributes
    return bool(attrs.get("crescendo")) and int(attrs.get("crescendo_api") or 0) >= 1


def is_dimmable(state: State | None) -> bool:
    """Return whether a light can do more than on and off."""
    if state is None:
        return False
    modes = state.attributes.get("supported_color_modes") or ()
    return any(m != "onoff" for m in modes) or is_crescendo(state)


def can_transition(state: State | None) -> bool:
    """Return whether a light fades by itself."""
    if state is None:
        return False
    return is_crescendo(state) or bool(int(state.attributes.get("supported_features") or 0) & TRANSITION_FEATURE)


def color_modes(state: State | None) -> set[str]:
    return set((state.attributes.get("supported_color_modes") or ()) if state is not None else ())


def values_of(state: State | None) -> dict[str, Any]:
    """Return what a light shows: brightness in percent, white tone or color."""
    if state is None or state.state != STATE_ON:
        return {"on": False}
    attrs = state.attributes
    if is_crescendo(state):
        position = attrs.get("position")
        brightness = float(position) if position is not None else _pct(attrs.get("brightness"))
        return {"on": True, "brightness": brightness, "kelvin": None, "rgb": None}
    rgb = attrs.get("rgb_color")
    return {
        "on": True,
        "brightness": _pct(attrs.get("brightness")) if attrs.get("brightness") is not None else 100.0,
        "kelvin": attrs.get("color_temp_kelvin") if attrs.get("color_mode") == "color_temp" else None,
        "rgb": list(rgb) if rgb and attrs.get("color_mode") not in ("color_temp", "onoff", "brightness") else None,
    }


def _pct(brightness: Any) -> float:
    try:
        return round(float(brightness) * 100 / 255, 1)
    except (TypeError, ValueError):
        return 0.0


def same_values(a: Mapping[str, Any] | None, b: Mapping[str, Any] | None) -> bool:
    """Return whether two sets of light values are the same within what lights round."""
    if not a or not b:
        return False
    if bool(a.get("on")) != bool(b.get("on")):
        return False
    if not a.get("on"):
        return True
    if abs(float(a.get("brightness") or 0) - float(b.get("brightness") or 0)) > BRIGHTNESS_TOLERANCE:
        return False
    ka, kb = a.get("kelvin"), b.get("kelvin")
    if ka is not None and kb is not None and abs(float(ka) - float(kb)) > KELVIN_TOLERANCE:
        return False
    ra, rb = a.get("rgb"), b.get("rgb")
    return not (ra and rb and max(abs(int(x) - int(y)) for x, y in zip(ra, rb, strict=False)) > RGB_TOLERANCE)


def _between(value: float, start: float, end: float) -> bool:
    lo, hi = sorted((start, end))
    return lo - BRIGHTNESS_TOLERANCE <= value <= hi + BRIGHTNESS_TOLERANCE


# -- bookkeeping --------------------------------------------------------------------------------------


@dataclass
class Expectation:
    """What a light should report after one of Maestro's commands."""

    target: dict[str, Any]
    start: dict[str, Any]
    until: datetime
    transition: float = 0
    contexts: set[str] = field(default_factory=set)
    at: datetime | None = None

    def reached(self, values: Mapping[str, Any]) -> bool:
        return same_values(self.target, values)

    def on_the_way(self, values: Mapping[str, Any], moment: datetime | None = None) -> bool:
        """A brightness between start and target while a transition runs."""
        if self.transition <= 0 or not (values.get("on") and self.target.get("on")):
            return False
        begin = float(self.start.get("brightness") or 0) if self.start.get("on") else 0.0
        end = float(self.target.get("brightness") or 0)
        value = float(values.get("brightness") or 0)
        if not _between(value, begin, end):
            return False
        if self.transition < LONG_TRANSITION or self.at is None or moment is None:
            return True
        # In a long fade a value far from where the fade is by now was set by hand.
        share = min(1.0, max(0.0, (moment - self.at).total_seconds() / self.transition))
        expected = begin + (end - begin) * share
        return abs(value - expected) <= max(10.0, abs(end - begin) * 0.25)


@dataclass
class Fade:
    """A light running from one brightness to another over a whole time of day."""

    rule: str
    light: str
    tod: str
    start: datetime
    end: datetime
    begin: float
    target: float
    kelvin_from: int | None = None
    kelvin_to: int | None = None
    state: str = FADE_RUNNING
    held: float | None = None

    def share(self, moment: datetime) -> float:
        total = (self.end - self.start).total_seconds()
        if total <= 0:
            return 1.0
        return min(1.0, max(0.0, (moment - self.start).total_seconds() / total))

    def value_at(self, moment: datetime) -> float:
        return round(self.begin + (self.target - self.begin) * self.share(moment), 1)

    def kelvin_at(self, moment: datetime) -> int | None:
        if self.kelvin_from is None or self.kelvin_to is None:
            return self.kelvin_to or self.kelvin_from
        return round(self.kelvin_from + (self.kelvin_to - self.kelvin_from) * self.share(moment))

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "light": self.light,
            "tod": self.tod,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "begin": self.begin,
            "target": self.target,
            "kelvin_from": self.kelvin_from,
            "kelvin_to": self.kelvin_to,
            "state": self.state,
            "held": self.held,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Fade:
        return cls(
            str(data["rule"]),
            str(data["light"]),
            str(data["tod"]),
            datetime.fromisoformat(data["start"]),
            datetime.fromisoformat(data["end"]),
            float(data["begin"]),
            float(data["target"]),
            data.get("kelvin_from"),
            data.get("kelvin_to"),
            str(data.get("state") or FADE_RUNNING),
            data.get("held"),
        )


@dataclass
class LightTrack:
    """What Maestro knows about one light, across rules. Stored over a restart."""

    entity_id: str
    overridden: bool = False
    memory: dict[str, Any] | None = None  # {"values": {...}, "at": iso}
    owner: str | None = None  # the rule that switched the light on last
    last_on: dict[str, Any] | None = None  # the values it showed while it was on last
    expectations: list[Expectation] = field(default_factory=list)
    contexts: dict[str, datetime] = field(default_factory=dict)
    prewarn: dict[str, Any] | None = None  # values before the pre-warning dimmed the light

    def as_dict(self) -> dict[str, Any]:
        return {"overridden": self.overridden, "memory": self.memory, "owner": self.owner, "last_on": self.last_on}

    @classmethod
    def from_dict(cls, entity_id: str, data: Mapping[str, Any]) -> LightTrack:
        return cls(
            entity_id,
            overridden=bool(data.get("overridden")),
            memory=data.get("memory") if isinstance(data.get("memory"), dict) else None,
            owner=data.get("owner"),
            last_on=data.get("last_on") if isinstance(data.get("last_on"), dict) else None,
        )

    def note_context(self, context_id: str, now: datetime) -> None:
        self.contexts[context_id] = now
        for key in [k for k, at in self.contexts.items() if now - at > CONTEXT_KEEP]:
            del self.contexts[key]

    def is_own(self, event_context_id: str | None, values: Mapping[str, Any], now: datetime) -> bool:
        """Return whether a reported state is the answer to one of Maestro's commands."""
        self.expectations = [e for e in self.expectations if now <= e.until]
        if event_context_id and event_context_id in self.contexts:
            self._settle(values)
            return True
        for index, expectation in enumerate(self.expectations):
            if expectation.reached(values):
                # The command is done; older expectations are history.
                del self.expectations[: index + 1]
                return True
        return any(e.on_the_way(values, now) for e in self.expectations)

    def _settle(self, values: Mapping[str, Any]) -> None:
        for index, expectation in enumerate(self.expectations):
            if expectation.reached(values):
                del self.expectations[: index + 1]
                return


@dataclass
class RuleRun:
    """The live state of one rule."""

    rule: dict[str, Any]
    pending: dict[str, datetime] = field(default_factory=dict)  # light -> when it goes off
    timer: CALLBACK_TYPE | None = None
    lock_until: datetime | None = None
    warn_timer: CALLBACK_TYPE | None = None
    warned: set[str] = field(default_factory=set)

    @property
    def id(self) -> str:
        return self.rule["id"]

    @property
    def name(self) -> str:
        return self.rule["name"]


class RuleEngine:
    """Runs all rules of one rhythm."""

    def __init__(self, rhythm: Rhythm) -> None:
        self.rhythm = rhythm
        self.hass = rhythm.hass
        self.tracks: dict[str, LightTrack] = {}
        self.runs: list[RuleRun] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._service_calls: dict[str, bool] = {}  # context id of light.turn_on -> carried a value
        self.fades: dict[str, Fade] = {}  # by light
        self._fade_timers: dict[str, CALLBACK_TYPE] = {}
        self._fade_sent: set[str] = set()  # lights whose fade was sent since Home Assistant started
        self._action_timers: dict[str, CALLBACK_TYPE] = {}
        self._action_planned: dict[str, datetime] = {}

    # -- lifecycle ------------------------------------------------------------------------------------

    async def async_start(self) -> None:
        """Restore what was known and listen to the lights and sensors."""
        for entity_id, data in (self.rhythm.data.get("lights") or {}).items():
            if isinstance(data, Mapping):
                self.tracks[entity_id] = LightTrack.from_dict(entity_id, data)
        for item in self.rhythm.data.get("fades") or ():
            try:
                fade = Fade.from_dict(item)
            except (KeyError, TypeError, ValueError):
                continue
            self.fades[fade.light] = fade
        self._build()
        # Lights that were about to go off when Home Assistant stopped go off at that moment, or soon.
        now = self.now
        for run in self.runs:
            for light, iso in (self.rhythm.data.get("pending") or {}).get(run.id, {}).items():
                try:
                    due = datetime.fromisoformat(iso)
                except ValueError:
                    continue
                run.pending[light] = max(due, now + timedelta(minutes=1))
            self._reschedule(run)

    async def async_stop(self) -> None:
        """Stop listening and cancel timers. Running fades are stored and continue after a restart."""
        self._teardown()
        for light in list(self._fade_timers):
            self._cancel_fade_timer(light)

    @callback
    def options_changed(self) -> None:
        """Use new rules. Timers of rules that still exist keep running."""
        old = {run.id: run for run in self.runs}
        self._teardown(keep_runs=True)
        self._build(old)

    def _teardown(self, keep_runs: bool = False) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        for key in list(self._action_timers):
            self._action_timers.pop(key)()
        self._action_planned.clear()
        if not keep_runs:
            for run in self.runs:
                self._cancel_timers(run)
            self.runs = []

    def _build(self, old: Mapping[str, RuleRun] | None = None) -> None:
        runs = []
        for rule in self.rhythm.options.get("rules", ()):
            previous = (old or {}).get(rule["id"])
            if previous is not None:
                previous.rule = rule
                runs.append(previous)
            else:
                runs.append(RuleRun(rule))
        for run in (old or {}).values():
            if run not in runs:
                self._cancel_timers(run)
        self.runs = runs
        lights, motion, buttons, lux = set(), set(), set(), set()
        for run in self.runs:
            lights.update(run.rule["lights"])
            motion.update(run.rule["motion"])
            buttons.update(b["entity"] for b in run.rule["buttons"])
            if run.rule.get("lux"):
                lux.add(run.rule["lux"]["sensor"])
        for entity_id in lights:
            self.tracks.setdefault(entity_id, LightTrack(entity_id))
        for entity_id in [e for e in self.tracks if e not in lights]:
            del self.tracks[entity_id]
        if lights:
            self._unsubs.append(async_track_state_change_event(self.hass, sorted(lights), self._light_changed))
            self._unsubs.append(self.hass.bus.async_listen(EVENT_CALL_SERVICE, self._service_called))
        if motion:
            self._unsubs.append(async_track_state_change_event(self.hass, sorted(motion), self._motion_changed))
        if buttons:
            self._unsubs.append(async_track_state_change_event(self.hass, sorted(buttons), self._button_changed))
        self._unsubs.append(self.rhythm.async_add_listener(self._rhythm_updated))
        for run in self.runs:
            self._reschedule(run)
        if self.rhythm.state is not None:
            self._schedule_actions()

    def _cancel_timers(self, run: RuleRun) -> None:
        if run.timer is not None:
            run.timer()
            run.timer = None
        if run.warn_timer is not None:
            run.warn_timer()
            run.warn_timer = None
        run.pending.clear()
        run.warned.clear()

    # -- helpers --------------------------------------------------------------------------------------

    @property
    def now(self) -> datetime:
        return dt_util.now(self.rhythm.tz)

    @property
    def defaults(self) -> Mapping[str, Any]:
        return self.rhythm.options["defaults"]

    def _state(self, entity_id: str) -> State | None:
        return self.hass.states.get(entity_id)

    def _is_on(self, entity_id: str) -> bool:
        state = self._state(entity_id)
        return state is not None and state.state == STATE_ON

    def _row(self, run: RuleRun, key: str | None = None) -> dict[str, Any]:
        """Return the rule's row for a time of day. A missing row does nothing."""
        key = key or (self.rhythm.state.key if self.rhythm.state else None)
        return run.rule["rows"].get(key or "", {"react": REACT_NONE, "begin": "keep"})

    def _after(self, run: RuleRun, row: Mapping[str, Any]) -> int:
        return int(row.get("after") if row.get("after") is not None else self.defaults["after"])

    def _transition(self, run: RuleRun, row: Mapping[str, Any], state: State | None) -> int | None:
        if row.get("transition") is not None:
            return int(row["transition"])
        if is_crescendo(state):
            return None  # the object's own speed
        return int(self.defaults["transition"])

    def _memory_minutes(self, row: Mapping[str, Any]) -> int:
        return int(row.get("memory") if row.get("memory") is not None else self.defaults["memory"])

    def _warn_on(self, run: RuleRun) -> bool:
        warn = run.rule.get("warn")
        return bool(self.defaults["warn"] if warn is None else warn)

    def _lock_seconds(self, run: RuleRun) -> int:
        lock = run.rule.get("lock")
        return int(self.defaults["lock"] if lock is None else lock)

    def _dark_enough(self, run: RuleRun, row: Mapping[str, Any]) -> bool:
        lux = run.rule.get("lux")
        if not lux:
            return True
        state = self._state(lux["sensor"])
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return True
        try:
            value = float(state.state)
        except ValueError:
            return True
        below = row.get("lux_below") if row.get("lux_below") is not None else lux["below"]
        return value < float(below)

    def _motion_present(self, run: RuleRun) -> bool:
        return any(self._is_on(e) for e in run.rule["motion"])

    def _runs_with(self, entity_id: str) -> list[RuleRun]:
        return [run for run in self.runs if run.rule["active"] and entity_id in run.rule["lights"]]

    def _save(self) -> None:
        self.rhythm.data["lights"] = {e: t.as_dict() for e, t in self.tracks.items()}
        self.rhythm.data["pending"] = {
            run.id: {light: due.isoformat() for light, due in run.pending.items()} for run in self.runs if run.pending
        }
        self.rhythm.data["fades"] = [fade.as_dict() for fade in self.fades.values()]
        self.rhythm._save()

    def _log(self, run: RuleRun | None, what: str, **detail: Any) -> None:
        self.rhythm.log(
            {"kind": "rule", "rule": run.id if run else None, "name": run.name if run else None, "what": what, **detail}
        )

    # -- commands to lights ---------------------------------------------------------------------------

    async def _call(self, domain: str, service: str, data: dict[str, Any], context: Context | None = None) -> bool:
        """Call an action and keep running when it fails, for example because Crescendo is not installed."""
        try:
            await self.hass.services.async_call(domain, service, data, blocking=True, context=context)
        except Exception as err:
            self._log(None, "command_error", entity=data.get(ATTR_ENTITY_ID), error=str(err) or type(err).__name__)
            _LOGGER.warning("Maestro could not call %s.%s for %s: %s", domain, service, data.get(ATTR_ENTITY_ID), err)
            return False
        return True

    async def _send_on(
        self,
        run: RuleRun | None,
        entity_id: str,
        values: Mapping[str, Any],
        transition: int | None,
        start: Mapping[str, Any] | None = None,
    ) -> None:
        """Switch a light on to values. The answer is Maestro's own, so it is noted before the call."""
        state = self._state(entity_id)
        track = self.tracks.setdefault(entity_id, LightTrack(entity_id))
        context = Context()
        now = self.now
        target = {"on": True, "brightness": float(values.get("brightness") or 100), "kelvin": None, "rgb": None}
        if is_crescendo(state):
            domain, service = CRESCENDO_DOMAIN, "fade_to"
            data: dict[str, Any] = {ATTR_ENTITY_ID: entity_id, "position": target["brightness"], "source": SOURCE}
            if transition is not None:
                data["duration"] = {"seconds": transition}
        else:
            domain, service = "light", SERVICE_TURN_ON
            data = {ATTR_ENTITY_ID: entity_id, "brightness_pct": round(target["brightness"])}
            if transition is not None:
                data["transition"] = transition
            color = values.get("color")
            if isinstance(color, Mapping):
                if color.get("kelvin") is not None:
                    data["color_temp_kelvin"] = int(color["kelvin"])
                    target["kelvin"] = int(color["kelvin"])
                elif color.get("rgb") is not None:
                    data["rgb_color"] = [int(c) for c in color["rgb"]]
                    target["rgb"] = [int(c) for c in color["rgb"]]
            elif values.get("kelvin") is not None:
                data["color_temp_kelvin"] = int(values["kelvin"])
                target["kelvin"] = int(values["kelvin"])
            elif values.get("rgb"):
                data["rgb_color"] = [int(c) for c in values["rgb"]]
                target["rgb"] = [int(c) for c in values["rgb"]]
            modes = color_modes(state)
            if "color_temp" not in modes and "color_temp_kelvin" in data:
                del data["color_temp_kelvin"]
                target["kelvin"] = None
            if not modes & {"hs", "rgb", "rgbw", "rgbww", "xy"} and "rgb_color" in data:
                del data["rgb_color"]
                target["rgb"] = None
            if not is_dimmable(state):
                data = {ATTR_ENTITY_ID: entity_id}
        track.note_context(context.id, now)
        track.expectations.append(
            Expectation(
                target,
                dict(start) if start is not None else values_of(state),
                now + timedelta(seconds=transition or 0) + EXPECT_GRACE,
                float(transition or 0),
                {context.id},
                now,
            )
        )
        if run is not None:
            track.owner = run.id
        await self._call(domain, service, data, context)

    async def _send_off(self, entity_id: str, transition: int | None) -> None:
        state = self._state(entity_id)
        track = self.tracks.setdefault(entity_id, LightTrack(entity_id))
        context = Context()
        now = self.now
        if is_crescendo(state):
            domain, service = CRESCENDO_DOMAIN, "fade_to"
            data: dict[str, Any] = {ATTR_ENTITY_ID: entity_id, "position": 0, "source": SOURCE}
            if transition is not None:
                data["duration"] = {"seconds": transition}
        else:
            domain, service = "light", SERVICE_TURN_OFF
            data = {ATTR_ENTITY_ID: entity_id}
            if transition is not None and is_dimmable(state):
                data["transition"] = transition
        track.note_context(context.id, now)
        track.expectations.append(
            Expectation(
                {"on": False},
                values_of(state),
                now + timedelta(seconds=transition or 0) + EXPECT_GRACE,
                float(transition or 0),
                {context.id},
                now,
            )
        )
        track.owner = None
        track.prewarn = None
        await self._call(domain, service, data, context)

    async def _set_on_position(self, entity_id: str, position: float | None) -> None:
        """Tell a Crescendo object what it switches on to, so it never flashes with an old value."""
        data: dict[str, Any] = {ATTR_ENTITY_ID: entity_id}
        if position is not None:
            data["position"] = position
        await self._call(CRESCENDO_DOMAIN, "set_on_position", data)

    def _values_for(
        self, track: LightTrack, row: Mapping[str, Any], use_memory: bool = True
    ) -> tuple[dict[str, Any], bool]:
        """Return the values a light gets when it goes on: its memory if fresh enough, else the row."""
        if use_memory and track.memory and track.memory.get("values", {}).get("on"):
            try:
                at = datetime.fromisoformat(track.memory["at"])
            except (KeyError, ValueError):
                at = None
            minutes = self._memory_minutes(row)
            if at is not None and minutes > 0 and self.now - at <= timedelta(minutes=minutes):
                return dict(track.memory["values"]), True
        values = {"brightness": row.get("brightness") or 100, "color": row.get("color")}
        return values, False

    async def apply_row(
        self, run: RuleRun, key: str | None = None, lights: Iterable[str] | None = None, use_memory: bool = True
    ) -> list[str]:
        """Switch the rule's lights on with the row of a time of day. Returns the lights it switched."""
        row = self._row(run, key)
        current = self.rhythm.state.key if self.rhythm.state else None
        done = []
        for entity_id in lights if lights is not None else run.rule["lights"]:
            state = self._state(entity_id)
            if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                continue
            if row.get("fade") and (key is None or key == current):
                # In a time of day with a fade, the light joins the fade where it is by now.
                fade = self.fades.get(entity_id)
                if fade is not None and fade.tod == current and fade.state == FADE_CANCELLED:
                    await self._resume_fade(fade)
                elif fade is None or fade.tod != current:
                    await self._start_fade(run, entity_id, current)
                done.append(entity_id)
                continue
            track = self.tracks.setdefault(entity_id, LightTrack(entity_id))
            values, from_memory = self._values_for(track, row, use_memory)
            transition = self._transition(run, row, state)
            if row.get("transition") is None and transition is not None and state.state != STATE_ON:
                # The default transition is for lights that follow a new time of day. Switching on is quick.
                transition = QUICK_TRANSITION
            await self._send_on(run, entity_id, values, transition)
            if from_memory:
                self._log(run, "memory", light=entity_id, values=values)
            else:
                track.overridden = False
                track.memory = None
            done.append(entity_id)
        if done:
            self._save()
        return done

    async def turn_off(self, run: RuleRun | None, lights: Iterable[str], transition: int | None) -> None:
        for entity_id in lights:
            if self._is_on(entity_id):
                await self._send_off(entity_id, transition)
        self._save()

    # -- time of day changes --------------------------------------------------------------------------

    @callback
    def time_of_day_changed(self, old: str | None, new: str) -> None:
        """A time of day began: lights follow or stay, devices get their values."""
        self.hass.async_create_task(self._async_time_of_day_changed(old, new), eager_start=True)

    async def _async_time_of_day_changed(self, old: str | None, new: str) -> None:
        for light, fade in list(self.fades.items()):
            if fade.tod != new:
                self._drop_fade(light)
        for run in self.runs:
            if not run.rule["active"]:
                continue
            row = self._row(run, new)
            react = row.get("react", REACT_NONE)
            begin = row.get("begin", BEGIN_FOLLOW_FREE)
            for entity_id in run.rule["lights"]:
                state = self._state(entity_id)
                if is_crescendo(state):
                    await self._set_on_position(
                        entity_id, float(row["brightness"]) if react == REACT_ON and row.get("brightness") else None
                    )
            if row.get("forget"):
                for entity_id in run.rule["lights"]:
                    track = self.tracks.get(entity_id)
                    if track is not None:
                        track.memory = None
            on_lights = [e for e in run.rule["lights"] if self._is_on(e)]
            if row.get("fade") and react == REACT_ON:
                # A fade switches its lights on by itself and runs until the time of day ends.
                for entity_id in run.rule["lights"]:
                    await self._start_fade(run, entity_id, new)
                self._log(run, "fade_start", to=new, lights=list(run.rule["lights"]))
            elif on_lights and react != REACT_NONE:
                if begin == BEGIN_OFF:
                    await self.turn_off(run, on_lights, self._transition(run, row, self._state(on_lights[0])))
                    self._log(run, "begin_off", to=new, lights=on_lights)
                elif begin in (BEGIN_FOLLOW, BEGIN_FOLLOW_FREE) and react == REACT_ON:
                    wanted = [
                        e
                        for e in on_lights
                        if begin == BEGIN_FOLLOW or not self.tracks.get(e, LightTrack(e)).overridden
                    ]
                    # The owner of a light decides; the first rule with it decides for lights nobody owns.
                    wanted = [e for e in wanted if self._decides(run, e)]
                    if wanted:
                        await self.apply_row(run, new, wanted, use_memory=False)
                        self._log(run, "follow", to=new, lights=wanted)
            # Actions right at a begin or an end come with the change itself, also the one after a restart.
            for action in run.rule["actions"]:
                if action["offset"]:
                    continue
                if (action["edge"] == EDGE_START and action["tod"] == new) or (
                    action["edge"] == EDGE_END and action["tod"] == old
                ):
                    await self._apply_device(run, action["entity"], action["value"])
        self._save()

    def _decides(self, run: RuleRun, entity_id: str) -> bool:
        """The rule that switched a light on decides for it; the first rule with it decides otherwise."""
        track = self.tracks.get(entity_id)
        owner = track.owner if track is not None else None
        if owner is not None and any(r.id == owner for r in self.runs if r.rule["active"]):
            return owner == run.id
        runs = self._runs_with(entity_id)
        return bool(runs) and runs[0] is run

    async def _apply_device(self, run: RuleRun, entity_id: str, value: Any, planned: datetime | None = None) -> None:
        """Give a device its value for the time of day, once. Planned is the moment of an action that follows late."""
        domain = entity_id.split(".")[0]
        try:
            if domain == "cover":
                await self.hass.services.async_call(
                    "cover",
                    "set_cover_position",
                    {ATTR_ENTITY_ID: entity_id, "position": int(float(value))},
                    blocking=True,
                )
            elif domain == "climate":
                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {ATTR_ENTITY_ID: entity_id, "temperature": float(value)},
                    blocking=True,
                )
            elif domain == "media_player":
                await self.hass.services.async_call(
                    "media_player",
                    "volume_set",
                    {ATTR_ENTITY_ID: entity_id, "volume_level": float(value) / 100},
                    blocking=True,
                )
            elif domain == "fan":
                await self.hass.services.async_call(
                    "fan", "set_percentage", {ATTR_ENTITY_ID: entity_id, "percentage": int(float(value))}, blocking=True
                )
            elif domain in ("number", "input_number"):
                await self.hass.services.async_call(
                    domain, "set_value", {ATTR_ENTITY_ID: entity_id, "value": float(value)}, blocking=True
                )
            elif domain in ("scene", "script"):
                if value not in (False, "off", 0, "0"):
                    await self.hass.services.async_call(
                        domain, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
                    )
            else:
                on = value not in (False, "off", 0, "0", 0.0)
                await self.hass.services.async_call(
                    "homeassistant",
                    SERVICE_TURN_ON if on else SERVICE_TURN_OFF,
                    {ATTR_ENTITY_ID: entity_id},
                    blocking=True,
                )
            if planned is not None:
                self._log(run, "device", entity=entity_id, value=value, planned=planned.isoformat())
            else:
                self._log(run, "device", entity=entity_id, value=value)
        except Exception as err:
            self._log(run, "device_error", entity=entity_id, error=str(err) or type(err).__name__)

    # -- what the lights report -----------------------------------------------------------------------

    @callback
    def _service_called(self, event: Event) -> None:
        """Remember whether a light.turn_on call from Home Assistant carried a value."""
        data = event.data
        if data.get("domain") != "light" or data.get("service") != SERVICE_TURN_ON:
            return
        service_data = data.get("service_data") or {}
        with_value = any(
            k in service_data
            for k in (
                "brightness",
                "brightness_pct",
                "brightness_step",
                "brightness_step_pct",
                "color_temp_kelvin",
                "color_temp",
                "rgb_color",
                "rgbw_color",
                "rgbww_color",
                "hs_color",
                "xy_color",
                "color_name",
                "white",
                "effect",
            )
        )
        self._service_calls[event.context.id] = with_value
        if len(self._service_calls) > 200:
            for key in list(self._service_calls)[:-100]:
                del self._service_calls[key]

    @callback
    def _light_changed(self, event: Event) -> None:
        self.hass.async_create_task(self._async_light_changed(event), eager_start=True)

    async def _async_light_changed(self, event: Event) -> None:
        entity_id: str = event.data["entity_id"]
        old: State | None = event.data.get("old_state")
        new: State | None = event.data.get("new_state")
        track = self.tracks.setdefault(entity_id, LightTrack(entity_id))
        now = self.now
        if new is None or new.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        values = values_of(new)
        if old is None or old.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            # The first state after a restart or after being unreachable is no change by anybody.
            if values["on"]:
                track.last_on = values
            return
        was_on = old.state == STATE_ON
        if is_crescendo(new) and new.attributes.get("command_source") == SOURCE:
            own = True
        else:
            own = track.is_own(event.context.id if event.context else None, values, now)
        if own:
            if values["on"]:
                track.last_on = values
            else:
                track.owner = None
            return
        fade = self.fades.get(entity_id)
        if fade is not None and fade.state in (FADE_RUNNING, FADE_PAUSED):
            self._cancel_fade(fade, "by_hand")
        if values["on"] and not was_on:
            await self._manual_on(track, new, event.context.id if event.context else None)
        elif values["on"] and was_on:
            if not same_values(values_of(old), values):
                self._override(track, values, "changed")
        elif was_on and not values["on"]:
            await self._manual_off(track)
        if values["on"]:
            track.last_on = values
        self._save()

    def _override(self, track: LightTrack, values: Mapping[str, Any], how: str) -> None:
        track.overridden = True
        track.memory = {"values": dict(values), "at": self.now.isoformat()}
        track.owner = None
        self._log(None, "override", light=track.entity_id, how=how, values=dict(values))

    async def _manual_on(self, track: LightTrack, new: State, context_id: str | None) -> None:
        """A light went on without Maestro: apply the time of day, or respect a chosen value."""
        values = values_of(new)
        if is_crescendo(new):
            with_value = new.attributes.get("command") != CRESCENDO_SWITCH_ON
            external = False
        elif context_id in self._service_calls:
            with_value = self._service_calls[context_id]
            external = False
        else:
            # From outside Home Assistant: a value is chosen if it differs from what the light showed last.
            with_value = track.last_on is not None and not same_values(track.last_on, values)
            external = True
        runs = [run for run in self._runs_with(track.entity_id) if run.rule["manual"]]
        run = runs[0] if runs else None
        if run is not None and external and run.rule.get("external_on") == EXTERNAL_ON_KEEP:
            with_value = True
        if with_value or run is None:
            if with_value:
                self._override(track, values, "on_with_value")
        else:
            row = self._row(run)
            if row.get("react") == REACT_ON:
                wanted, from_memory = self._values_for(track, row)
                if not same_values(
                    {
                        "on": True,
                        "brightness": wanted.get("brightness"),
                        "kelvin": (wanted.get("color") or {}).get("kelvin")
                        if isinstance(wanted.get("color"), Mapping)
                        else wanted.get("kelvin"),
                        "rgb": None,
                    },
                    values,
                ):
                    await self._send_on(None, track.entity_id, wanted, 0)
                track.overridden = from_memory
                if not from_memory:
                    track.memory = None
                self._log(run, "manual_on", light=track.entity_id, memory=from_memory)
        # Lights switched on by hand go off again with motion rules, unless the rule says otherwise.
        for candidate in self._runs_with(track.entity_id):
            self._plan_off_for_manual(candidate, track.entity_id)

    async def _manual_off(self, track: LightTrack) -> None:
        """Somebody switched a light off: it stays off, and motion is ignored for the lock time."""
        if track.overridden and track.memory:
            track.memory["at"] = self.now.isoformat()
        track.owner = None
        track.prewarn = None
        for run in self._runs_with(track.entity_id):
            run.pending.pop(track.entity_id, None)
            run.warned.discard(track.entity_id)
            if run.rule["motion"] and self._lock_seconds(run):
                run.lock_until = self.now + timedelta(seconds=self._lock_seconds(run))
            self._reschedule(run)
        self._log(None, "manual_off", light=track.entity_id)

    # -- motion ---------------------------------------------------------------------------------------

    @callback
    def _motion_changed(self, event: Event) -> None:
        new: State | None = event.data.get("new_state")
        if new is None:
            return
        self.hass.async_create_task(
            self._async_motion(event.data["entity_id"], new.state == STATE_ON), eager_start=True
        )

    async def _async_motion(self, sensor: str, detected: bool) -> None:
        for run in self.runs:
            if not run.rule["active"] or sensor not in run.rule["motion"]:
                continue
            if detected:
                await self._motion_detected(run)
            elif not self._motion_present(run):
                self._all_clear(run)
        self._save()

    async def _motion_detected(self, run: RuleRun) -> None:
        now = self.now
        if run.lock_until is not None and now < run.lock_until:
            self._log(run, "locked")
            return
        run.lock_until = None
        # Motion while the pre-warning dims the lights: back to the previous values.
        if run.warned:
            await self._cancel_prewarn(run)
        on_lights = [e for e in run.rule["lights"] if self._is_on(e)]
        if on_lights:
            # Presence keeps lights on; the countdown starts again when all sensors are clear.
            for entity_id in on_lights:
                run.pending.pop(entity_id, None)
            self._reschedule(run)
            return
        row = self._row(run)
        if row.get("react") != REACT_ON:
            return
        if not self._dark_enough(run, row):
            self._log(run, "bright")
            return
        done = await self.apply_row(run)
        if done:
            self._log(run, "motion_on", lights=done, row=self.rhythm.state.key if self.rhythm.state else None)

    def _all_clear(self, run: RuleRun) -> None:
        """No sensor of the rule sees anybody: the lights that are on go off after their time."""
        row = self._row(run)
        if row.get("react") == REACT_NONE:
            return
        after = self._after(run, row)
        for entity_id in run.rule["lights"]:
            if not self._is_on(entity_id) or entity_id in run.pending or self._held_by_fade(run, entity_id):
                continue
            minutes = self._minutes_for(run, entity_id, after)
            if minutes is None:
                continue
            run.pending[entity_id] = self.now + timedelta(minutes=minutes)
        self._reschedule(run)

    def _minutes_for(self, run: RuleRun, entity_id: str, after: int) -> int | None:
        """Return after how many minutes a light goes off, or None if the rule leaves it alone."""
        track = self.tracks.get(entity_id)
        if track is not None and track.owner == run.id:
            return after
        manual = run.rule.get("manual_after", MANUAL_AFTER_SAME)
        if manual == MANUAL_AFTER_NEVER:
            return None
        if manual == MANUAL_AFTER_SAME:
            return after
        return int(manual)

    def _plan_off_for_manual(self, run: RuleRun, entity_id: str) -> None:
        """A light went on by hand or through a button: plan its end if nobody is there."""
        if not run.rule["active"]:
            return
        row = self._row(run)
        if row.get("react") == REACT_NONE:
            return
        if run.rule["motion"]:
            if self._motion_present(run):
                return
            minutes = self._minutes_for(run, entity_id, self._after(run, row))
        else:
            # Without motion, a row's time means: off this long after switching on.
            minutes = int(row["after"]) if row.get("after") else None
        if minutes is None or minutes <= 0 or self._held_by_fade(run, entity_id):
            return
        run.pending[entity_id] = self.now + timedelta(minutes=minutes)
        self._reschedule(run)

    def _reschedule(self, run: RuleRun) -> None:
        if run.timer is not None:
            run.timer()
            run.timer = None
        run.pending = {e: due for e, due in run.pending.items() if self._is_on(e)}
        if not run.pending:
            return
        due = min(run.pending.values())

        @callback
        def fire(_now: datetime) -> None:
            run.timer = None
            self.hass.async_create_task(self._async_due(run), eager_start=True)

        run.timer = async_track_point_in_utc_time(self.hass, fire, due)

    async def _async_due(self, run: RuleRun) -> None:
        now = self.now
        due = [e for e, at in run.pending.items() if at <= now + timedelta(seconds=1)]
        for entity_id in due:
            run.pending.pop(entity_id, None)
        due = [e for e in due if not self._held_by_fade(run, e)]
        if not due:
            self._reschedule(run)
            return
        row = self._row(run)
        if self._warn_on(run):
            dimmable = [e for e in due if self._is_on(e) and is_dimmable(self._state(e))]
            plain = [e for e in due if e not in dimmable]
            if plain:
                await self.turn_off(run, plain, None)
                self._log(run, "off", lights=plain)
            if dimmable:
                await self._prewarn(run, dimmable)
        else:
            on = [e for e in due if self._is_on(e)]
            await self.turn_off(run, on, self._transition(run, row, self._state(on[0]) if on else None))
            self._log(run, "off", lights=on)
        self._reschedule(run)
        self._save()

    async def _prewarn(self, run: RuleRun, lights: list[str]) -> None:
        """Dim to half for a moment before switching off, so people can wave."""
        for entity_id in lights:
            state = self._state(entity_id)
            track = self.tracks.setdefault(entity_id, LightTrack(entity_id))
            current = values_of(state)
            track.prewarn = current
            half = max(1.0, float(current.get("brightness") or 100) / 2)
            if is_crescendo(state):
                context = Context()
                track.note_context(context.id, self.now)
                await self._call(
                    CRESCENDO_DOMAIN,
                    "fade_to",
                    {
                        ATTR_ENTITY_ID: entity_id,
                        "position": half,
                        "duration": {"seconds": PREWARN_TRANSITION},
                        "source": SOURCE,
                        "devices": False,
                    },
                    context,
                )
            else:
                await self._send_on(
                    None,
                    entity_id,
                    {"brightness": half, "kelvin": current.get("kelvin"), "rgb": current.get("rgb")},
                    PREWARN_TRANSITION,
                )
            track.owner = run.id
            run.warned.add(entity_id)
        self._log(run, "prewarn", lights=lights)
        if run.warn_timer is not None:
            run.warn_timer()

        @callback
        def fire(_now: datetime) -> None:
            run.warn_timer = None
            self.hass.async_create_task(self._async_warn_over(run), eager_start=True)

        run.warn_timer = async_track_point_in_utc_time(
            self.hass, fire, self.now + timedelta(seconds=int(self.defaults["warn_seconds"]))
        )

    async def _async_warn_over(self, run: RuleRun) -> None:
        lights = [e for e in run.warned if self._is_on(e)]
        run.warned.clear()
        for entity_id in lights:
            track = self.tracks.get(entity_id)
            if track is not None:
                track.prewarn = None
        await self.turn_off(run, lights, QUICK_TRANSITION)
        self._log(run, "off", lights=lights)

    async def _cancel_prewarn(self, run: RuleRun) -> None:
        if run.warn_timer is not None:
            run.warn_timer()
            run.warn_timer = None
        lights = list(run.warned)
        run.warned.clear()
        for entity_id in lights:
            track = self.tracks.get(entity_id)
            previous = track.prewarn if track else None
            if track is not None:
                track.prewarn = None
            if previous and previous.get("on") and self._is_on(entity_id):
                await self._send_on(run, entity_id, previous, PREWARN_TRANSITION)
        self._log(run, "prewarn_cancelled", lights=lights)

    # -- buttons --------------------------------------------------------------------------------------

    @callback
    def _button_changed(self, event: Event) -> None:
        old: State | None = event.data.get("old_state")
        new: State | None = event.data.get("new_state")
        if new is None or old is None or new.state == old.state or new.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        if old.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        entity_id = event.data["entity_id"]
        event_type = new.attributes.get("event_type")
        for run in self.runs:
            if not run.rule["active"]:
                continue
            for button in run.rule["buttons"]:
                if button["entity"] != entity_id:
                    continue
                if button.get("event") and event_type is not None and button["event"] != event_type:
                    continue
                self.hass.async_create_task(self.async_toggle(run, "toggle", by="button"), eager_start=True)

    async def async_toggle(self, run: RuleRun, mode: str = "toggle", by: str = "action") -> None:
        """Switch the rule's lights: off when any is on, else on with the row of the time of day."""
        on_lights = [e for e in run.rule["lights"] if self._is_on(e)]
        if mode == "off" or (mode == "toggle" and on_lights):
            for entity_id in on_lights:
                fade = self.fades.get(entity_id)
                if fade is not None and fade.state in (FADE_RUNNING, FADE_PAUSED):
                    self._cancel_fade(fade, by)
            await self.turn_off(run, on_lights, QUICK_TRANSITION)
            run.pending = {e: d for e, d in run.pending.items() if e not in on_lights}
            self._reschedule(run)
            self._log(run, "toggle_off", by=by, lights=on_lights)
            return
        row = self._row(run)
        if row.get("react") != REACT_ON:
            self._log(run, "toggle_ignored", by=by)
            return
        done = await self.apply_row(run)
        for entity_id in done:
            self._plan_off_for_manual(run, entity_id) if not run.rule["motion"] else None
        if run.rule["motion"] and not self._motion_present(run):
            self._all_clear(run)
        self._log(run, "toggle_on", by=by, lights=done)

    # -- fades over a whole time of day ---------------------------------------------------------------

    def _held_by_fade(self, run: RuleRun, entity_id: str) -> bool:
        """While a fade runs, motion does not switch its light off, unless the rule says so."""
        fade = self.fades.get(entity_id)
        return fade is not None and fade.state == FADE_RUNNING and bool(run.rule.get("fade_hold", True))

    def _fade_target(self, run: RuleRun, tod: str) -> tuple[float, int | None]:
        """Return where a fade ends: the row's own target, else the next time of day's row, else 100 %."""
        row = run.rule["rows"].get(tod) or {}
        own = row.get("color") if isinstance(row.get("color"), Mapping) else {}
        state = self.rhythm.state
        nxt = run.rule["rows"].get(state.next_key or "") if state is not None and state.key == tod else None
        nxt_color = (nxt or {}).get("color") if isinstance((nxt or {}).get("color"), Mapping) else {}
        kelvin = nxt_color.get("kelvin") or own.get("kelvin")
        if row.get("fade_to"):
            return float(row["fade_to"]), kelvin
        if nxt and nxt.get("react") == REACT_ON and nxt.get("brightness"):
            return float(nxt["brightness"]), kelvin
        return 100.0, kelvin

    async def _start_fade(self, run: RuleRun, entity_id: str, tod: str | None) -> None:
        """Start a light's fade from the row's brightness, or from where it is, to the end of the time of day."""
        state = self.rhythm.state
        light = self._state(entity_id)
        if tod is None or state is None or state.key != tod or state.until is None:
            return
        if light is None or light.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        now = self.now
        row = run.rule["rows"].get(tod) or {}
        target, kelvin_to = self._fade_target(run, tod)
        current = values_of(light)
        own = row.get("color") if isinstance(row.get("color"), Mapping) else {}
        begin = float(current["brightness"]) if current["on"] else float(row.get("brightness") or 1)
        kelvin_from = current.get("kelvin") if current["on"] and current.get("kelvin") else own.get("kelvin")
        self._drop_fade(entity_id)
        self.fades[entity_id] = Fade(run.id, entity_id, tod, now, state.until, begin, target, kelvin_from, kelvin_to)
        track = self.tracks.setdefault(entity_id, LightTrack(entity_id))
        track.overridden = False
        track.memory = None
        await self._fade_step(entity_id, first=not current["on"])
        self._save()

    async def _fade_step(self, entity_id: str, first: bool = False) -> None:
        """Send the next part of a fade: one command per part, the light or Crescendo fades by itself."""
        fade = self.fades.get(entity_id)
        if fade is None or fade.state != FADE_RUNNING:
            return
        self._cancel_fade_timer(entity_id)
        self._fade_sent.add(entity_id)
        run = self.run_by(fade.rule)
        light = self._state(entity_id)
        now = self.now
        remaining = (fade.end - now).total_seconds()
        here = {"on": True, "brightness": fade.value_at(now)}
        if first:
            await self._send_on(run, entity_id, {"brightness": fade.value_at(now), "kelvin": fade.kelvin_at(now)}, 0)
        if remaining <= 1:
            await self._send_on(run, entity_id, {"brightness": fade.target, "kelvin": fade.kelvin_to}, 1, start=here)
            return
        next_at = None
        if is_crescendo(light):
            await self._send_on(run, entity_id, {"brightness": fade.target}, round(remaining), start=here)
        elif can_transition(light):
            chunk_end = min(fade.end, now + MAX_CHUNK)
            seconds = round((chunk_end - now).total_seconds())
            values = {"brightness": fade.value_at(chunk_end), "kelvin": fade.kelvin_at(chunk_end)}
            await self._send_on(run, entity_id, values, seconds, start=here)
            next_at = chunk_end if chunk_end < fade.end else None
        else:
            # A light without its own fade gets small steps.
            await self._send_on(run, entity_id, {"brightness": fade.value_at(now), "kelvin": fade.kelvin_at(now)}, None)
            step = timedelta(seconds=max(30.0, (fade.end - fade.start).total_seconds() / 100))
            next_at = min(fade.end, now + step)
        if next_at is not None:

            @callback
            def fire(_now: datetime) -> None:
                self._fade_timers.pop(entity_id, None)
                self.hass.async_create_task(self._fade_step(entity_id), eager_start=True)

            self._fade_timers[entity_id] = async_track_point_in_utc_time(self.hass, fire, next_at)

    def _cancel_fade_timer(self, entity_id: str) -> None:
        timer = self._fade_timers.pop(entity_id, None)
        if timer is not None:
            timer()

    def _drop_fade(self, entity_id: str) -> None:
        self._cancel_fade_timer(entity_id)
        self._fade_sent.discard(entity_id)
        self.fades.pop(entity_id, None)

    def _cancel_fade(self, fade: Fade, by: str) -> None:
        """Somebody changed the light: the fade stops and can be resumed."""
        if fade.state == FADE_RUNNING:
            fade.held = fade.value_at(self.now)
        fade.state = FADE_CANCELLED
        self._cancel_fade_timer(fade.light)
        self._log(self.run_by(fade.rule), "fade_cancelled", light=fade.light, by=by)
        self._save()

    async def _pause_fade(self, fade: Fade) -> None:
        """The running time of day was pinned: the fade holds where it is."""
        now = self.now
        fade.held = fade.value_at(now)
        fade.state = FADE_PAUSED
        self._cancel_fade_timer(fade.light)
        light = self._state(fade.light)
        if is_crescendo(light):
            context = Context()
            self.tracks.setdefault(fade.light, LightTrack(fade.light)).note_context(context.id, now)
            await self._call(CRESCENDO_DOMAIN, "stop", {ATTR_ENTITY_ID: fade.light, "source": SOURCE}, context)
        else:
            run = self.run_by(fade.rule)
            await self._send_on(run, fade.light, {"brightness": fade.held, "kelvin": fade.kelvin_at(now)}, 1)
        self._log(self.run_by(fade.rule), "fade_paused", light=fade.light)

    async def _resume_fade(self, fade: Fade, quick: bool = True) -> None:
        """Continue a fade: to where it would be by now, then on to the end of the time of day."""
        state = self.rhythm.state
        if state is None or state.key != fade.tod or state.until is None or state.until <= self.now:
            return
        now = self.now
        if fade.state == FADE_PAUSED and fade.held is not None:
            fade.begin = fade.held
            fade.start = now
        elif fade.state == FADE_CANCELLED:
            fade.begin = fade.value_at(now)
            fade.start = now
        fade.end = state.until
        fade.state = FADE_RUNNING
        fade.held = None
        track = self.tracks.setdefault(fade.light, LightTrack(fade.light))
        track.overridden = False
        track.memory = None
        run = self.run_by(fade.rule)
        if quick:
            await self._send_on(
                run, fade.light, {"brightness": fade.begin, "kelvin": fade.kelvin_at(now)}, RESUME_TRANSITION
            )

            @callback
            def later(_now: datetime) -> None:
                self._fade_timers.pop(fade.light, None)
                self.hass.async_create_task(self._fade_step(fade.light), eager_start=True)

            self._cancel_fade_timer(fade.light)
            self._fade_timers[fade.light] = async_call_later(self.hass, RESUME_TRANSITION, later)
        else:
            await self._fade_step(fade.light)
        self._log(run, "fade_resumed", light=fade.light)
        self._save()

    async def async_resume_fades(self, lights: Iterable[str] | None = None) -> None:
        """Continue fades that were stopped by hand."""
        for fade in list(self.fades.values()):
            if fade.state == FADE_CANCELLED and (lights is None or fade.light in lights):
                await self._resume_fade(fade)

    @callback
    def _rhythm_updated(self) -> None:
        """After every evaluation of the rhythm: plan actions with an offset and keep fades in step."""
        self._schedule_actions()
        self.hass.async_create_task(self._async_check_fades(), eager_start=True)

    async def _async_check_fades(self) -> None:
        state = self.rhythm.state
        if state is None:
            return
        now = self.now
        for light, fade in list(self.fades.items()):
            run = self.run_by(fade.rule)
            row = run.rule["rows"].get(fade.tod) if run is not None else None
            if run is None or not row or not row.get("fade") or state.key != fade.tod:
                self._drop_fade(light)
                continue
            if fade.state == FADE_CANCELLED:
                continue
            holding = state.pinned and state.planned == fade.tod
            if holding:
                if fade.state == FADE_RUNNING:
                    await self._pause_fade(fade)
            elif fade.state == FADE_PAUSED:
                await self._resume_fade(fade, quick=False)
            elif state.until is not None and abs((state.until - fade.end).total_seconds()) > 20:
                # The end moved: on from where the light is, slower or faster.
                fade.begin = fade.value_at(now)
                fade.start = now
                fade.end = state.until
                await self._fade_step(light)
                self._log(run, "fade_moved", light=light)
            elif light not in self._fade_sent and fade.end > now:
                # After a restart: on from the point the fade has reached.
                await self._fade_step(light, first=not self._is_on(light))
        self._save()

    def describe_fades(self) -> list[dict[str, Any]]:
        now = self.now
        out = []
        for fade in self.fades.values():
            run = self.run_by(fade.rule)
            light = self._state(fade.light)
            out.append(
                {
                    "rule": fade.rule,
                    "rule_name": run.name if run else fade.rule,
                    "light": fade.light,
                    "name": (light.attributes.get("friendly_name") if light else None) or fade.light,
                    "tod": fade.tod,
                    "state": fade.state,
                    "begin": fade.begin,
                    "target": fade.target,
                    "start": fade.start.isoformat(),
                    "end": fade.end.isoformat(),
                    "value": fade.held if fade.state != FADE_RUNNING and fade.held is not None else fade.value_at(now),
                    "progress": round(fade.share(now) * 100),
                }
            )
        return out

    # -- actions with an offset -----------------------------------------------------------------------

    @staticmethod
    def _action_key(run: RuleRun, action: Mapping[str, Any]) -> str:
        """Name an action by when it happens. A new value keeps the name, a new moment makes a new action."""
        return f"{run.id}|{action['entity']}|{action['tod']}|{action['edge']}|{action['offset']}"

    @callback
    def _schedule_actions(self) -> None:
        """Carry out every action with an offset once per occasion, at its moment or as soon as possible after it.

        An action that was missed, because Home Assistant was not running or because the plan moved its moment into
        the past, follows while the time of day that begins at its edge is still running. One that has run does not
        run again for the same day when the plan moves it later. An action that is new, or whose rule was paused,
        starts with the moments still to come.
        """
        now = dt_util.utcnow()
        book: dict[str, Any] = self.rhythm.data.setdefault("actions", {})
        seen: set[str] = set()
        changed = False
        wanted: dict[str, tuple[datetime, RuleRun, Mapping[str, Any]]] = {}
        due: list[tuple[str, str, datetime, RuleRun, Mapping[str, Any]]] = []
        for run in self.runs:
            if not run.rule["active"]:
                continue
            for action in run.rule["actions"]:
                if not action["offset"]:
                    continue  # comes with the change of the time of day
                key = self._action_key(run, action)
                if key in seen:
                    continue
                seen.add(key)
                edges = self.rhythm.edges(action["tod"], action["edge"])
                offset = timedelta(minutes=action["offset"])
                entry = book.get(key)
                if not isinstance(entry, dict) or not isinstance(entry.get("fired"), dict):
                    # New, or the rule was paused: what has passed counts as done.
                    entry = book[key] = {"fired": {day: None for day, at, _u in edges if at + offset <= now}}
                    changed = True
                for day, edge_at, until in edges:
                    if day in entry["fired"]:
                        continue
                    moment = edge_at + offset
                    if moment > now:
                        if key not in wanted or moment < wanted[key][0]:
                            wanted[key] = (moment, run, action)
                    elif now < until or now - moment < ACTION_GRACE:
                        due.append((key, day, moment, run, action))
        # Forget what belongs to actions that are gone or paused, and days long past.
        old = (now - timedelta(days=ACTION_KEEP_DAYS)).date().isoformat()
        for key in list(book):
            if key not in seen:
                del book[key]
                changed = True
                continue
            book[key]["fired"] = {d: m for d, m in book[key]["fired"].items() if d >= old}
        for key in list(self._action_timers):
            if key not in wanted or wanted[key][0] != self._action_planned.get(key):
                self._action_timers.pop(key)()
                self._action_planned.pop(key, None)
        for key, (moment, _run, _action) in wanted.items():
            if key in self._action_timers:
                continue

            @callback
            def fire(_now: datetime, key: str = key) -> None:
                self._action_timers.pop(key, None)
                self._action_planned.pop(key, None)
                self._schedule_actions()

            self._action_planned[key] = moment
            self._action_timers[key] = async_track_point_in_utc_time(self.hass, fire, moment)
        for key, day, moment, run, action in due:
            book[key]["fired"][day] = moment.isoformat()
            late = moment if now - moment >= ACTION_GRACE else None
            self.hass.async_create_task(
                self._apply_device(run, action["entity"], action["value"], planned=late), eager_start=True
            )
        if due or changed:
            # Stored at once, so a restart right after it still knows which moments are done.
            self._save()

    def describe_actions(self) -> list[dict[str, Any]]:
        """Return the coming and the last moments of all actions."""
        out = []
        book = self.rhythm.data.get("actions") or {}
        for run in self.runs:
            for action in run.rule["actions"]:
                key = self._action_key(run, action)
                moment = self._action_planned.get(key)
                fired = (book.get(key) or {}).get("fired") or {}
                done = [datetime.fromisoformat(m) for m in fired.values() if m]
                out.append(
                    {
                        "rule": run.id,
                        "rule_name": run.name,
                        **action,
                        "next": moment.isoformat() if moment else None,
                        "last": max(done).isoformat() if done else None,
                    }
                )
        return out

    # -- for the page, the card and the actions -------------------------------------------------------

    def run_by(self, ident: str) -> RuleRun | None:
        """Return a rule by its id or its name."""
        wanted = ident.casefold()
        for run in self.runs:
            if run.id == ident or run.name.casefold() == wanted:
                return run
        return None

    async def async_test(self, run: RuleRun, key: str) -> None:
        """Apply a row now, as a test from the page. A fade runs in 20 seconds instead of the whole time of day."""
        row = self._row(run, key)
        if row.get("fade") and row.get("react") == REACT_ON:
            target, kelvin_to = self._fade_target(run, key)
            begin = float(row.get("brightness") or 1)
            kelvin_from = (row.get("color") or {}).get("kelvin") if isinstance(row.get("color"), Mapping) else None
            for entity_id in run.rule["lights"]:
                await self._send_on(run, entity_id, {"brightness": begin, "kelvin": kelvin_from}, 0)
                await self._send_on(
                    run,
                    entity_id,
                    {"brightness": target, "kelvin": kelvin_to},
                    20,
                    start={"on": True, "brightness": begin},
                )
        else:
            await self.apply_row(run, key, use_memory=False)
        self._log(run, "test", row=key)

    async def async_test_action(self, run: RuleRun, index: int) -> None:
        """Carry out one action now, as a test from the page."""
        action = run.rule["actions"][index]
        await self._apply_device(run, action["entity"], action["value"])

    async def async_forget(self, lights: Iterable[str] | None = None) -> None:
        """Forget what was set by hand."""
        for entity_id in lights if lights is not None else list(self.tracks):
            track = self.tracks.get(entity_id)
            if track is not None:
                track.memory = None
                track.overridden = False
        self._save()
        self._log(None, "forget", lights=list(lights) if lights is not None else None)

    def overridden(self) -> list[dict[str, Any]]:
        """Return the lights people changed by hand, with what is remembered."""
        out = []
        for entity_id, track in sorted(self.tracks.items()):
            if track.overridden or track.memory:
                out.append(
                    {
                        "entity_id": entity_id,
                        "name": (
                            self._state(entity_id).attributes.get("friendly_name") if self._state(entity_id) else None
                        )
                        or entity_id,
                        "overridden": track.overridden,
                        "memory": track.memory,
                        "on": self._is_on(entity_id),
                    }
                )
        return out

    def describe(self) -> list[dict[str, Any]]:
        """Return the rules' live state for the page."""
        return [
            {
                "id": run.id,
                "name": run.name,
                "active": run.rule["active"],
                "on": [e for e in run.rule["lights"] if self._is_on(e)],
                "pending": {e: d.isoformat() for e, d in run.pending.items()},
                "locked_until": run.lock_until.isoformat() if run.lock_until and run.lock_until > self.now else None,
                "motion": self._motion_present(run) if run.rule["motion"] else None,
            }
            for run in self.runs
        ]
