"""A rhythm's settings: validation, stable keys, templates and the rules."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import copy
import re
from typing import Any

import voluptuous as vol

from .schedule import SUN_EVENTS, WEEKDAYS

OPTIONS_VERSION = 2

KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,39}$")
CLOCK_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
SERVICE_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)(\s*\+\s*1)?$")

KEY = vol.All(str, vol.Match(KEY_RE, msg="a key uses lowercase letters, digits and _"))
CLOCK = vol.All(str, vol.Match(CLOCK_RE, msg="a time looks like 06:30"))
COLOR = vol.All(str, vol.Match(r"^#[0-9a-fA-F]{6}$", msg="a color looks like #f2a65a"))
ICON = vol.All(str, vol.Match(r"^[a-z0-9-]+:[a-z0-9-]+$", msg="an icon looks like mdi:weather-night"))
NAME = vol.All(str, vol.Strip, vol.Length(min=1, max=60))
ENTITY = vol.All(str, vol.Match(r"^[a-z_]+\.[a-z0-9_]+$", msg="an entity id looks like light.kitchen"))
LIGHT = vol.All(str, vol.Match(r"^light\.[a-z0-9_]+$", msg="a light's entity id starts with light."))

DEFAULT_ICON = "mdi:clock-outline"
DEFAULT_COLOR = "#7a8599"

# Reactions of a rule's row, what happens when a time of day begins, and the rule-level choices.
REACT_ON = "on"
REACT_OFF_ONLY = "off_only"
REACT_NONE = "none"
REACTIONS = (REACT_ON, REACT_OFF_ONLY, REACT_NONE)
BEGIN_FOLLOW_FREE = "follow_free"
BEGIN_FOLLOW = "follow"
BEGIN_KEEP = "keep"
BEGIN_OFF = "off"
BEGINS = (BEGIN_FOLLOW_FREE, BEGIN_FOLLOW, BEGIN_KEEP, BEGIN_OFF)
MANUAL_AFTER_SAME = "same"
MANUAL_AFTER_NEVER = "never"
EXTERNAL_ON_APPLY = "apply"
EXTERNAL_ON_KEEP = "keep"

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
        # Until 0.1.0b1 the transition lived here. It is a default of the rules now.
        vol.Remove("transition"): object,
    }
)
BASE = vol.Schema(
    {
        vol.Required("key"): KEY,
        vol.Required("name"): NAME,
        vol.Optional("icon", default="mdi:weather-night"): ICON,
        vol.Optional("color", default="#37474f"): COLOR,
        vol.Remove("transition"): object,
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

_MINUTES = vol.All(vol.Coerce(int), vol.Range(min=0, max=1440))
_SECONDS = vol.All(vol.Coerce(int), vol.Range(min=0, max=7200))
DEFAULTS = vol.Schema(
    {
        vol.Optional("transition", default=60): _SECONDS,
        vol.Optional("memory", default=15): _MINUTES,
        vol.Optional("after", default=3): _MINUTES,
        vol.Optional("warn", default=True): bool,
        vol.Optional("warn_seconds", default=20): vol.All(vol.Coerce(int), vol.Range(min=3, max=300)),
        vol.Optional("lock", default=30): vol.All(vol.Coerce(int), vol.Range(min=0, max=3600)),
    },
    extra=vol.REMOVE_EXTRA,
)
COLOR_VALUE = vol.Any(
    None,
    vol.Schema({vol.Required("kelvin"): vol.All(vol.Coerce(int), vol.Range(min=1000, max=10000))}),
    vol.Schema({vol.Required("rgb"): vol.All([vol.All(vol.Coerce(int), vol.Range(min=0, max=255))], vol.Length(3, 3))}),
)
ROW = vol.Schema(
    {
        vol.Optional("react", default=REACT_ON): vol.In(REACTIONS),
        vol.Optional("brightness", default=None): vol.Any(None, vol.All(vol.Coerce(int), vol.Range(min=1, max=100))),
        vol.Optional("color", default=None): COLOR_VALUE,
        vol.Optional("after", default=None): vol.Any(None, _MINUTES),
        vol.Optional("begin", default=BEGIN_FOLLOW_FREE): vol.In(BEGINS),
        vol.Optional("transition", default=None): vol.Any(None, _SECONDS),
        vol.Optional("memory", default=None): vol.Any(None, _MINUTES),
        vol.Optional("forget", default=False): bool,
        vol.Optional("lux_below", default=None): vol.Any(None, vol.Coerce(float)),
    },
    extra=vol.REMOVE_EXTRA,
)
DEVICE = vol.Schema(
    {
        vol.Required("entity"): ENTITY,
        vol.Optional("values", default=dict): {KEY: vol.Any(None, bool, vol.Coerce(float), str)},
    }
)
BUTTON = vol.Schema({vol.Required("entity"): ENTITY, vol.Optional("event", default=None): vol.Any(None, str)})
RULE = vol.Schema(
    {
        vol.Required("id"): KEY,
        vol.Required("name"): NAME,
        vol.Optional("active", default=True): bool,
        vol.Optional("lights", default=list): [LIGHT],
        vol.Optional("motion", default=list): [ENTITY],
        vol.Optional("buttons", default=list): [BUTTON],
        vol.Optional("manual", default=True): bool,
        vol.Optional("lux", default=None): vol.Any(
            None, vol.Schema({vol.Required("sensor"): ENTITY, vol.Required("below"): vol.Coerce(float)})
        ),
        vol.Optional("manual_after", default=MANUAL_AFTER_SAME): vol.Any(
            MANUAL_AFTER_SAME, MANUAL_AFTER_NEVER, vol.All(vol.Coerce(int), vol.Range(min=1, max=1440))
        ),
        vol.Optional("external_on", default=EXTERNAL_ON_APPLY): vol.In((EXTERNAL_ON_APPLY, EXTERNAL_ON_KEEP)),
        vol.Optional("warn", default=None): vol.Any(None, bool),
        vol.Optional("lock", default=None): vol.Any(None, vol.All(vol.Coerce(int), vol.Range(min=0, max=3600))),
        vol.Optional("rows", default=dict): {KEY: ROW},
        vol.Optional("devices", default=list): [DEVICE],
    },
    extra=vol.REMOVE_EXTRA,
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
        vol.Optional("defaults", default=dict): DEFAULTS,
        vol.Optional("rules", default=list): [RULE],
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
    _unique([r["id"] for r in options["rules"]], "rules")
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
    # Rows and device values for times of day that no longer exist are dropped quietly,
    # so deleting a time of day never makes a rhythm unsavable.
    all_keys = known | {options["base"]["key"]}
    for rule in options["rules"]:
        rule["rows"] = {k: v for k, v in rule["rows"].items() if k in all_keys}
        for device in rule["devices"]:
            device["values"] = {k: v for k, v in device["values"].items() if k in all_keys and v is not None}
        rule["lights"] = list(dict.fromkeys(rule["lights"]))
        rule["motion"] = list(dict.fromkeys(rule["motion"]))
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
_ICONS = {
    "base": "mdi:weather-night",
    "wake": "mdi:weather-sunset-up",
    "morning": "mdi:coffee-outline",
    "midday": "mdi:white-balance-sunny",
    "afternoon": "mdi:weather-partly-cloudy",
    "evening": "mdi:weather-sunset-down",
    "bedtime": "mdi:bed-outline",
    "day": "mdi:white-balance-sunny",
}
# Two palettes: Home Assistant's own interface colors, and deep warm earth tones.
PALETTE_HA = "ha"
PALETTE_EARTH = "earth"
PALETTES = (PALETTE_HA, PALETTE_EARTH)
_COLORS = {
    PALETTE_HA: {
        "base": "#37474f",
        "wake": "#ff9800",
        "morning": "#ffc107",
        "midday": "#03a9f4",
        "afternoon": "#009688",
        "evening": "#e91e63",
        "bedtime": "#673ab7",
        "day": "#ffc107",
    },
    PALETTE_EARTH: {
        "base": "#1f2937",
        "wake": "#c2410c",
        "morning": "#b45309",
        "midday": "#0f766e",
        "afternoon": "#4d7c0f",
        "evening": "#86198f",
        "bedtime": "#3730a3",
        "day": "#b45309",
    },
}

TEMPLATE_DAY = "day"
TEMPLATE_EMPTY = "empty"
TEMPLATES = (TEMPLATE_DAY, TEMPLATE_EMPTY)


def _fixed(clock: str, next_day: bool = False) -> dict[str, Any]:
    return {"kind": "fixed", "time": clock, "next_day": next_day}


def _look(kind: str, palette: str) -> tuple[str, str]:
    colors = _COLORS.get(palette, _COLORS[PALETTE_HA])
    return _ICONS[kind], colors[kind]


def time_of_day_templates(language: str, palette: str = PALETTE_HA) -> list[dict[str, Any]]:
    """Return the templates offered when adding a time of day, in the user's language."""
    names = _NAMES.get(language, _NAMES["en"])
    out = []
    for kind in ("wake", "morning", "midday", "afternoon", "evening", "bedtime"):
        icon, color = _look(kind, palette)
        out.append({"key": make_key(names[kind]), "name": names[kind], "icon": icon, "color": color})
    return out


def default_options(language: str = "en", template: str = TEMPLATE_DAY, palette: str = PALETTE_HA) -> dict[str, Any]:
    """Return the settings of a new rhythm."""
    names = _NAMES.get(language, _NAMES["en"])
    icon, color = _look("base", palette)
    base = {"key": make_key(names["base"]), "name": names["base"], "icon": icon, "color": color}

    def tod(kind: str) -> dict[str, Any]:
        icon, color = _look(kind, palette)
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


def default_rows(options: Mapping[str, Any], brightness: int = 100) -> dict[str, dict[str, Any]]:
    """Return rows for a new rule: on everywhere, off only in the base state."""
    rows = {t["key"]: ROW({"react": REACT_ON, "brightness": brightness}) for t in options["times_of_day"]}
    rows[options["base"]["key"]] = ROW({"react": REACT_OFF_ONLY, "begin": BEGIN_OFF})
    return rows
