"""Buttons: restart now, and keep awake for an hour."""
from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import StowawayError
from .coordinator import StowawayConfigEntry, StowawayCoordinator
from .entity import StowawayAppEntity, add_per_app

PARALLEL_UPDATES = 1


async def async_setup_entry(hass: HomeAssistant, entry: StowawayConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    def make(coordinator: StowawayCoordinator, name: str, item: dict):
        ents = [RestartButton(coordinator, name, "restart")]
        if item.get("controlled"):
            ents.append(KeepAwakeHourButton(coordinator, name, "keep_awake_hour"))
        return ents

    add_per_app(entry, async_add_entities, make)


class RestartButton(StowawayAppEntity, ButtonEntity):
    """Run the container's maintenance now (restart, and update if its schedule says so)."""

    _attr_device_class = ButtonDeviceClass.RESTART

    async def async_press(self) -> None:
        try:
            await self.coordinator.client.restart(self.app_name)
        except StowawayError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()


class KeepAwakeHourButton(StowawayAppEntity, ButtonEntity):
    async def async_press(self) -> None:
        try:
            self.coordinator.apply(await self.coordinator.client.keep_awake(self.app_name, 60))
        except StowawayError as err:
            raise HomeAssistantError(str(err)) from err
