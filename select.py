"""Select platform for the LX200 Telescope integration (slew rate).

Author: Justin Aarden
GitHub: https://github.com/Jaarden/HA-LX200-OnStep
"""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TelescopeCoordinator
from .lx200 import SLEW_RATES, CannotConnect, send_control

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the slew rate selector from a config entry."""
    coordinator: TelescopeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TelescopeSlewRateSelect(coordinator)])


class TelescopeSlewRateSelect(SelectEntity):
    """Select entity that controls the mount's slew rate."""

    _attr_has_entity_name = True
    _attr_name = "Slew Rate"
    _attr_icon = "mdi:speedometer"
    _attr_options = list(SLEW_RATES.keys())   # ["Guide", "Center", "Find", "Slew"]

    def __init__(self, coordinator: TelescopeCoordinator) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_slew_rate"
        self._attr_current_option = "Max"   # default; mount powers on at max slew rate
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Telescope",
            manufacturer="Meade / Compatible",
            model="LX200",
        )

    async def async_select_option(self, option: str) -> None:
        """Send the rate command and update local state."""
        cmd = SLEW_RATES.get(option)
        if cmd is None:
            _LOGGER.warning("Unknown slew rate option: %s", option)
            return
        try:
            await send_control(self._coordinator.host, self._coordinator.port, cmd)
            self._attr_current_option = option
            self.async_write_ha_state()
        except CannotConnect as exc:
            _LOGGER.error("Failed to set slew rate %s: %s", option, exc)
