"""Keeps the state of every Stowaway app up to date, and the app list in step with Stowaway."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import InvalidAuth, StowawayClient, StowawayError
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class StowawayData:
    info: dict
    apps: dict[str, dict]


type StowawayConfigEntry = ConfigEntry[StowawayCoordinator]


class StowawayCoordinator(DataUpdateCoordinator[StowawayData]):
    config_entry: StowawayConfigEntry

    def __init__(self, hass: HomeAssistant, entry: StowawayConfigEntry, client: StowawayClient) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.client = client

    async def _async_update_data(self) -> StowawayData:
        try:
            info = await self.client.info()
            apps = await self.client.apps()
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except StowawayError as err:
            raise UpdateFailed(str(err)) from err
        new = StowawayData(info=info, apps={a["name"]: a for a in apps})
        if self.data is not None:
            self._follow_changes(self.data.apps, new.apps)
        return new

    def _follow_changes(self, old: dict[str, dict], new: dict[str, dict]) -> None:
        """Apps added to Stowaway get entities from the platforms' listeners. Here: apps
        removed from Stowaway lose their device, and an app that changed kind (e.g. a
        scheduled-only container Stowaway now puts to sleep) gets its entities rebuilt."""
        gone = set(old) - set(new)
        if gone:
            _LOGGER.info("Removing apps no longer in Stowaway: %s", ", ".join(sorted(gone)))
            self.remove_missing_devices(set(new))
        changed = [n for n in set(old) & set(new)
                   if bool(old[n].get("controlled")) != bool(new[n].get("controlled"))]
        if changed:
            _LOGGER.info("Rebuilding entities for %s (changed in Stowaway)", ", ".join(sorted(changed)))
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

    def remove_missing_devices(self, present: set[str]) -> None:
        """Remove the device (and its entities) of every app Stowaway no longer has."""
        entry_id = self.config_entry.entry_id
        dev_reg = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(dev_reg, entry_id):
            for domain, ident in device.identifiers:
                if domain == DOMAIN and ident.startswith(f"{entry_id}_") \
                        and ident.removeprefix(f"{entry_id}_") not in present:
                    dev_reg.async_update_device(device.id, remove_config_entry_id=entry_id)
                    break

    def apply(self, item: dict) -> None:
        """Use the state an action returned right away, instead of waiting for the next poll."""
        if self.data and item and "name" in item:
            self.data.apps[item["name"]] = item
            self.async_set_updated_data(self.data)
