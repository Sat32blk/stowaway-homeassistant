"""Sensors: each app's state, sleep mode, CPU and memory, and what last woke it; plus
Stowaway's own totals."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import STATES
from .coordinator import StowawayConfigEntry, StowawayCoordinator
from .entity import StowawayAppEntity, StowawayHubEntity, add_per_app

PARALLEL_UPDATES = 0


def _ts(value) -> datetime | None:
    return dt_util.utc_from_timestamp(value) if isinstance(value, (int, float)) else None


def _mins(sec: float) -> str:
    m = max(1, round(sec / 60))
    if m < 60:
        return f"{m} min"
    h, r = divmod(m, 60)
    return f"{h} h {r} min" if r else f"{h} h"


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v not in (None, [], "")}


async def async_setup_entry(hass: HomeAssistant, entry: StowawayConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities([AppsAsleepSensor(coordinator, "apps_asleep"),
                        MemoryFreedSensor(coordinator, "memory_freed")])

    def make(coordinator: StowawayCoordinator, name: str, item: dict):
        ents = [StatusSensor(coordinator, name, "status"), SleepModeSensor(coordinator, name, "sleep_mode"),
                CpuSensor(coordinator, name, "cpu"), MemorySensor(coordinator, name, "memory")]
        if item.get("controlled"):
            ents.append(LastWokenBySensor(coordinator, name, "last_woken_by"))
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
        return _clean({
            "label": item.get("indicator"),          # "In Use", "Sleeping in 8 min", ... as on dashboards
            "summary": item.get("summary"),
            "in_use": item.get("in_use"),
            "busy": item.get("busy"),
            "link": item.get("link"),
        })


class SleepModeSensor(StowawayAppEntity, SensorEntity):
    """How Stowaway puts the app to sleep, as in the Sleep column of Stowaway's app list."""

    @property
    def native_value(self) -> str | None:
        item = self.item
        if not item:
            return None
        if item.get("mode_text"):
            return item["mode_text"]
        # Stowaway older than 1.6.3
        if not item.get("controlled"):
            return "Not managed"
        t = item.get("idle_timeout") or 0
        return f"Sleeps after {_mins(t)}" if t > 0 else "Sleeps only when told"

    @property
    def extra_state_attributes(self) -> dict:
        item = self.item or {}
        m = item.get("maintenance") or {}
        return _clean({
            "mode": item.get("mode"),
            "awake_while_busy": item.get("awake_while_busy"),
            "awake_hours": item.get("awake_hours"),
            "kept_awake_until": "released" if item.get("kept_awake") and not item.get("kept_awake_until")
                                else _ts(item.get("kept_awake_until")) if item.get("kept_awake") else None,
            "wont_wake_when_opened": True if item.get("wake_blocked") else None,
            "restart_schedule": m.get("schedule"),
        })


class _UsageSensor(StowawayAppEntity, SensorEntity):
    """0 while the app is asleep or stopped, so history shows what sleeping saves."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _field = ""

    @property
    def native_value(self) -> float | None:
        item = self.item
        if not item:
            return None
        if item.get("state") not in ("running", "stopping"):
            return 0
        return item.get(self._field)


class CpuSensor(_UsageSensor):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 1
    _field = "cpu"


class MemorySensor(_UsageSensor):
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.MEGABYTES
    _attr_suggested_display_precision = 0
    _field = "memory_mb"


class LastWokenBySensor(StowawayAppEntity, SensorEntity):
    """What last opened or woke the app: a device on your network, Home Assistant,
    an API token, its awake hours, or Stowaway's own Wake / Keep awake."""

    @property
    def native_value(self) -> str | None:
        o = (self.item or {}).get("last_open")
        return o.get("who") if o else None

    @property
    def extra_state_attributes(self) -> dict:
        o = (self.item or {}).get("last_open") or {}
        return _clean({"kind": o.get("kind"), "when": _ts(o.get("at")), "device": o.get("device"),
                       "host": o.get("host"), "ip": o.get("ip"), "detail": o.get("detail")})


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
