"""Constants for Cloudless Maestro."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "cloudless_maestro"
NAME: Final = "Cloudless Maestro"

PANEL_URL: Final = "cloudless-maestro"
URL_STATIC: Final = "/cloudless_maestro_static"

STORAGE_VERSION: Final = 1
LOG_SIZE: Final = 200
ADJUSTMENT_KEEP_DAYS: Final = 7

CALENDAR_DAYS_BACK: Final = 1
CALENDAR_DAYS_AHEAD: Final = 42
CALENDAR_REFRESH_MINUTES: Final = 30

EVENT_CHANGED: Final = f"{DOMAIN}_changed"

REASON_PLAN: Final = "plan"
REASON_PIN: Final = "pin"
REASON_RESUME: Final = "resume"
REASON_ADJUSTMENT: Final = "adjustment"
REASON_CALENDAR: Final = "calendar"
REASON_CONFIG: Final = "config"
REASON_RESTART: Final = "restart"

CONF_TEMPLATE: Final = "template"

ATTR_TIME_OF_DAY: Final = "time_of_day"
ATTR_UNTIL: Final = "until"
ATTR_DURATION: Final = "duration"
ATTR_TIME: Final = "time"
ATTR_DATE: Final = "date"
ATTR_MODEL: Final = "model"
ATTR_TIMES: Final = "times"
ATTR_END: Final = "end"

SERVICE_PIN: Final = "pin"
SERVICE_RESUME: Final = "resume"
SERVICE_ADJUST_DAY: Final = "adjust_day"
SERVICE_CLEAR_DAY: Final = "clear_day"
SERVICE_REFRESH_CALENDARS: Final = "refresh_calendars"
