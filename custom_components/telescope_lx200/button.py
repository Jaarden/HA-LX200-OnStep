"""Button platform for the LX200 Telescope integration.

Author: Justin Aarden
GitHub: https://github.com/Jaarden/HA-LX200-OnStep
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import TelescopeCoordinator
from .lx200 import CannotConnect, send_control, sync_time

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class TelescopeButtonDescription(ButtonEntityDescription):
    """Extends ButtonEntityDescription with the LX200 command to send."""
    command: str = ""
    unpark_after: bool = False              # send :hR# after the main command
    follow_up_commands: tuple[str, ...] = ()# extra commands sent after the main one
    refresh_after: bool = False             # request a coordinator poll to update sensors immediately


BUTTON_DESCRIPTIONS: tuple[TelescopeButtonDescription, ...] = (
    TelescopeButtonDescription(
        key="move_north",
        name="Move North",
        icon="mdi:arrow-up-circle",
        command=":Mn#",
    ),
    TelescopeButtonDescription(
        key="move_south",
        name="Move South",
        icon="mdi:arrow-down-circle",
        command=":Ms#",
    ),
    TelescopeButtonDescription(
        key="move_east",
        name="Move East",
        icon="mdi:arrow-right-circle",
        command=":Me#",
    ),
    TelescopeButtonDescription(
        key="move_west",
        name="Move West",
        icon="mdi:arrow-left-circle",
        command=":Mw#",
    ),
    TelescopeButtonDescription(
        key="stop_motion",
        name="Stop Motion",
        icon="mdi:stop-circle",
        command=":Q#",
    ),
    TelescopeButtonDescription(
        key="go_home",
        name="Go to Home",
        icon="mdi:home-import-outline",
        command=":hC#",
        unpark_after=True,
        refresh_after=True,
    ),
    TelescopeButtonDescription(
        key="set_home",
        name="Set Home",
        icon="mdi:home-edit",
        command=":hF#",
        follow_up_commands=(":Td#",),  # stop tracking so mount is ready to move
        refresh_after=True,
    ),
    TelescopeButtonDescription(
        key="set_park",
        name="Set Park Position",
        icon="mdi:map-marker-check",
        command=":hQ#",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up telescope buttons from a config entry."""
    coordinator: TelescopeCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = [
        TelescopeButton(coordinator, description)
        for description in BUTTON_DESCRIPTIONS
    ]
    entities.append(TelescopeTimeSyncButton(coordinator))
    async_add_entities(entities)


class TelescopeButton(ButtonEntity):
    """A button that sends a single LX200 command to the mount."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TelescopeCoordinator,
        description: TelescopeButtonDescription,
    ) -> None:
        self.entity_description = description
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Telescope",
            manufacturer="Meade / Compatible",
            model="LX200",
        )

    async def async_press(self) -> None:
        """Send the LX200 command when the button is pressed.

        For Go to Home and Set Home, an unpark command is sent afterwards so
        the mount is immediately ready for movement without manual intervention.
        A coordinator refresh is requested so sensors update straight away.
        """
        host = self._coordinator.host
        port = self._coordinator.port
        try:
            await send_control(host, port, self.entity_description.command)
            if self.entity_description.unpark_after:
                await send_control(host, port, ":hR#")
            for cmd in self.entity_description.follow_up_commands:
                await send_control(host, port, cmd)
        except CannotConnect as exc:
            _LOGGER.error(
                "Failed to send %s to mount: %s",
                self.entity_description.command,
                exc,
            )
            return

        if self.entity_description.refresh_after:
            await self._coordinator.async_request_refresh()


class TelescopeTimeSyncButton(ButtonEntity):
    """Button that syncs the current date and time from Home Assistant to the mount."""

    _attr_has_entity_name = True
    _attr_name = "Sync Time"
    _attr_icon = "mdi:clock-check"

    def __init__(self, coordinator: TelescopeCoordinator) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_sync_time"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Telescope",
            manufacturer="Meade / Compatible",
            model="LX200",
        )

    async def async_press(self) -> None:
        """Send the current date and time to the mount."""
        now = dt_util.now()
        date_str = now.strftime("%m/%d/%y")   # MM/DD/YY
        time_str = now.strftime("%H:%M:%S")   # HH:MM:SS (24-hour local time)
        try:
            await sync_time(
                self._coordinator.host,
                self._coordinator.port,
                date_str,
                time_str,
            )
            _LOGGER.debug("Synced time to mount: %s %s", date_str, time_str)
            await self._coordinator.async_request_refresh()
        except CannotConnect as exc:
            _LOGGER.error("Failed to sync time to mount: %s", exc)
