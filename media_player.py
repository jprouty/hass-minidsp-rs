"""Support for Devialet Expect integrated amps."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_NETWORK_CONTROLLER,
    DEFAULT_SCAN_INTERVAL,
    DISPATCH_CONTROLLER_DISCOVERED,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)
from .devialet_expert import Device

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

SUPPORT_DEVIALET = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
)


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize an IZone Controller."""
    nc = hass.data[DATA_NETWORK_CONTROLLER]

    @callback
    def init_device(device: Device):
        """Register the Devialet device."""
        _LOGGER.info(f"Devialet Device {device.name} discovered")

        device = DevialetDevice(device)
        async_add_entities([device])

    # Create Entities for discovered devices.
    for device in nc.devices():
        init_device(device)

    # Connect to register any further components
    config.async_on_unload(
        async_dispatcher_connect(hass, DISPATCH_CONTROLLER_DISCOVERED, init_device)
    )


class DevialetDevice(MediaPlayerEntity):
    """Representation of a Devialet device."""

    def __init__(self, device: Device) -> None:
        """Initialize the Devialet device."""
        self._device = device

    # async def async_update(self) -> None:
    #     """Get the latest details from the device."""
    #     await self._client.async_update()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.name)},
            name=self.device.name,
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version="10.1.0",
        )

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._device.name

    @property
    def unique_id(self) -> str:
        """Return the unique id of the device."""
        return self._device.name

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self._device.volume

    @property
    def is_volume_muted(self) -> bool | None:
        """Return boolean if volume is currently muted."""
        return self._device.muted

    @property
    def source_list(self) -> list[str] | None:
        """Return the list of available input sources."""
        return self._device.get_sources()

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        return SUPPORT_DEVIALET

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self._device.get_source()

    async def async_volume_up(self) -> None:
        """Volume up media player."""
        await self._device.async_volume_up()

    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self._device.async_volume_down()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._device.async_set_volume(volume)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        await self._device.async_mute(mute)

    async def async_turn_off(self) -> None:
        """Turn off media player."""
        await self._device.async_turn_off()

    async def async_turn_on(self) -> None:
        """Turn on media player."""
        await self._device.async_turn_on()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self._device.async_select_source(source)
