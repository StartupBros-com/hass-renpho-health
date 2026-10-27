# Renpho Health for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Home Assistant integration for Renpho Health smart scales. Access your body composition data directly in Home Assistant.

## Features

- **Body Composition Sensors**: Weight, BMI, body fat %, muscle mass, water %, bone mass
- **Metabolic Data**: Visceral fat, BMR (Basal Metabolic Rate), body age
- **Extended Metrics**: Protein %, subcutaneous fat, skeletal muscle
- **Easy Setup**: Configuration through the Home Assistant UI

## Requirements

- Home Assistant 2024.1.0 or newer
- A [Renpho Health](https://renpho.com) account with a connected smart scale
- **Important**: This works with the **Renpho Health** app (blue icon), not the legacy Renpho app

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu → **Custom repositories**
3. Add `https://github.com/StartupBros-com/hass-renpho-health` as an **Integration**
4. Search for "Renpho Health" and install
5. Restart Home Assistant

### Manual Installation

1. Download the latest release
2. Copy `custom_components/renpho_health` to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Renpho Health"
4. Enter your Renpho Health app credentials
5. Set your preferred update interval (default: 1 hour)

## Sensors

| Sensor           | Unit     | Description                 |
| ---------------- | -------- | --------------------------- |
| Weight           | kg       | Body weight                 |
| BMI              | kg/m²    | Body Mass Index             |
| Body Fat         | %        | Body fat percentage         |
| Muscle Mass      | %        | Muscle mass percentage      |
| Body Water       | %        | Body water percentage       |
| Bone Mass        | kg       | Bone mass                   |
| BMR              | kcal/day | Basal Metabolic Rate        |
| Visceral Fat     | level    | Visceral fat level (1-59)   |
| Body Age         | years    | Metabolic body age          |
| Protein          | %        | Protein percentage          |
| Subcutaneous Fat | %        | Subcutaneous fat percentage |
| Skeletal Muscle  | %        | Skeletal muscle percentage  |

## Technical Notes

- Uses the Renpho Health API (`cloud.renpho.com`), not the legacy API
- HTTPS provides transport security. Renpho additionally requires AES-128-ECB payload encoding with a protocol key embedded in the client; this is not an independent security boundary.
- Data is polled at configurable intervals (minimum 5 minutes)
- Requests send credentials and retrieve account/health data from Renpho cloud. Home Assistant persists the configured email and password in its config-entry storage; protect your configuration directory and backups.
- Home Assistant may retain sensor history through Recorder and operational messages through logs. Review your Recorder exclusions, purge settings, log retention and backup policy for your privacy needs. This integration avoids logging account/health payloads.

## Development and compatibility

See [reproducible developer checks](tests/README.md). Fixture tests cover Home
Assistant 2024.1.0 on Python 3.11.14 and 2026.2.3 on Python 3.13.11. These are the
bounded tested versions, not evidence for every intervening release or a live
Renpho account/scale installation.

HACS custom-repository installation is distinct from default catalog eligibility.
The repository currently lacks a Home Assistant brands entry;
full HACS catalog readiness remains blocked. CI runs tests and Hassfest;
it does not claim a passing full HACS validator.

## Credits

API implementation based on reverse engineering from [RenphoGarminSync-CLI](https://github.com/forkerer/RenphoGarminSync-CLI).

## License

MIT
