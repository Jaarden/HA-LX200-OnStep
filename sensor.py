"""Sensor platform for the LX200 Telescope integration.

Author: Justin Aarden
GitHub: https://github.com/Jaarden/HA-LX200-OnStep
"""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TelescopeCoordinator

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="ra",
        name="RA",
        native_unit_of_measurement="h",
        icon="mdi:telescope",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="dec",
        name="DEC",
        native_unit_of_measurement="°",
        icon="mdi:compass",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="altitude",
        name="Altitude",
        native_unit_of_measurement="°",
        icon="mdi:elevation-rise",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="azimuth",
        name="Azimuth",
        native_unit_of_measurement="°",
        icon="mdi:rotate-right",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ra_hms",
        name="RA (HMS)",
        icon="mdi:telescope",
    ),
    SensorEntityDescription(
        key="dec_dms",
        name="DEC (DMS)",
        icon="mdi:compass",
    ),
    SensorEntityDescription(
        key="lst",
        name="Local Sidereal Time",
        icon="mdi:clock-outline",
    ),
    SensorEntityDescription(
        key="tracking_rate",
        name="Tracking Rate",
        icon="mdi:orbit",
    ),
    SensorEntityDescription(
        key="park_status",
        name="Park Status",
        icon="mdi:shield-moon",
    ),
    SensorEntityDescription(
        key="local_time",
        name="Mount Time",
        icon="mdi:clock-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up telescope sensors from a config entry."""
    coordinator: TelescopeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        TelescopeSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class TelescopeSensor(CoordinatorEntity[TelescopeCoordinator], SensorEntity):
    """A single sensor that exposes one field from the telescope coordinator."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TelescopeCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Telescope",
            manufacturer="Meade / Compatible",
            model="LX200",
            configuration_url=(
                f"http://{coordinator.host}:{coordinator.port}"
            ),
        )

    @property
    def native_value(self) -> float | str | None:
        data = self.coordinator.data
        if data is None:
            return None
        return getattr(data, self.entity_description.key, None)
