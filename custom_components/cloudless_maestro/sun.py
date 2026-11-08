"""Sun times for a rhythm's location, as the schedule needs them."""

from __future__ import annotations

from datetime import date, datetime, tzinfo
from functools import lru_cache

from astral import Observer
from astral import sun as astral_sun

from .schedule import Missing, SunLookup

# The elevation an event refers to: civil twilight for dawn and dusk, the upper edge of the sun otherwise.
THRESHOLD = {"dawn": -6.0, "dusk": -6.0, "sunrise": -0.833, "sunset": -0.833}
RISING = frozenset({"dawn", "sunrise"})


def make_sun(latitude: float, longitude: float, tz: tzinfo) -> SunLookup:
    """Return a lookup for sun events at a location. Results are cached per date."""
    observer = Observer(latitude, longitude)

    @lru_cache(maxsize=512)
    def lookup(event: str, day: date) -> datetime | Missing:
        if event == "noon":
            return astral_sun.noon(observer, day, tzinfo=tz)
        try:
            return getattr(astral_sun, event)(observer, day, tzinfo=tz)
        except ValueError:
            # The event does not happen. If the sun stays above its elevation all day, a rising event already
            # lies behind and a setting one never comes; in polar night it is the other way round.
            noon = astral_sun.noon(observer, day, tzinfo=tz)
            above = astral_sun.elevation(observer, noon) > THRESHOLD[event]
            if above:
                return Missing.EARLY if event in RISING else Missing.LATE
            return Missing.LATE if event in RISING else Missing.EARLY

    return lookup
