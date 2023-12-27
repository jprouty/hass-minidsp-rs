"""Constants for the Devialet integration."""
from typing import Final

DOMAIN: Final = "devialet_expert"
DEFAULT_SCAN_INTERVAL: Final = 5
MANUFACTURER: Final = "Devialet"
MODEL: Final = "Expert"

DATA_NETWORK_CONTROLLER = "devialet_expert_network_controller"
DATA_CONFIG = "devialet_expert_config"

DISPATCH_CONTROLLER_DISCOVERED = "devialet_expert_controller_discovered"
DISPATCH_CONTROLLER_DISCONNECTED = "devialet_expert_controller_disconnected"
DISPATCH_CONTROLLER_RECONNECTED = "devialet_expert_controller_reconnected"
DISPATCH_CONTROLLER_UPDATE = "devialet_expert_controller_update"
DISPATCH_ZONE_UPDATE = "devialet_expert_zone_update"
