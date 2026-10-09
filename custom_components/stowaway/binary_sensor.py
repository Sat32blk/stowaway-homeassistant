"""Binary sensor: a newer version waiting to be installed."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import StowawayConfigEntry, StowawayCoordinator
from .entity import StowawayAppEntity, add_per_app

PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: StowawayConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    def make(coordinator: StowawayCoordinator, name: str, item: dict):
        return [UpdateAvailable(coordinator, name, "update_available")] if item.get("controlled") else []

    add_per_app(entry, async_add_entities, make)


class UpdateAvailable(StowawayAppEntity, BinarySensorEntity):
    """A newer image was found; Stowaway installs it the next time the app wakes."""

    _attr_device_class = BinarySensorDeviceClass.UPDATE

    @property
    def is_on(self) -> bool | None:
        item = self.item
        return bool(item.get("update_available")) if item else None
