# Renpho Health for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Home Assistant integration for Renpho Health smart scales. Access your body composition data directly in Home Assistant.

## Features

- **Body Composition Sensors**: Weight, BMI, body fat %, muscle mass, water %, bone mass
- **Metabolic Data**: Visceral fat, BMR (Basal Metabolic Rate), body age
- **Extended Metrics**: Protein %, subcutaneous fat, skeletal muscle
- **No Session Conflicts**: Uses the modern Renpho Health API - won't log you out of the app
- **Easy Setup**: Configuration through the Home Assistant UI

## Requirements

- Home Assistant 2024.1.0 or newer
- A [Renpho Health](https://renpho.com) account with a connected smart scale
- **Important**: This works with the **Renpho Health** app (blue icon), not the legacy Renpho app

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu → **Custom repositories**
3. Add `https://github.com/StartupBros/hass-renpho-health` as an **Integration**
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

| Sensor | Unit | Description |
|--------|------|-------------|
| Weight | kg | Body weight |
| BMI | kg/m² | Body Mass Index |
| Body Fat | % | Body fat percentage |
| Muscle Mass | % | Muscle mass percentage |
| Body Water | % | Body water percentage |
| Bone Mass | kg | Bone mass |
| BMR | kcal/day | Basal Metabolic Rate |
| Visceral Fat | level | Visceral fat level (1-59) |
| Body Age | years | Metabolic body age |
| Protein | % | Protein percentage |
| Subcutaneous Fat | % | Subcutaneous fat percentage |
| Skeletal Muscle | % | Skeletal muscle percentage |

## Technical Notes

- Uses the Renpho Health API (`cloud.renpho.com`), not the legacy API
- Implements AES-128-ECB encryption for secure API communication
- Data is polled at configurable intervals (minimum 5 minutes)
- No data is stored permanently or sent to third parties

## Comparison to hass_renpho

| Feature | This Integration | hass_renpho |
|---------|-----------------|-------------|
| API | Renpho Health (new) | Legacy Renpho |
| Session Conflicts | None | Yes (logs you out) |
| Last Updated | 2026 | 2024 |
| Active Development | Yes | Limited |

## Credits

API implementation based on reverse engineering from [RenphoGarminSync-CLI](https://github.com/forkerer/RenphoGarminSync-CLI).

## License

MIT
