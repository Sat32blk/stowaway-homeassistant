"""Stowaway: see and control apps that Stowaway puts to sleep and wakes on demand."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import StowawayClient
from .const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL, DOMAIN
from .coordinator import StowawayConfigEntry, StowawayCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Actions that target an app's switch, e.g. stowaway.keep_awake on switch.jellyfin_awake."""
    service.async_register_platform_entity_service(
        hass, DOMAIN, "keep_awake", entity_domain=SWITCH_DOMAIN, func="async_keep_awake",
        schema={vol.Optional("minutes"): vol.All(vol.Coerce(int), vol.Range(min=1, max=43200)),
                vol.Optional("forever", default=False): cv.boolean})
    service.async_register_platform_entity_service(
        hass, DOMAIN, "release", entity_domain=SWITCH_DOMAIN, func="async_release", schema=None)
    service.async_register_platform_entity_service(
        hass, DOMAIN, "sleep", entity_domain=SWITCH_DOMAIN, func="async_sleep",
        schema={vol.Optional("block"): cv.boolean})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: StowawayConfigEntry) -> bool:
    session = async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True))
    client = StowawayClient(session, entry.data[CONF_URL], entry.data[CONF_TOKEN])
    coordinator = StowawayCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: StowawayConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
