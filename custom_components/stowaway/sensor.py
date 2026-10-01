"""Sensors: each app's state, when it goes to sleep, and its next scheduled restart."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import STATES
from .coordinator import StowawayConfigEntry, StowawayCoordinator
from .entity import StowawayAppEntity, StowawayHubEntity, add_per_app

PARALLEL_UPDATES = 0


def _ts(value) -> datetime | None:
    return dt_util.utc_from_timestamp(value) if isinstance(value, (int, float)) else None


async def async_setup_entry(hass: HomeAssistant, entry: StowawayConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities([AppsAsleepSensor(coordinator, "apps_asleep"),
                        MemoryFreedSensor(coordinator, "memory_freed")])

    def make(coordinator: StowawayCoordinator, name: str, item: dict):
        ents = [StatusSensor(coordinator, name, "status"), NextRestartSensor(coordinator, name, "next_restart")]
        if item.get("controlled"):
            ents.append(SleepsAtSensor(coordinator, name, "sleeps_at"))
        return ents

    add_per_app(entry, async_add_entities, make)


class StatusSensor(StowawayAppEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATES

    @property
    def native_value(self) -> str | None:
        item = self.item
        return item["state"] if item and item["state"] in STATES else None

    @property
    def extra_state_attributes(self) -> dict:
        item = self.item or {}
        m = item.get("maintenance") or {}
        attrs = {
            "summary": item.get("summary"),
            "wake_blocked": item.get("wake_blocked"),
            "kept_awake": item.get("kept_awake"),
            "in_use": item.get("in_use"),
            "busy": item.get("busy"),
            "cpu_percent": item.get("cpu"),
            "memory_mb": item.get("memory_mb"),
            "link": item.get("link"),
            "restart_schedule": m.get("schedule"),
            "last_restart_result": m.get("last_result"),
        }
        return {k: v for k, v in attrs.items() if v is not None}


class SleepsAtSensor(StowawayAppEntity, SensorEntity):
    """When an idle app will be put to sleep (empty while in use, kept awake or asleep)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        item = self.item or {}
        return _ts(item.get("sleeps_at"))


class NextRestartSensor(StowawayAppEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        m = (self.item or {}).get("maintenance") or {}
        return _ts(m.get("next_restart"))

    @property
    def extra_state_attributes(self) -> dict:
        m = (self.item or {}).get("maintenance") or {}
        attrs = {"schedule": m.get("schedule"), "with_updates": m.get("updates"),
                 "last_result": m.get("last_result"), "last_message": m.get("last_message"),
                 "last_run": _ts(m.get("last_at")), "waiting": m.get("waiting")}
        return {k: v for k, v in attrs.items() if v is not None}


class AppsAsleepSensor(StowawayHubEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.info.get("asleep") if self.coordinator.data else None

    @property
    def extra_state_attributes(self) -> dict:
        info = self.coordinator.data.info if self.coordinator.data else {}
        return {"apps": info.get("apps"), "awake": info.get("awake"),
                "scheduled_restarts": info.get("scheduled_restarts")}


class MemoryFreedSensor(StowawayHubEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.MEGABYTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.info.get("memory_freed_mb") if self.coordinator.data else None
