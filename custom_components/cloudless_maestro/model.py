"""A rhythm's settings: validation, stable keys and templates."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import copy
import re
from typing import Any

import voluptuous as vol

from .schedule import SUN_EVENTS, WEEKDAYS

OPTIONS_VERSION = 1

KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,39}$")
CLOCK_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
SERVICE_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)(\s*\+\s*1)?$")

KEY = vol.All(str, vol.Match(KEY_RE, msg="a key uses lowercase letters, digits and _"))
CLOCK = vol.All(str, vol.Match(CLOCK_RE, msg="a time looks like 06:30"))
COLOR = vol.All(str, vol.Match(r"^#[0-9a-fA-F]{6}$", msg="a color looks like #f2a65a"))
ICON = vol.All(str, vol.Match(r"^[a-z0-9-]+:[a-z0-9-]+$", msg="an icon looks like mdi:weather-night"))
NAME = vol.All(str, vol.Strip, vol.Length(min=1, max=60))

DEFAULT_ICON = "mdi:clock-outline"
DEFAULT_COLOR = "#7a8599"
DEFAULT_TRANSITION = 60

_FIXED = vol.Schema(
    {
        vol.Required("kind"): "fixed",
        vol.Required("time"): CLOCK,
        vol.Optional("next_day", default=False): bool,
    }
)
_SUN = vol.Schema(
    {
        vol.Required("kind"): "sun",
        vol.Required("event"): vol.In(SUN_EVENTS),
        vol.Optional("offset", default=0): vol.All(vol.Coerce(int), vol.Range(min=-720, max=720)),
        vol.Optional("earliest", default=None): vol.Any(None, CLOCK),
        vol.Optional("latest", default=None): vol.Any(None, CLOCK),
        vol.Optional("next_day", default=False): bool,
    }
)


def time_spec(value: Any) -> dict[str, Any]:
    """Validate a start time or day end."""
    if not isinstance(value, Mapping):
        raise vol.Invalid("a time is an object with kind fixed or sun")
    if value.get("kind") == "fixed":
        return dict(_FIXED(dict(value)))
    if value.get("kind") == "sun":
        spec = dict(_SUN(dict(value)))
        if spec["earliest"] and spec["latest"] and spec["earliest"] > spec["latest"]:
            raise vol.Invalid("earliest lies after latest")
        return spec
    raise vol.Invalid("a time has kind fixed or sun")


TIME_OF_DAY = vol.Schema(
    {
        vol.Required("key"): KEY,
        vol.Required("name"): NAME,
        vol.Optional("icon", default=DEFAULT_ICON): ICON,
        vol.Optional("color", default=DEFAULT_COLOR): COLOR,
        vol.Optional("transition", default=DEFAULT_TRANSITION): vol.All(vol.Coerce(int), vol.Range(min=0, max=3600)),
    }
)
BASE = vol.Schema(
    {
        vol.Required("key"): KEY,
        vol.Required("name"): NAME,
        vol.Optional("icon", default="mdi:weather-night"): ICON,
        vol.Optional("color", default="#2e3a6b"): COLOR,
        vol.Optional("transition", default=DEFAULT_TRANSITION): vol.All(vol.Coerce(int), vol.Range(min=0, max=3600)),
    }
)
MODEL = vol.Schema(
    {
        vol.Required("key"): KEY,
        vol.Required("name"): NAME,
        vol.Optional("entries", default=list): [vol.Schema({vol.Required("tod"): KEY, vol.Required("at"): time_spec})],
        vol.Required("end"): time_spec,
    }
)
LINK = vol.Schema(
    {
        vol.Required("calendar"): vol.All(str, vol.Match(r"^calendar\.[a-z0-9_]+$", msg="choose a calendar")),
        vol.Optional("match", default=""): vol.All(str, vol.Strip, vol.Length(max=100)),
        vol.Required("model"): KEY,
    }
)
LOCATION = vol.Any(
    None,
    vol.Schema(
        {
            vol.Required("latitude"): vol.All(vol.Coerce(float), vol.Range(min=-90, max=90)),
            vol.Required("longitude"): vol.All(vol.Coerce(float), vol.Range(min=-180, max=180)),
        }
    ),
)
_OPTIONS = vol.Schema(
    {
        vol.Optional("version", default=OPTIONS_VERSION): vol.Coerce(int),
        vol.Required("base"): BASE,
        vol.Optional("times_of_day", default=list): [TIME_OF_DAY],
        vol.Optional("models", default=list): [MODEL],
        vol.Optional("week", default=dict): vol.Schema({vol.Optional(day): vol.Any(None, KEY) for day in WEEKDAYS}),
        vol.Optional("calendar_links", default=list): [LINK],
        vol.Optional("location", default=None): LOCATION,
    },
    extra=vol.REMOVE_EXTRA,
)


def _unique(keys: Iterable[str], what: str) -> None:
    seen: set[str] = set()
    for key in keys:
        if key in seen:
            raise vol.Invalid(f"the key {key} is used for two {what}")
        seen.add(key)


def normalize_options(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a rhythm's settings and fill in defaults. Raises vol.Invalid with a readable message."""
    options = _OPTIONS(copy.deepcopy(dict(raw)))
    tods = [t["key"] for t in options["times_of_day"]]
    _unique([options["base"]["key"], *tods], "times of day")
    _unique([m["key"] for m in options["models"]], "day models")
    known = set(tods)
    for model in options["models"]:
        used = [e["tod"] for e in model["entries"]]
        for key in used:
            if key not in known:
                raise vol.Invalid(f"the day model {model['name']} uses an unknown time of day: {key}")
        if len(set(used)) != len(used):
            raise vol.Invalid(f"a time of day appears twice in the day model {model['name']}")
        if model["end"]["kind"] == "sun" and not model["end"]["latest"]:
            raise vol.Invalid(f"the day end of {model['name']} follows the sun and needs a latest time")
    models = {m["key"] for m in options["models"]}
    week = {day: options["week"].get(day) for day in WEEKDAYS}
    for day, key in week.items():
        if key is not None and key not in models:
            raise vol.Invalid(f"the week plan uses an unknown day model on {day}: {key}")
    options["week"] = week
    for link in options["calendar_links"]:
        if link["model"] not in models:
            raise vol.Invalid(f"a calendar link uses an unknown day model: {link['model']}")
    options["version"] = OPTIONS_VERSION
    return options


ADJUSTMENT = vol.Schema(
    {
        vol.Optional("model", default=None): vol.Any(None, KEY),
        vol.Optional("times", default=dict): {KEY: time_spec},
        vol.Optional("end", default=None): vol.Any(None, time_spec),
    }
)


def normalize_adjustment(raw: Mapping[str, Any], options: Mapping[str, Any]) -> dict[str, Any] | None:
    """Validate a day adjustment against the settings. Returns None if nothing deviates."""
    adjustment = ADJUSTMENT(dict(raw))
    if adjustment["model"] is not None and adjustment["model"] not in {m["key"] for m in options["models"]}:
        raise vol.Invalid(f"unknown day model: {adjustment['model']}")
    tods = {t["key"] for t in options["times_of_day"]}
    for key in adjustment["times"]:
        if key not in tods:
            raise vol.Invalid(f"unknown time of day: {key}")
    if adjustment["end"] is not None and adjustment["end"]["kind"] == "sun" and not adjustment["end"]["latest"]:
        raise vol.Invalid("a day end that follows the sun needs a latest time")
    if adjustment["model"] is None and not adjustment["times"] and adjustment["end"] is None:
        return None
    return adjustment


def service_time(value: Any) -> dict[str, Any]:
    """Read a time from an action: 23:30, 01:00+1 for the following day, or a full time object."""
    if isinstance(value, Mapping):
        return time_spec(value)
    match = SERVICE_TIME_RE.match(str(value).strip())
    if not match:
        raise vol.Invalid("a time looks like 23:30, or 01:00+1 for the following day")
    return {"kind": "fixed", "time": f"{int(match[1]):02d}:{match[2]}", "next_day": bool(match[3])}


# -- keys ---------------------------------------------------------------------------------------------

_GERMAN = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "ae", "Ö": "oe", "Ü": "ue"})


def make_key(name: str, taken: Iterable[str] = ()) -> str:
    """Make a stable key from a name, unique among the taken ones. The same rule runs in the frontend."""
    base = re.sub(r"[^a-z0-9]+", "_", name.translate(_GERMAN).lower()).strip("_")[:36] or "item"
    if not base[0].isalnum():
        base = f"x{base}"
    taken = set(taken)
    key, n = base, 2
    while key in taken:
        key = f"{base}_{n}"
        n += 1
    return key


# -- templates ----------------------------------------------------------------------------------------

_NAMES = {
    "de": {
        "base": "Nacht",
        "wake": "Aufstehen",
        "morning": "Morgen",
        "midday": "Mittag",
        "afternoon": "Nachmittag",
        "evening": "Abend",
        "bedtime": "Einschlafen",
        "day": "Tag",
        "workday": "Werktag",
        "weekend": "Wochenende",
        "daily": "Täglich",
    },
    "en": {
        "base": "Night",
        "wake": "Wake up",
        "morning": "Morning",
        "midday": "Midday",
        "afternoon": "Afternoon",
        "evening": "Evening",
        "bedtime": "Bedtime",
        "day": "Day",
        "workday": "Workday",
        "weekend": "Weekend",
        "daily": "Daily",
    },
}
_LOOKS = {
    "wake": ("mdi:weather-sunset-up", "#f2a65a"),
    "morning": ("mdi:coffee-outline", "#f2c94c"),
    "midday": ("mdi:white-balance-sunny", "#7cc6e8"),
    "afternoon": ("mdi:weather-partly-cloudy", "#6fb98f"),
    "evening": ("mdi:weather-sunset-down", "#c46bae"),
    "bedtime": ("mdi:bed-outline", "#6c63b5"),
    "day": ("mdi:white-balance-sunny", "#f2c94c"),
}

TEMPLATE_DAY = "day"
TEMPLATE_EMPTY = "empty"
TEMPLATES = (TEMPLATE_DAY, TEMPLATE_EMPTY)


def _fixed(clock: str, next_day: bool = False) -> dict[str, Any]:
    return {"kind": "fixed", "time": clock, "next_day": next_day}


def time_of_day_templates(language: str) -> list[dict[str, Any]]:
    """Return the templates offered when adding a time of day, in the user's language."""
    names = _NAMES.get(language, _NAMES["en"])
    return [
        {"key": make_key(names[k]), "name": names[k], "icon": icon, "color": color, "transition": DEFAULT_TRANSITION}
        for k, (icon, color) in _LOOKS.items()
        if k != "day"
    ]


def default_options(language: str = "en", template: str = TEMPLATE_DAY) -> dict[str, Any]:
    """Return the settings of a new rhythm."""
    names = _NAMES.get(language, _NAMES["en"])
    base = {"key": make_key(names["base"]), "name": names["base"], "icon": "mdi:weather-night", "color": "#2e3a6b"}

    def tod(kind: str) -> dict[str, Any]:
        icon, color = _LOOKS[kind]
        return {"key": make_key(names[kind]), "name": names[kind], "icon": icon, "color": color}

    if template == TEMPLATE_EMPTY:
        day = tod("day")
        model = {
            "key": make_key(names["daily"]),
            "name": names["daily"],
            "entries": [{"tod": day["key"], "at": _fixed("08:00")}],
            "end": _fixed("20:00"),
        }
        return normalize_options(
            {"base": base, "times_of_day": [day], "models": [model], "week": dict.fromkeys(WEEKDAYS, model["key"])}
        )
    kinds = ("wake", "morning", "midday", "afternoon", "evening", "bedtime")
    tods = [tod(k) for k in kinds]
    key = {k: t["key"] for k, t in zip(kinds, tods, strict=True)}
    evening = {"kind": "sun", "event": "sunset", "offset": -30, "earliest": "18:00", "latest": "21:00"}
    workday = {
        "key": make_key(names["workday"]),
        "name": names["workday"],
        "entries": [
            {"tod": key["wake"], "at": _fixed("06:30")},
            {"tod": key["morning"], "at": _fixed("07:00")},
            {"tod": key["midday"], "at": _fixed("12:00")},
            {"tod": key["afternoon"], "at": _fixed("14:00")},
            {"tod": key["evening"], "at": evening},
            {"tod": key["bedtime"], "at": _fixed("22:30")},
        ],
        "end": _fixed("23:30"),
    }
    weekend = {
        "key": make_key(names["weekend"]),
        "name": names["weekend"],
        "entries": [
            {"tod": key["wake"], "at": _fixed("08:00")},
            {"tod": key["morning"], "at": _fixed("08:30")},
            {"tod": key["midday"], "at": _fixed("12:30")},
            {"tod": key["afternoon"], "at": _fixed("14:30")},
            {"tod": key["evening"], "at": evening},
            {"tod": key["bedtime"], "at": _fixed("23:00")},
        ],
        "end": _fixed("00:30", next_day=True),
    }
    week = {d: workday["key"] for d in WEEKDAYS[:5]} | {d: weekend["key"] for d in WEEKDAYS[5:]}
    return normalize_options({"base": base, "times_of_day": tods, "models": [workday, weekend], "week": week})
