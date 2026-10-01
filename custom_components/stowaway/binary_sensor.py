"""Binary sensors: maintenance running, and a newer version waiting to be installed."""
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
        ents = [MaintenanceRunning(coordinator, name, "maintenance_running")]
        if item.get("controlled"):
            ents.append(UpdateAvailable(coordinator, name, "update_available"))
        return ents

    add_per_app(entry, async_add_entities, make)


class MaintenanceRunning(StowawayAppEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self) -> bool | None:
        m = (self.item or {}).get("maintenance") or {}
        return bool(m.get("running"))

    @property
    def extra_state_attributes(self) -> dict:
        m = (self.item or {}).get("maintenance") or {}
        return {k: v for k, v in {"phase": m.get("phase"), "waiting": m.get("waiting")}.items() if v}


class UpdateAvailable(StowawayAppEntity, BinarySensorEntity):
    """A newer image was found; Stowaway installs it the next time the app wakes."""

    _attr_device_class = BinarySensorDeviceClass.UPDATE

    @property
    def is_on(self) -> bool | None:
        item = self.item
        return bool(item.get("update_available")) if item else None
