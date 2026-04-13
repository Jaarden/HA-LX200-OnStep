# LX200 Telescope — Home Assistant Integration

> [!WARNING]  
> This is in development, use at your own risk. The code can change anytime and break things!

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/Jaarden/HA-LX200-OnStep)](https://github.com/Jaarden/HA-LX200-OnStep/releases)
[![License](https://img.shields.io/github/license/Jaarden/HA-LX200-OnStep)](LICENSE)

A Home Assistant custom integration that connects to an LX200-compatible telescope mount over TCP. It exposes live coordinate sensors, a connectivity health check, and full mount controls — all as native HA entities with no MQTT broker required.

**Author:** Justin Aarden  
**Repository:** [Jaarden/HA-LX200-OnStep](https://github.com/Jaarden/HA-LX200-OnStep)

---

## Features

- Live **RA, DEC, Altitude, Azimuth** and **Local Sidereal Time** sensors
- **Connectivity** binary sensor — shows Online / Offline when the mount is unreachable
- **Directional motion** buttons — Move North / South / East / West and Stop
- **Slew rate** selector — Guide, Center, Find, Slew
- **Tracking** switch — enable or disable mount tracking
- **Park / Unpark** switch — park the mount or resume from park
- **Go to Home** button — slew to the home (Counterweight Down) position, then automatically unparks
- **Set Home** button — save the current position as the home reference, then automatically unparks
- **Set Park Position** button — save the current position as the park position
- Configurable poll interval (default 10 s)
- No MQTT broker required — talks directly to the mount over TCP
- Full UI setup via Settings → Integrations (no `configuration.yaml` edits)
- Compatible with any LX200-protocol mount: **OnStep**, **iOptron**, **Celestron**, **SkyWatcher**, **Meade**, and others

---

## Requirements

| Requirement | Details |
|---|---|
| Home Assistant | 2023.1.0 or newer |
| Mount firmware | LX200 protocol over TCP |
| Network access | HA must be able to reach the mount's IP and TCP port |

The integration communicates with the mount's built-in TCP server (e.g. OnStep's WiFi interface) or a serial-to-TCP bridge such as `ser2net`. No extra Python packages are required.

---

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant.
2. Go to **Integrations** → click the three-dot menu → **Custom repositories**.
3. Add `https://github.com/Jaarden/HA-LX200-OnStep` with category **Integration**.
4. Search for **LX200 Telescope** and click **Download**.
5. Restart Home Assistant.

### Manual

1. Download or clone this repository.
2. Copy the `custom_components/telescope_lx200/` folder into your HA config directory:
   ```
   config/
   └── custom_components/
       └── telescope_lx200/
   ```
3. Restart Home Assistant.

---

## Configuration

1. Go to **Settings → Integrations → Add Integration**.
2. Search for **LX200 Telescope**.
3. Fill in the connection details:

| Field | Description | Default |
|---|---|---|
| Host / IP address | IP address of the mount or TCP bridge | — |
| TCP port | Port the mount listens on (see table below) | `9999` |
| Poll interval | How often to query the mount, in seconds | `10` |

4. Click **Submit** — the integration validates the connection before saving.

### Common TCP ports

| Mount / Software | Port |
|---|---|
| OnStep (WiFi) | `4031` |
| iOptron mounts | `8899` |
| ser2net / socat bridge | user-defined |
| StellariumScope | `10001` |

---

## Entities

All entities are grouped under a single **Telescope** device in Home Assistant.

### Sensors

| Entity | Unit | Description |
|---|---|---|
| `sensor.telescope_ra` | h | Right Ascension (decimal hours) |
| `sensor.telescope_dec` | ° | Declination (decimal degrees) |
| `sensor.telescope_altitude` | ° | Current altitude above horizon |
| `sensor.telescope_azimuth` | ° | Current azimuth |
| `sensor.telescope_local_sidereal_time` | — | Local Sidereal Time string |
| `sensor.telescope_park_status` | — | Park state: Parked / Not parked / Parking / Park failed |
| `sensor.telescope_mount_time` | — | Local time reported by the mount (HH:MM:SS) |

### Binary Sensor

| Entity | States | Description |
|---|---|---|
| `binary_sensor.telescope_connection` | Online / Offline | Whether the mount is reachable |
| `binary_sensor.telescope_guiding` | On / Off | Whether the mount is currently guiding / tracking (`:GU#` `G` flag) |

The connection sensor flips to **Offline** as soon as a poll fails and recovers to **Online** on the next successful poll — no manual intervention required.

### Buttons

| Entity | LX200 Command | Description |
|---|---|---|
| `button.telescope_move_north` | `:Mn#` | Begin slewing north |
| `button.telescope_move_south` | `:Ms#` | Begin slewing south |
| `button.telescope_move_east` | `:Me#` | Begin slewing east |
| `button.telescope_move_west` | `:Mw#` | Begin slewing west |
| `button.telescope_stop_motion` | `:Q#` | Stop all motion immediately |
| `button.telescope_go_to_home` | `:hC#` | Slew to the home (Counterweight Down) position |
| `button.telescope_set_home` | `:hF#` | Save the current position as the home reference |
| `button.telescope_set_park` | `:hQ#` | Save the current position as the park position |
| `button.telescope_sync_time` | `:SC…#` `:SL…#` | Push the current HA date and time to the mount |

> **Motion control workflow:** Press a directional button to start slewing, then press **Stop Motion** when the target is reached. The mount will continue moving until stopped.

> **Home workflow:** Press **Go to Home** to slew to the Counterweight Down (CWD) position. This does not park the mount.

> **Park workflow:** Point the scope at your desired park position and press **Set Park Position** to save it. The **Parked** switch will then move the mount to that position when turned on, and unpark it when turned off.

### Select

| Entity | Options | Description |
|---|---|---|
| `select.telescope_slew_rate` | Guide, Center, Find, Slew | Controls how fast the directional buttons move the mount |

Slew rates from slowest to fastest:

| Option | OnStep command | Use case |
|---|---|---|
| **0.5x** | `:R1#` | Fine guiding corrections |
| **1x** | `:R2#` | Sidereal rate |
| **2x** | `:R3#` | Slow centering |
| **4x** | `:R4#` | Centering |
| **8x** | `:R5#` | Fast centering |
| **20x** | `:R6#` | Searching nearby sky |
| **48x** | `:R7#` | Fast repositioning |
| **Max** | `:R9#` | Full-speed slew |

### Switches

| Entity | Commands | Description |
|---|---|---|
| `switch.telescope_tracking` | `:Te#` / `:Td#` | Enables or disables sidereal tracking |
| `switch.telescope_parked` | `:hP#` / `:hR#` | Parks or unparks the mount |

Both switches read their state from the mount on every poll cycle (via `:GU#`). If the firmware does not report the state, each switch operates optimistically and reflects the last command sent. Both switches become **unavailable** when the mount is offline.

---

## Example Automations

**Turn on a red-light switch when the telescope comes online:**

```yaml
automation:
  - alias: "Telescope session started"
    trigger:
      - platform: state
        entity_id: binary_sensor.telescope_connection
        to: "on"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.observatory_red_light
```

**Stop all motion and disable tracking when the mount goes offline:**

```yaml
automation:
  - alias: "Telescope lost connection"
    trigger:
      - platform: state
        entity_id: binary_sensor.telescope_connection
        to: "off"
    action:
      - service: notify.persistent_notification
        data:
          message: "Telescope mount has gone offline."
```

**Set slew rate to Guide before pressing a direction button (via script):**

```yaml
script:
  nudge_north:
    sequence:
      - service: select.select_option
        target:
          entity_id: select.telescope_slew_rate
        data:
          option: Guide
      - service: button.press
        target:
          entity_id: button.telescope_move_north
      - delay: "00:00:02"
      - service: button.press
        target:
          entity_id: button.telescope_stop_motion
```

---

## Troubleshooting

**Sensors show "Unavailable"**  
The mount is not reachable. Check:
- The mount's WiFi / TCP server is enabled and running.
- The IP address and port match what the mount reports.
- Home Assistant and the mount are on the same network (or a route exists).
- No firewall is blocking the TCP port.

**Connection sensor stays Offline after mount comes back**  
The integration retries on every poll interval. Wait one poll cycle (default 10 s) and it will recover automatically.

**RA / DEC reads 0.0 or doesn't update**  
- The mount may be in low-precision mode. The integration sends `:U#` to switch to high-precision automatically — confirm your firmware supports this.
- Ensure the mount is **connected** in your planetarium software (e.g. KStars/Ekos) before querying; some firmware only reports coordinates once the motor controller is initialised.

**Tracking switch always shows unknown state**  
Older or non-OnStep firmware may not respond to `:GW#`. The switch will still work — it operates optimistically and reflects whatever command was last sent.

**Go to Home does nothing**  
The mechanical home position is set in OnStep firmware (typically the polar-star aligned position). If your firmware does not define one, `:hC#` may have no effect.

**Park switch does not respond**  
Some older firmware versions use different park commands. If `:hP#` / `:hR#` do not work with your mount, check your firmware documentation for the correct park/unpark commands.

---

## Contributing

Issues and pull requests are welcome at [Jaarden/HA-LX200-OnStep](https://github.com/Jaarden/HA-LX200-OnStep/issues).

---

## License

MIT License — see [LICENSE](LICENSE) for details.
