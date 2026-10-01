"""Keeps the state of every Stowaway app up to date."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
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
        return StowawayData(info=info, apps={a["name"]: a for a in apps})

    def apply(self, item: dict) -> None:
        """Use the state an action returned right away, instead of waiting for the next poll."""
        if self.data and item and "name" in item:
            self.data.apps[item["name"]] = item
            self.async_set_updated_data(self.data)
