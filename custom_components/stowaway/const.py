"""Constants for the Stowaway integration."""
from datetime import timedelta

DOMAIN = "stowaway"
MANUFACTURER = "Stowaway"

CONF_URL = "url"
CONF_TOKEN = "token"
CONF_VERIFY_SSL = "verify_ssl"

SCAN_INTERVAL = timedelta(seconds=15)

# States an app can be in (sensor options). "stopped" is for containers that
# Stowaway only restarts on a schedule.
STATES = ["running", "sleeping", "starting", "stopping", "updating", "maintenance", "failed", "stopped"]
AWAKE_STATES = ("running", "starting", "updating", "maintenance")

# Keep-awake choices for the select entity, in minutes ("off" releases, None = until released).
KEEP_AWAKE_OPTIONS: dict[str, float | None] = {
    "off": 0, "30_minutes": 30, "1_hour": 60, "2_hours": 120, "4_hours": 240,
    "8_hours": 480, "24_hours": 1440, "until_released": None,
}

# Entities earlier versions created that are gone now; removed from the entity registry on setup.
REMOVED_KEYS = ("dont_wake", "restart", "keep_awake_hour", "maintenance_running", "next_restart", "sleeps_at")
