"""Switch platform for the LX200 Telescope integration (tracking + park).

Author: Justin Aarden
GitHub: https://github.com/Jaarden/HA-LX200-OnStep
"""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TelescopeCoordinator
from .lx200 import CannotConnect, send_control

_LOGGER = logging.getLogger(__name__)

# OnStep LX200 commands for tracking
_CMD_TRACKING_ON  = ":Te#"
_CMD_TRACKING_OFF = ":Td#"

# OnStep LX200 commands for park
_CMD_PARK   = ":hP#"
_CMD_UNPARK = ":hR#"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up tracking and park switches from a config entry."""
    coordinator: TelescopeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        TelescopeTrackingSwitch(coordinator),
        TelescopeParkSwitch(coordinator),
    ])


class TelescopeTrackingSwitch(CoordinatorEntity[TelescopeCoordinator], SwitchEntity):
    """Switch that enables / disables mount tracking.

    State is read from the coordinator (via :GW#).  When the coordinator
    cannot determine the state (older firmware), the switch operates
    optimistically — it reflects the last command sent.
    """

    _attr_has_entity_name = True
    _attr_name = "Tracking"
    _attr_icon = "mdi:telescope"

    def __init__(self, coordinator: TelescopeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_tracking"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Telescope",
            manufacturer="Meade / Compatible",
            model="LX200",
        )
        # Optimistic state used when the coordinator returns tracking=None
        self._optimistic_state: bool | None = None

    @property
    def is_on(self) -> bool | None:
        """Return tracking state from coordinator when available, else optimistic.

        :GT# returns 0 Hz when tracking is off and a positive rate when on,
        so the coordinator reflects changes made from any source (app,
        hand controller, etc.).  Falls back to optimistic only when the
        firmware does not respond to :GT#.
        """
        if self.coordinator.data is not None and self.coordinator.data.tracking is not None:
            return self.coordinator.data.tracking
        return self._optimistic_state

    @property
    def available(self) -> bool:
        """Unavailable when the mount is offline."""
        return self.coordinator.last_update_success

    async def async_turn_on(self, **kwargs) -> None:
        """Enable tracking."""
        await self._send(_CMD_TRACKING_ON, optimistic=True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable tracking."""
        await self._send(_CMD_TRACKING_OFF, optimistic=False)

    async def _send(self, cmd: str, optimistic: bool) -> None:
        try:
            await send_control(
                self.coordinator.host,
                self.coordinator.port,
                cmd,
            )
            self._optimistic_state = optimistic
            self.async_write_ha_state()
        except CannotConnect as exc:
            _LOGGER.error("Failed to send tracking command %s: %s", cmd, exc)


class TelescopeParkSwitch(CoordinatorEntity[TelescopeCoordinator], SwitchEntity):
    """Switch that parks / unparks the mount.

    State is read from the coordinator (via :GW# park character).
    When the coordinator cannot determine the state, the switch operates
    optimistically — it reflects the last command sent.
    """

    _attr_has_entity_name = True
    _attr_name = "Parked"
    _attr_icon = "mdi:shield-moon"

    def __init__(self, coordinator: TelescopeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_park"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Telescope",
            manufacturer="Meade / Compatible",
            model="LX200",
        )
        self._optimistic_state: bool | None = None

    @property
    def is_on(self) -> bool | None:
        """Return park state from coordinator, fall back to optimistic."""
        if self.coordinator.data is not None and self.coordinator.data.parked is not None:
            return self.coordinator.data.parked
        return self._optimistic_state

    @property
    def available(self) -> bool:
        """Unavailable when the mount is offline."""
        return self.coordinator.last_update_success

    async def async_turn_on(self, **kwargs) -> None:
        """Park the mount."""
        await self._send(_CMD_PARK, optimistic=True)

    async def async_turn_off(self, **kwargs) -> None:
        """Unpark the mount."""
        await self._send(_CMD_UNPARK, optimistic=False)

    async def _send(self, cmd: str, optimistic: bool) -> None:
        try:
            await send_control(
                self.coordinator.host,
                self.coordinator.port,
                cmd,
            )
            self._optimistic_state = optimistic
            self.async_write_ha_state()
        except CannotConnect as exc:
            _LOGGER.error("Failed to send park command %s: %s", cmd, exc)


