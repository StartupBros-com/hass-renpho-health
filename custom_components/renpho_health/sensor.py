"""Sensor platform for Renpho Health."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RenphoHealthCoordinator


@dataclass(frozen=True, kw_only=True)
class RenphoSensorEntityDescription(SensorEntityDescription):
    """Describes a Renpho sensor entity."""

    value_key: str


SENSOR_DESCRIPTIONS: tuple[RenphoSensorEntityDescription, ...] = (
    RenphoSensorEntityDescription(
        key="weight",
        value_key="weight",
        translation_key="weight",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RenphoSensorEntityDescription(
        key="bmi",
        value_key="bmi",
        translation_key="bmi",
        native_unit_of_measurement="kg/m²",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:human",
    ),
    RenphoSensorEntityDescription(
        key="bodyfat",
        value_key="bodyfat",
        translation_key="body_fat",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:percent",
    ),
    RenphoSensorEntityDescription(
        key="muscle",
        value_key="muscle",
        translation_key="muscle_mass",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:arm-flex",
    ),
    RenphoSensorEntityDescription(
        key="water",
        value_key="water",
        translation_key="water",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
    ),
    RenphoSensorEntityDescription(
        key="bone",
        value_key="bone",
        translation_key="bone_mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RenphoSensorEntityDescription(
        key="bmr",
        value_key="bmr",
        translation_key="bmr",
        native_unit_of_measurement="kcal/day",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fire",
    ),
    RenphoSensorEntityDescription(
        key="visceral_fat",
        value_key="visceral_fat",
        translation_key="visceral_fat",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:stomach",
    ),
    RenphoSensorEntityDescription(
        key="body_age",
        value_key="body_age",
        translation_key="body_age",
        native_unit_of_measurement="years",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:calendar-account",
    ),
    RenphoSensorEntityDescription(
        key="protein",
        value_key="protein",
        translation_key="protein",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:food-steak",
    ),
    RenphoSensorEntityDescription(
        key="subcutaneous_fat",
        value_key="subcutaneous_fat",
        translation_key="subcutaneous_fat",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:percent",
    ),
    RenphoSensorEntityDescription(
        key="skeletal_muscle",
        value_key="skeletal_muscle",
        translation_key="skeletal_muscle",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:arm-flex-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Renpho Health sensors from a config entry."""
    coordinator: RenphoHealthCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        RenphoHealthSensor(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class RenphoHealthSensor(CoordinatorEntity[RenphoHealthCoordinator], SensorEntity):
    """Representation of a Renpho Health sensor."""

    entity_description: RenphoSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RenphoHealthCoordinator,
        description: RenphoSensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Renpho Health Scale",
            manufacturer="Renpho",
            model="Smart Scale",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get(self.entity_description.value_key)
        if value is not None and isinstance(value, float):
            return round(value, 1)
        return value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.entity_description.value_key in self.coordinator.data
            and self.coordinator.data[self.entity_description.value_key] is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None
        last_updated = self.coordinator.data.get("last_updated")
        if last_updated:
            return {"measurement_time": last_updated.isoformat()}
        return None
