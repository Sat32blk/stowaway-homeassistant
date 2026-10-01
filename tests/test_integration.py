"""Tests for the Stowaway integration, with Stowaway's API mocked."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
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
            "maintenance": {"schedule": "Sundays at 4:00 AM · with updates", "updates": True,
                            "next_restart": 1790906400.0, "next_restart_text": "Sun 4:00 AM", "running": False,
                            "phase": None, "waiting": None, "last_result": "ok", "last_at": 1790300000.0,
                            "last_message": "Restarted (5s)."}}
    item.update(extra)
    return item


APPS = [app("jellyfin"), app("grafana", "sleeping"),
        {"name": "pihole", "container": "pihole", "controlled": False, "state": "running", "running": True,
         "summary": "Running · restart Oct 31 3:30 AM", "wake_blocked": False,
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
    assert hass.states.get("switch.jellyfin_don_t_wake").state == "off"
    st = hass.states.get("sensor.grafana_status")
    assert st.state == "sleeping" and st.attributes["restart_schedule"].startswith("Sundays")
    assert hass.states.get("sensor.jellyfin_next_restart").state.startswith("2026-")
    assert hass.states.get("sensor.jellyfin_sleeps_at").state.startswith("2026-")
    assert hass.states.get("sensor.stowaway_apps_asleep").state == "1"
    assert hass.states.get("sensor.stowaway_memory_freed").state == "412"
    assert hass.states.get("binary_sensor.jellyfin_maintenance_running").state == "off"
    assert hass.states.get("button.pihole_restart_now") is not None
    # scheduled-only container: no awake switch
    assert hass.states.get("switch.pihole_awake") is None
    assert hass.states.get("sensor.pihole_status").state == "running"


async def test_switch_actions(hass: HomeAssistant, aioclient_mock):
    await setup(hass, aioclient_mock)
    aioclient_mock.post(f"{BASE}/apps/jellyfin/sleep", json=app("jellyfin", "stopping"))
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.jellyfin_awake"}, blocking=True)
    assert hass.states.get("switch.jellyfin_awake").state == "off"
    aioclient_mock.post(f"{BASE}/apps/grafana/block", json=app("grafana", "sleeping", blocked=True))
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.grafana_don_t_wake"}, blocking=True)
    assert hass.states.get("switch.grafana_don_t_wake").state == "on"
    aioclient_mock.post(f"{BASE}/apps/grafana/wake", json=app("grafana", "starting"))
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.grafana_awake"}, blocking=True)
    assert hass.states.get("switch.grafana_awake").state == "on"
    calls = [(c[0], str(c[1]), c[2]) for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert calls[0] == ("POST", f"{BASE}/apps/jellyfin/sleep", {"block": None})
    assert calls[1][2] == {"on": True}


async def test_services(hass: HomeAssistant, aioclient_mock):
    await setup(hass, aioclient_mock)
    aioclient_mock.post(f"{BASE}/apps/jellyfin/keep-awake", json=app("jellyfin", kept_awake=True))
    aioclient_mock.post(f"{BASE}/apps/grafana/sleep", json=app("grafana", "sleeping", blocked=True))
    await hass.services.async_call(DOMAIN, "keep_awake", {"entity_id": "switch.jellyfin_awake", "minutes": 90}, blocking=True)
    await hass.services.async_call(DOMAIN, "sleep", {"entity_id": "switch.grafana_awake", "block": True}, blocking=True)
    posts = [c for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert posts[0][2] == {"minutes": 90, "forever": False}
    assert posts[1][2] == {"block": True}
    assert hass.states.get("switch.grafana_don_t_wake").state == "on"


async def test_restart_button(hass: HomeAssistant, aioclient_mock):
    await setup(hass, aioclient_mock)
    aioclient_mock.post(f"{BASE}/apps/pihole/restart", json={"queued": True, "container": "pihole"}, status=202)
    await hass.services.async_call("button", "press", {"entity_id": "button.pihole_restart_now"}, blocking=True)
    assert any(c[0] == "POST" and str(c[1]).endswith("/pihole/restart") for c in aioclient_mock.mock_calls)


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
