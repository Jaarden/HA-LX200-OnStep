"""DataUpdateCoordinator for the LX200 Telescope integration.

Author: Justin Aarden
GitHub: https://github.com/Jaarden/HA-LX200-OnStep
"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .lx200 import CannotConnect, TelescopeData, query_mount

_LOGGER = logging.getLogger(__name__)


class TelescopeCoordinator(DataUpdateCoordinator[TelescopeData]):
    """Polls the telescope mount on a fixed interval."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.host: str = entry.data[CONF_HOST]
        self.port: int = entry.data[CONF_PORT]
        interval: int = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.config_entry = entry

    async def _async_update_data(self) -> TelescopeData:
        try:
            return await query_mount(self.host, self.port)
        except CannotConnect as exc:
            raise UpdateFailed(str(exc)) from exc
