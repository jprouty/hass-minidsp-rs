"""Discovery service for Devialet Expert."""
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DATA_NETWORK_CONTROLLER,
    DISPATCH_CONTROLLER_DISCONNECTED,
    DISPATCH_CONTROLLER_DISCOVERED,
    DISPATCH_CONTROLLER_RECONNECTED,
    DISPATCH_CONTROLLER_UPDATE,
    DISPATCH_ZONE_UPDATE,
)
from .devialet_expert import NetworkController

_LOGGER = logging.getLogger(__name__)


# class DiscoveryService(pizone.Listener):
#     """Discovery data and interfacing with pizone library."""

#     def __init__(self, hass: HomeAssistant) -> None:
#         """Initialise discovery service."""
#         super().__init__()
#         self.hass = hass
#         self.pi_disco: pizone.DiscoveryService | None = None

#     # Listener interface
#     def controller_discovered(self, ctrl: pizone.Controller) -> None:
#         """Handle new controller discoverery."""
#         async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_DISCOVERED, ctrl)

#     def controller_disconnected(self, ctrl: pizone.Controller, ex: Exception) -> None:
#         """On disconnect from controller."""
#         async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_DISCONNECTED, ctrl, ex)

#     def controller_reconnected(self, ctrl: pizone.Controller) -> None:
#         """On reconnect to controller."""
#         async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_RECONNECTED, ctrl)

#     def controller_update(self, ctrl: pizone.Controller) -> None:
#         """System update message is received from the controller."""
#         async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_UPDATE, ctrl)

#     def zone_update(self, ctrl: pizone.Controller, zone: pizone.Zone) -> None:
#         """Zone update message is received from the controller."""
#         async_dispatcher_send(self.hass, DISPATCH_ZONE_UPDATE, ctrl, zone)


async def async_start_network_controller(hass: HomeAssistant):
    """Start the Devialet Expert network controller."""
    if nc := hass.data.get(DATA_NETWORK_CONTROLLER):
        # Already started
        return nc
    _LOGGER.info("Starting Devialet Expert Network Controller")

    nc = NetworkController()
    hass.data[DATA_NETWORK_CONTROLLER] = nc
    await nc.listen()

    return nc


async def async_stop_network_controller(hass: HomeAssistant):
    """Stop the network controller."""
    if not (nc := hass.data.get(DATA_NETWORK_CONTROLLER)):
        return

    await nc.close()
    del hass.data[DATA_NETWORK_CONTROLLER]

    _LOGGER.info("Stopped Devialet Expert Network Controller")
