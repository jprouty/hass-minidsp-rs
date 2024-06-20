"""Constants for the miniDSP-RS integration."""

from typing import Final

DOMAIN: Final = "minidsp_rs"
# miniDSP-RS devices average status messages roughly every 300ms. 2 seconds should be able to catch all experts broadcasting on network, including for packet loss.
DEFAULT_SCAN_INTERVAL: Final = 5
UNAVAILABLE_TIMEOUT_S: Final = 60
MANUFACTURER: Final = "miniDSP"
MODEL: Final = "Flex HTx"

DATA_NETWORK_CONTROLLER = "minidsp_rs_network_controller"
DATA_CONFIG = "minidsp_rs_config"

DISPATCH_DEVICE_DISCOVERED = "minidsp_rs_device_discovered"
DISPATCH_DEVICE_UPDATE = "minidsp_rs_device_update"
