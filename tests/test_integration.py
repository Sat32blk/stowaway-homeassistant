"""Tests for the Stowaway integration, with Stowaway's API mocked."""
import time
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stowaway.const import DOMAIN

BASE = "http://192.168.1.2:8880/_stowaway/api/v1"
INFO = {"version": "1.0.0", "apps": 2, "asleep": 1, "awake": 1, "scheduled_restarts": 2,
        "memory_freed_mb": 412, "cpu_freed_percent": 1.2, "cpu_hours_saved_7d": 3.5, "stowaway_memory_mb": 40}


def app(name, state="running", blocked=False, controlled=True, **extra):
    item = {"name": name, "container": name, "controlled": controlled, "state": state,
            "running": state == "running", "summary": f"{state}", "wake_blocked": blocked,
            "sleeps_at": 1790800000.0 if state == "running" else None, "kept_awake": False,
            "in_use": 0, "busy": False, "cpu": 0.3, "memory_mb": 300, "update_available": False,
            "link": f"http://192.168.1.2:1{len(name)}000", "link_port": 18096,
            "idle_timeout": 900, "mode": "idle", "mode_text": "Sleeps after 15 min", "awake_while_busy": True,
            "awake_hours": [], "indicator": "In Use" if state == "running" else "Sleeping",
            "last_open": {"kind": "visit", "who": "laptop", "at": 1790800000.0, "ip": "192.168.1.20",
                          "host": "laptop", "device": "Chrome on Windows"},
            "maintenance": {"schedule": "Sundays at 4:00 AM · with updates", "updates": True,
                            "next_restart": 1790906400.0, "next_restart_text": "Sun 4:00 AM", "running": False,
                            "phase": None, "waiting": None, "last_result": "ok", "last_at": 1790300000.0,
                            "last_message": "Restarted (5s)."}}
    item.update(extra)
    return item


APPS = [app("jellyfin"), app("grafana", "sleeping"),
        {"name": "pihole", "container": "pihole", "controlled": False, "state": "running", "running": True,
         "summary": "Running · restart Oct 31 3:30 AM", "wake_blocked": False, "cpu": 1.5, "memory_mb": 80,
         "mode": "schedule", "mode_text": "Not managed · restarts monthly on the last day at 3:30 AM",
         "maintenance": {"schedule": "Monthly on the last day at 3:30 AM", "updates": False,
                         "next_restart": 1793430600.0, "next_restart_text": "Oct 31 3:30 AM", "running": False,
                         "phase": None, "waiting": None, "last_result": None, "last_at": None, "last_message": None}}]


def mock_api(aioclient_mock, apps=None, status=200):
    aioclient_mock.get(f"{BASE}/info", json=INFO, status=status)
    aioclient_mock.get(f"{BASE}/apps", json={"apps": apps or APPS}, status=status)


async def setup(hass, aioclient_mock, apps=None):
    mock_api(aioclient_mock, apps)
    entry = MockConfigEntry(domain=DOMAIN, unique_id="192.168.1.2:8880",
                            data={"url": "http://192.168.1.2:8880", "token": "stw_test", "verify_ssl": True})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow_success(hass: HomeAssistant, aioclient_mock):
    mock_api(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with patch("custom_components.stowaway.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "192.168.1.2:8880/_stowaway/", "token": " stw_test ", "verify_ssl": True})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"url": "http://192.168.1.2:8880", "token": "stw_test", "verify_ssl": True}
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == "Bearer stw_test"


async def test_config_flow_errors(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(f"{BASE}/info", status=401)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": "192.168.1.2:8880", "token": "stw_bad", "verify_ssl": True})
    assert result["errors"] == {"base": "invalid_auth"}
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/info", exc=TimeoutError())
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": "192.168.1.2:8880", "token": "stw_x", "verify_ssl": True})
    assert result["errors"] == {"base": "cannot_connect"}


async def test_entities(hass: HomeAssistant, aioclient_mock):
    entry = await setup(hass, aioclient_mock)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("switch.jellyfin_awake").state == "on"
    assert hass.states.get("switch.grafana_awake").state == "off"
    assert hass.states.get("select.jellyfin_keep_awake").state == "off"
    assert hass.states.get("sensor.grafana_status").state == "sleeping"
    mode = hass.states.get("sensor.jellyfin_sleep_mode")
    assert mode.state == "Sleeps after 15 min" and mode.attributes["awake_while_busy"] is True
    assert hass.states.get("sensor.jellyfin_cpu").state == "0.3"
    assert hass.states.get("sensor.jellyfin_memory").state == "300"
    assert hass.states.get("sensor.grafana_cpu").state == "0"          # asleep
    woke = hass.states.get("sensor.jellyfin_last_woken_by")
    assert woke.state == "laptop" and woke.attributes["device"] == "Chrome on Windows"
    assert hass.states.get("sensor.stowaway_apps_asleep").state == "1"
    assert hass.states.get("sensor.stowaway_memory_freed").state == "412"
    assert hass.states.get("binary_sensor.jellyfin_update_ready").state == "off"
    # scheduled-only container: status, mode and usage, no controls
    assert hass.states.get("switch.pihole_awake") is None
    assert hass.states.get("select.pihole_keep_awake") is None
    assert hass.states.get("sensor.pihole_status").state == "running"
    assert hass.states.get("sensor.pihole_sleep_mode").state.startswith("Not managed")
    assert hass.states.get("sensor.pihole_cpu").state == "1.5"
    # gone in 1.1
    for gone in ("switch.jellyfin_don_t_wake", "button.jellyfin_keep_awake_1_hour", "button.pihole_restart_now",
                 "sensor.jellyfin_sleeps_at", "sensor.jellyfin_next_restart",
                 "binary_sensor.jellyfin_maintenance_running"):
        assert hass.states.get(gone) is None, gone


async def test_older_stowaway(hass: HomeAssistant, aioclient_mock):
    """Stowaway before 1.6.3 sends no mode or last_open: fall back sensibly."""
    old = app("jellyfin", idle_timeout=0)
    for k in ("mode", "mode_text", "last_open"):
        old.pop(k)
    await setup(hass, aioclient_mock, [old])
    assert hass.states.get("sensor.jellyfin_sleep_mode").state == "Sleeps only when told"
    assert hass.states.get("sensor.jellyfin_last_woken_by").state == "unknown"


async def test_switch_actions(hass: HomeAssistant, aioclient_mock):
    await setup(hass, aioclient_mock)
    aioclient_mock.post(f"{BASE}/apps/jellyfin/sleep", json=app("jellyfin", "stopping"))
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.jellyfin_awake"}, blocking=True)
    assert hass.states.get("switch.jellyfin_awake").state == "off"
    aioclient_mock.post(f"{BASE}/apps/grafana/wake", json=app("grafana", "starting"))
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.grafana_awake"}, blocking=True)
    assert hass.states.get("switch.grafana_awake").state == "on"
    calls = [(c[0], str(c[1]), c[2]) for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert calls[0] == ("POST", f"{BASE}/apps/jellyfin/sleep", {"block": None})


async def test_keep_awake_select(hass: HomeAssistant, aioclient_mock):
    await setup(hass, aioclient_mock)
    until = time.time() + 7200
    aioclient_mock.post(f"{BASE}/apps/grafana/keep-awake",
                        json=app("grafana", "starting", kept_awake=True, kept_awake_until=until))
    await hass.services.async_call("select", "select_option",
                                   {"entity_id": "select.grafana_keep_awake", "option": "2_hours"}, blocking=True)
    assert hass.states.get("select.grafana_keep_awake").state == "2_hours"
    aioclient_mock.clear_requests()
    aioclient_mock.post(f"{BASE}/apps/grafana/keep-awake", json=app("grafana", "running"))
    await hass.services.async_call("select", "select_option",
                                   {"entity_id": "select.grafana_keep_awake", "option": "off"}, blocking=True)
    assert hass.states.get("select.grafana_keep_awake").state == "off"
    aioclient_mock.clear_requests()
    aioclient_mock.post(f"{BASE}/apps/grafana/keep-awake", json=app("grafana", "running", kept_awake=True))
    await hass.services.async_call("select", "select_option",
                                   {"entity_id": "select.grafana_keep_awake", "option": "until_released"}, blocking=True)
    assert hass.states.get("select.grafana_keep_awake").state == "until_released"
    posts = [c[2] for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert posts[-1] == {"minutes": None, "forever": True}


async def test_kept_awake_elsewhere(hass: HomeAssistant, aioclient_mock):
    """Kept awake from Stowaway's own page: the select shows the nearest choice."""
    await setup(hass, aioclient_mock, [app("jellyfin", kept_awake=True, kept_awake_until=time.time() + 50 * 60)])
    assert hass.states.get("select.jellyfin_keep_awake").state == "1_hour"


async def test_services(hass: HomeAssistant, aioclient_mock):
    await setup(hass, aioclient_mock)
    aioclient_mock.post(f"{BASE}/apps/jellyfin/keep-awake", json=app("jellyfin", kept_awake=True))
    aioclient_mock.post(f"{BASE}/apps/grafana/sleep", json=app("grafana", "sleeping", blocked=True))
    await hass.services.async_call(DOMAIN, "keep_awake", {"entity_id": "switch.jellyfin_awake", "minutes": 90}, blocking=True)
    await hass.services.async_call(DOMAIN, "sleep", {"entity_id": "switch.grafana_awake", "block": True}, blocking=True)
    posts = [c for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert posts[0][2] == {"minutes": 90, "forever": False}
    assert posts[1][2] == {"block": True}


async def test_old_entities_removed(hass: HomeAssistant, aioclient_mock):
    """Entities from 1.0 (Don't wake, Restart now, ...) are cleaned out of the registry."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="192.168.1.2:8880",
                            data={"url": "http://192.168.1.2:8880", "token": "stw_test", "verify_ssl": True})
    entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create("switch", DOMAIN, f"{entry.entry_id}_jellyfin_dont_wake", config_entry=entry)
    ent_reg.async_get_or_create("button", DOMAIN, f"{entry.entry_id}_pihole_restart", config_entry=entry)
    mock_api(aioclient_mock)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    left = [e.unique_id for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)]
    assert not any(u.endswith(("_dont_wake", "_restart")) for u in left)
    assert f"{entry.entry_id}_jellyfin_awake" in left


async def test_new_app_appears(hass: HomeAssistant, aioclient_mock):
    entry = await setup(hass, aioclient_mock)
    aioclient_mock.clear_requests()
    mock_api(aioclient_mock, APPS + [app("plex", "sleeping")])
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("switch.plex_awake").state == "off"


async def test_revoked_token_starts_reauth(hass: HomeAssistant, aioclient_mock):
    entry = await setup(hass, aioclient_mock)
    aioclient_mock.clear_requests()
    mock_api(aioclient_mock, status=401)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_removed_app_goes_and_comes_back(hass: HomeAssistant, aioclient_mock):
    entry = await setup(hass, aioclient_mock)
    dev_reg = dr.async_get(hass)
    ident = {(DOMAIN, f"{entry.entry_id}_grafana")}
    assert dev_reg.async_get_device(identifiers=ident)
    aioclient_mock.clear_requests()
    mock_api(aioclient_mock, [a for a in APPS if a["name"] != "grafana"])
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert dev_reg.async_get_device(identifiers=ident) is None
    assert hass.states.get("switch.grafana_awake") is None
    assert hass.states.get("switch.jellyfin_awake").state == "on"
    # added back to Stowaway later
    aioclient_mock.clear_requests()
    mock_api(aioclient_mock)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("switch.grafana_awake").state == "off"


async def test_app_removed_while_ha_was_off(hass: HomeAssistant, aioclient_mock):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="192.168.1.2:8880",
                            data={"url": "http://192.168.1.2:8880", "token": "stw_test", "verify_ssl": True})
    entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, f"{entry.entry_id}_oldapp")})
    mock_api(aioclient_mock)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert dev_reg.async_get_device(identifiers={(DOMAIN, f"{entry.entry_id}_oldapp")}) is None


async def test_scheduled_container_becomes_managed(hass: HomeAssistant, aioclient_mock):
    """A container that only had a restart schedule is now put to sleep: it gets its controls."""
    entry = await setup(hass, aioclient_mock)
    assert hass.states.get("switch.pihole_awake") is None
    aioclient_mock.clear_requests()
    mock_api(aioclient_mock, APPS[:2] + [app("pihole")])
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("switch.pihole_awake").state == "on"


async def test_allow_wake(hass: HomeAssistant, aioclient_mock):
    await setup(hass, aioclient_mock)
    aioclient_mock.post(f"{BASE}/apps/grafana/block", json=app("grafana", "sleeping"))
    await hass.services.async_call(DOMAIN, "allow_wake", {"entity_id": "switch.grafana_awake"}, blocking=True)
    posts = [c for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert str(posts[0][1]).endswith("/grafana/block") and posts[0][2] == {"on": False}
