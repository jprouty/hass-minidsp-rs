"""Constants for the Devialet integration."""
from typing import Final

DOMAIN: Final = "devialet_expert"
# Devialet Expert devices average status messages roughly every 300ms. 2 seconds should be able to catch all experts broadcasting on network, including for packet loss.
DEFAULT_SCAN_INTERVAL: Final = 5
UNAVAILABLE_TIMEOUT_S: Final = 60
MANUFACTURER: Final = "Devialet"
MODEL: Final = "Expert"

DATA_NETWORK_CONTROLLER = "devialet_expert_network_controller"
DATA_CONFIG = "devialet_expert_config"

DISPATCH_DEVICE_DISCOVERED = "devialet_expert_device_discovered"
DISPATCH_DEVICE_UPDATE = "devialet_expert_device_update"

# DISPATCH_CONTROLLER_DISCONNECTED = "devialet_expert_controller_disconnected"
# DISPATCH_CONTROLLER_RECONNECTED = "devialet_expert_controller_reconnected"
