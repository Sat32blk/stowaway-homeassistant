"""Select: keep an app awake for a while (or until released)."""
from __future__ import annotations

import time

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import StowawayError
from .const import KEEP_AWAKE_OPTIONS
from .coordinator import StowawayConfigEntry, StowawayCoordinator
from .entity import StowawayAppEntity, add_per_app

PARALLEL_UPDATES = 1


async def async_setup_entry(hass: HomeAssistant, entry: StowawayConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    def make(coordinator: StowawayCoordinator, name: str, item: dict):
        return [KeepAwakeSelect(coordinator, name, "keep_awake")] if item.get("controlled") else []

    add_per_app(entry, async_add_entities, make)


class KeepAwakeSelect(StowawayAppEntity, SelectEntity):
    """Off, or how long to keep the app awake. Picking a time wakes it if it's asleep."""

    _attr_options = list(KEEP_AWAKE_OPTIONS)
    _chosen: str | None = None

    @property
    def current_option(self) -> str | None:
        item = self.item
        if not item:
            return None
        if not item.get("kept_awake"):
            return "off"
        until = item.get("kept_awake_until")
        if not until:
            return "until_released"
        if self._chosen and KEEP_AWAKE_OPTIONS.get(self._chosen):
            return self._chosen
        # Kept awake from somewhere else: show the nearest choice that covers what's left.
        left = (until - time.time()) / 60
        for key, minutes in KEEP_AWAKE_OPTIONS.items():
            if minutes and minutes >= left - 1:
                return key
        return "24_hours"

    @property
    def extra_state_attributes(self) -> dict:
        until = (self.item or {}).get("kept_awake_until")
        return {"until": until} if until else {}

    @callback
    def _handle_coordinator_update(self) -> None:
        if not (self.item or {}).get("kept_awake"):
            self._chosen = None
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        minutes = KEEP_AWAKE_OPTIONS[option]
        client = self.coordinator.client
        try:
            if option == "off":
                item = await client.keep_awake(self.app_name)                 # release
            elif minutes is None:
                item = await client.keep_awake(self.app_name, forever=True)
            else:
                item = await client.keep_awake(self.app_name, minutes)
        except StowawayError as err:
            raise HomeAssistantError(str(err)) from err
        self._chosen = option
        self.coordinator.apply(item)
