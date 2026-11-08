"""Config flow: one config entry per rhythm."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
import voluptuous as vol

from .const import CONF_TEMPLATE, DOMAIN, PANEL_URL
from .model import TEMPLATE_DAY, TEMPLATES, default_options


class MaestroConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create a rhythm. Its times of day and models are set up on the Maestro page."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Name the rhythm and choose how it starts."""
        if user_input is not None:
            language = (self.hass.config.language or "en").split("-")[0]
            return self.async_create_entry(
                title=user_input[CONF_NAME].strip(),
                data={},
                options=default_options(language, user_input.get(CONF_TEMPLATE, TEMPLATE_DAY)),
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): selector.TextSelector(),
                    vol.Required(CONF_TEMPLATE, default=TEMPLATE_DAY): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=list(TEMPLATES), translation_key=CONF_TEMPLATE)
                    ),
                }
            ),
            description_placeholders={"panel": f"/{PANEL_URL}"},
        )
