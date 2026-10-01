"""Base entities: one device for Stowaway itself, and one per app."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import StowawayConfigEntry, StowawayCoordinator


def hub_device(coordinator: StowawayCoordinator) -> DeviceInfo:
    entry = coordinator.config_entry
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Stowaway",
        manufacturer=MANUFACTURER,
        model="Stowaway",
        sw_version=(coordinator.data.info.get("version") if coordinator.data else None),
        configuration_url=f"{coordinator.client.base}/_stowaway",
    )


class StowawayHubEntity(CoordinatorEntity[StowawayCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: StowawayCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = hub_device(coordinator)


class StowawayAppEntity(CoordinatorEntity[StowawayCoordinator]):
    """An entity belonging to one app (or scheduled container)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: StowawayCoordinator, name: str, key: str) -> None:
        super().__init__(coordinator)
        self.app_name = name
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{name}_{key}"
        self._attr_translation_key = key
        item = self.item or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{name}")},
            name=name,
            manufacturer=MANUFACTURER,
            model="App put to sleep by Stowaway" if item.get("controlled") else "Container restarted by Stowaway",
            via_device=(DOMAIN, entry_id),
            configuration_url=item.get("link") or f"{coordinator.client.base}/_stowaway",
        )

    @property
    def item(self) -> dict | None:
        data = self.coordinator.data
        return data.apps.get(self.app_name) if data else None

    @property
    def available(self) -> bool:
        return super().available and self.item is not None


def add_per_app(
    entry: StowawayConfigEntry,
    async_add_entities: AddEntitiesCallback,
    make: Callable[[StowawayCoordinator, str, dict], list[Entity]],
) -> None:
    """Create entities for every app now, and for apps added to Stowaway later."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    def add_new() -> None:
        new = []
        for name, item in (coordinator.data.apps if coordinator.data else {}).items():
            if name not in known:
                known.add(name)
                new.extend(make(coordinator, name, item))
        if new:
            async_add_entities(new)

    add_new()
    entry.async_on_unload(coordinator.async_add_listener(add_new))
