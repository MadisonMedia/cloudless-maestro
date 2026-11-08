"""Serve the card and the settings page."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.start import async_at_started

from .const import PANEL_URL, URL_STATIC

_LOGGER = logging.getLogger(__name__)

FILES = Path(__file__).parent / "frontend"
CARD_FILE = "maestro-card.js"
PANEL_FILE = "maestro-panel.js"


def _versions() -> dict[str, str]:
    """Return a short hash per file, so browsers pick up a new version at once."""
    result = {}
    for path in FILES.glob("*.js"):
        result[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()[:10]
    return result


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register the static files, the card and the sidebar page."""
    await hass.http.async_register_static_paths([StaticPathConfig(URL_STATIC, str(FILES), cache_headers=True)])
    versions = await hass.async_add_executor_job(_versions)
    shared = versions.get("maestro-shared.js", "0")
    card_url = f"{URL_STATIC}/{CARD_FILE}?v={versions.get(CARD_FILE, '0')}{shared}"
    panel_url = f"{URL_STATIC}/{PANEL_FILE}?v={versions.get(PANEL_FILE, '0')}{shared}"

    # The extra module makes the card available everywhere. The dashboard resource makes
    # sure it is ready before a dashboard renders, also in companion apps.
    frontend.add_extra_js_url(hass, card_url)

    @callback
    def _register_resource(_hass: HomeAssistant) -> None:
        hass.async_create_task(_async_register_resource(hass, card_url))

    async_at_started(hass, _register_resource)

    if PANEL_URL not in hass.data.get(frontend.DATA_PANELS, {}):
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_URL,
            webcomponent_name="maestro-panel",
            sidebar_title="Maestro",
            sidebar_icon="mdi:timeline-clock-outline",
            module_url=panel_url,
            require_admin=True,
        )


async def _async_register_resource(hass: HomeAssistant, url: str) -> None:
    """Add or update the card in the dashboard resources, for dashboards in storage mode."""
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
    except ImportError:
        return
    data = hass.data.get(LOVELACE_DATA)
    if data is None or data.resource_mode != MODE_STORAGE:
        return
    resources = data.resources
    try:
        if not getattr(resources, "loaded", True):
            await resources.async_load()
            resources.loaded = True
        base = url.split("?", 1)[0]
        for item in resources.async_items():
            if str(item.get("url", "")).split("?", 1)[0] == base:
                if item["url"] != url:
                    await resources.async_update_item(item["id"], {"res_type": "module", "url": url})
                return
        await resources.async_create_item({"res_type": "module", "url": url})
    except Exception:
        _LOGGER.warning("Could not add the Maestro card to the dashboard resources", exc_info=True)
