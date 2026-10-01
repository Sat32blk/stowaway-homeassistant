"""Set up Stowaway from the UI: its address and an API token."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnect, InvalidAuth, StowawayClient, StowawayError, normalize_url
from .const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema({
    vol.Required(CONF_URL): str,
    vol.Required(CONF_TOKEN): str,
    vol.Optional(CONF_VERIFY_SSL, default=True): bool,
})


class StowawayConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _check(self, url: str, token: str, verify_ssl: bool) -> tuple[dict, dict]:
        errors: dict[str, str] = {}
        info: dict = {}
        client = StowawayClient(async_get_clientsession(self.hass, verify_ssl=verify_ssl), url, token)
        try:
            info = await client.info()
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except StowawayError:
            _LOGGER.exception("unexpected answer from Stowaway")
            errors["base"] = "unknown"
        return info, errors

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            await self.async_set_unique_id(url.split("://", 1)[1].lower())
            self._abort_if_unique_id_configured()
            _, errors = await self._check(url, user_input[CONF_TOKEN].strip(), user_input[CONF_VERIFY_SSL])
            if not errors:
                return self.async_create_entry(
                    title="Stowaway",
                    data={CONF_URL: url, CONF_TOKEN: user_input[CONF_TOKEN].strip(),
                          CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL]})
        return self.async_show_form(
            step_id="user", data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input or {}),
            errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            _, errors = await self._check(entry.data[CONF_URL], token, entry.data.get(CONF_VERIFY_SSL, True))
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: token})
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors, description_placeholders={"url": entry.data[CONF_URL]})
