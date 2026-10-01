# Stowaway for Home Assistant

[![Validate](https://github.com/Sat32blk/Stowaway-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/Sat32blk/Stowaway-homeassistant/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-support-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/sat32blk)

See and control the apps that [Stowaway](https://github.com/Sat32blk/Stowaway) puts to sleep and wakes on demand, and the containers it restarts on a schedule.

## What you get

For each app Stowaway puts to sleep:

| Entity | What it does |
|---|---|
| `switch.<app>_awake` | On while the app is awake. Turn off to put it to sleep now, on to wake it. |
| `switch.<app>_don_t_wake` | On: visitors can't wake the app; they see "switched off". Turn off to allow waking again. |
| `sensor.<app>_status` | Awake, Asleep, Starting, Going to sleep, Updating, Maintenance or Failed to start. Attributes include a one-line summary, CPU and memory. |
| `sensor.<app>_sleeps_at` | When an idle app will be put to sleep. |
| `sensor.<app>_next_restart` | Next scheduled restart, if it has one. |
| `binary_sensor.<app>_maintenance_running` | On while a scheduled restart/update is in progress. |
| `binary_sensor.<app>_update_ready` | A newer version was found; it installs the next time the app wakes. |
| `button.<app>_restart_now` | Run its maintenance now (restart, and update if its schedule includes updates). |
| `button.<app>_keep_awake_1_hour` | Keep it awake for an hour. |

Containers that Stowaway only restarts on a schedule get the status, next restart, maintenance running and restart now entities.

Stowaway itself gets `sensor.stowaway_apps_asleep` and `sensor.stowaway_memory_freed`.

Actions (on an app's `awake` switch):
- `stowaway.keep_awake` with `minutes`, or `forever: true`
- `stowaway.release` ends a keep-awake
- `stowaway.sleep` with `block: true` to also switch waking off

## Install

1. In HACS: **⋮ → Custom repositories**, add `https://github.com/Sat32blk/Stowaway-homeassistant` as an **Integration**, then install **Stowaway** and restart Home Assistant.
   Without HACS, copy `custom_components/stowaway` into your Home Assistant `config/custom_components/` folder.
2. In the Stowaway dashboard: **Integrations → Home Assistant → Create token**. Copy it.
3. In Home Assistant: **Settings → Devices & services → Add integration → Stowaway**. Enter Stowaway's address (e.g. `192.168.1.2:8880`) and the token.

Home Assistant must be on your home network, unless you allowed the Stowaway dashboard from outside. If the token is revoked, Home Assistant asks for a new one.

Needs Stowaway 1.0.0 or newer and Home Assistant 2025.1 or newer.

## Examples

**Switch media servers off while nobody's home, back on when someone arrives**

```yaml
automation:
  - alias: Media servers off while away
    triggers:
      - trigger: numeric_state
        entity_id: zone.home
        below: 1
        for: "00:15:00"
    actions:
      - action: stowaway.sleep
        target:
          entity_id: [switch.plex_awake, switch.jellyfin_awake]
        data:
          block: true          # leave this out to let remote streaming still wake them

  - alias: Media servers back when home
    triggers:
      - trigger: numeric_state
        entity_id: zone.home
        above: 0
    actions:
      - action: switch.turn_off
        target:
          entity_id: [switch.plex_don_t_wake, switch.jellyfin_don_t_wake]
      - action: switch.turn_on          # optional: have Plex ready before you sit down
        target:
          entity_id: switch.plex_awake
```

**Keep Jellyfin awake during movie night**

```yaml
- action: stowaway.keep_awake
  target:
    entity_id: switch.jellyfin_awake
  data:
    minutes: 240
```

## Development

```bash
pip install pytest-homeassistant-custom-component
pytest
```

## Support

If Stowaway saves you some resources (or some hassle), you can [buy me a coffee](https://buymeacoffee.com/sat32blk). Thank you!

## License

MIT. See [LICENSE](LICENSE).
