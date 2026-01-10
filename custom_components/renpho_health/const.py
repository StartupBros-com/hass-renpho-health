"""Constants for the Renpho Health integration."""
from typing import Final

DOMAIN: Final = "renpho_health"

# Configuration keys
CONF_EMAIL: Final = "email"
CONF_PASSWORD: Final = "password"
CONF_REFRESH_INTERVAL: Final = "refresh_interval"

# Default values
DEFAULT_REFRESH_INTERVAL: Final = 3600  # 1 hour in seconds

# API constants
API_BASE: Final = "https://cloud.renpho.com"
ENCRYPTION_SECRET: Final = "ed*wijdi$h6fe3ew"

# Sensor categories
SENSOR_WEIGHT: Final = "weight"
SENSOR_BMI: Final = "bmi"
SENSOR_BODY_FAT: Final = "bodyfat"
SENSOR_MUSCLE: Final = "muscle"
SENSOR_WATER: Final = "water"
SENSOR_BONE: Final = "bone"
SENSOR_BMR: Final = "bmr"
SENSOR_VISCERAL_FAT: Final = "visceral_fat"
SENSOR_BODY_AGE: Final = "body_age"
SENSOR_PROTEIN: Final = "protein"
SENSOR_SUBCUTANEOUS_FAT: Final = "subcutaneous_fat"
SENSOR_SKELETAL_MUSCLE: Final = "skeletal_muscle"
