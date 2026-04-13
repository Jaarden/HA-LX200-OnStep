"""Binary sensor platform for the LX200 Telescope integration.

Author: Justin Aarden
GitHub: https://github.com/Jaarden/HA-LX200-OnStep
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TelescopeCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up telescope binary sensors."""
    coordinator: TelescopeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        TelescopeConnectivitySensor(coordinator),
        TelescopeGuidingSensor(coordinator),
    ])


class TelescopeConnectivitySensor(
    CoordinatorEntity[TelescopeCoordinator], BinarySensorEntity
):
    """Reports whether the telescope mount is reachable."""

    _attr_has_entity_name = True
    _attr_name = "Connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: TelescopeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_connectivity"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Telescope",
            manufacturer="Meade / Compatible",
            model="LX200",
            configuration_url=f"http://{coordinator.host}:{coordinator.port}",
        )

    @property
    def is_on(self) -> bool:
        """True = online, False = offline."""
        return self.coordinator.last_update_success


class TelescopeGuidingSensor(
    CoordinatorEntity[TelescopeCoordinator], BinarySensorEntity
):
    """Reports whether the mount is currently guiding / tracking.

    OnStep uses the 'G' flag in the :GU# response to indicate that guiding
    (sidereal tracking with corrections) is in progress.
    """

    _attr_has_entity_name = True
    _attr_name = "Guiding"
    _attr_icon = "mdi:star-four-points-circle"

    def __init__(self, coordinator: TelescopeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_guiding"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Telescope",
            manufacturer="Meade / Compatible",
            model="LX200",
            configuration_url=f"http://{coordinator.host}:{coordinator.port}",
        )

    @property
    def is_on(self) -> bool | None:
        """True = guiding active, False = not guiding, None = unknown."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.guiding

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success
