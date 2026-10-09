"""Switch: wake an app or put it to sleep."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import StowawayError
from .const import AWAKE_STATES
from .coordinator import StowawayConfigEntry, StowawayCoordinator
from .entity import StowawayAppEntity, add_per_app

PARALLEL_UPDATES = 1


async def async_setup_entry(hass: HomeAssistant, entry: StowawayConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    def make(coordinator: StowawayCoordinator, name: str, item: dict):
        if not item.get("controlled"):
            return []
        return [AwakeSwitch(coordinator, name, "awake")]

    add_per_app(entry, async_add_entities, make)


class _Base(StowawayAppEntity, SwitchEntity):
    async def _call(self, coro) -> None:
        try:
            self.coordinator.apply(await coro)
        except StowawayError as err:
            raise HomeAssistantError(str(err)) from err

    # Entity services (registered in __init__.py).
    async def async_keep_awake(self, minutes: int | None = None, forever: bool = False) -> None:
        await self._call(self.coordinator.client.keep_awake(self.app_name, minutes, forever))

    async def async_sleep(self, block: bool | None = None) -> None:
        await self._call(self.coordinator.client.sleep(self.app_name, block))

    async def async_release(self) -> None:
        await self._call(self.coordinator.client.keep_awake(self.app_name))

    async def async_allow_wake(self) -> None:
        """Undo sleep with block: visitors can wake it again (it stays asleep for now)."""
        await self._call(self.coordinator.client.block(self.app_name, False))


class AwakeSwitch(_Base):
    """On: the app is awake (or waking). Turning it off puts it to sleep."""

    @property
    def is_on(self) -> bool | None:
        item = self.item
        return item["state"] in AWAKE_STATES if item else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._call(self.coordinator.client.wake(self.app_name))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._call(self.coordinator.client.sleep(self.app_name))
