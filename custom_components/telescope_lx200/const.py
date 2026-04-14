"""Constants for the LX200 Telescope integration.

Author: Justin Aarden
GitHub: https://github.com/Jaarden/HA-LX200-OnStep
"""

DOMAIN = "telescope_lx200"

CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_PORT = 9999
DEFAULT_SCAN_INTERVAL = 10   # seconds

CONNECT_TIMEOUT = 5.0        # seconds to establish TCP connection
CMD_TIMEOUT = 2.0            # seconds to wait for each LX200 response
