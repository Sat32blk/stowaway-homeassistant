"""Stowaway: see and control apps that Stowaway puts to sleep and wakes on demand."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import service
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import StowawayClient
from .const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL, DOMAIN, REMOVED_KEYS
from .coordinator import StowawayConfigEntry, StowawayCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]
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
    service.async_register_platform_entity_service(
        hass, DOMAIN, "allow_wake", entity_domain=SWITCH_DOMAIN, func="async_allow_wake", schema=None)
    return True


def _remove_old_entities(hass: HomeAssistant, entry: StowawayConfigEntry) -> None:
    """Drop entities that earlier versions made and this one doesn't (Don't wake, Restart now, ...)."""
    ent_reg = er.async_get(hass)
    for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if any(ent.unique_id.endswith(f"_{key}") for key in REMOVED_KEYS):
            ent_reg.async_remove(ent.entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: StowawayConfigEntry) -> bool:
    session = async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True))
    client = StowawayClient(session, entry.data[CONF_URL], entry.data[CONF_TOKEN])
    coordinator = StowawayCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    _remove_old_entities(hass, entry)
    # Apps removed from Stowaway while Home Assistant was off.
    coordinator.remove_missing_devices(set(coordinator.data.apps))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: StowawayConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(hass: HomeAssistant, entry: StowawayConfigEntry,
                                           device: dr.DeviceEntry) -> bool:
    """Let an app's device be deleted by hand once Stowaway no longer has the app."""
    coordinator: StowawayCoordinator = entry.runtime_data
    for domain, ident in device.identifiers:
        if domain != DOMAIN:
            continue
        if ident == entry.entry_id:
            return False                    # Stowaway itself
        name = ident.removeprefix(f"{entry.entry_id}_")
        if coordinator.data and name in coordinator.data.apps:
            return False
    return True
