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
