"""Support for Devialet Expect integrated amps."""
from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player.const import MediaPlayerState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_NETWORK_CONTROLLER,
    DEFAULT_SCAN_INTERVAL,
    DISPATCH_DEVICE_DISCOVERED,
    DISPATCH_DEVICE_UPDATE,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    UNAVAILABLE_TIMEOUT_S,
)
from .devialet_expert import Device

_LOGGER = logging.getLogger(__name__)

# SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

# SELECT_SOUND_MODE
SUPPORT_DEVIALET = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
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
    for device in nc.get_devices():
        init_device(device)

    # Connect to register any further components
    config.async_on_unload(
        async_dispatcher_connect(hass, DISPATCH_DEVICE_DISCOVERED, init_device)
    )


class DevialetDevice(MediaPlayerEntity):
    """Representation of a Devialet device."""

    def __init__(self, device: Device) -> None:
        """Initialize the Devialet device."""
        self._device = device
        self._last_update = datetime.now()

    @property
    def state(self) -> MediaPlayerState | None:
        """State of the media player."""
        return MediaPlayerState.ON if self._device.power else MediaPlayerState.OFF

    @property
    def entity_picture(self) -> str | None:
        """Url of a picture to show for the entity."""
        return "https://assets.devialet.com/en-us/media/dvl_media/Expert_Packshot_220-3_4.png?twic=v1/background=f4f4f4/cover=800x800"

    @property
    def volume_step(self) -> float | None:
        """Volume step to use for the volume_up and volume_down services."""
        return 1/255

    @property
    def icon(self) -> str | None:
        """Icon to use in the frontend.

        Icons start with mdi: plus an identifier. You probably don't need this since Home Assistant already provides default icons for all entities according to its device_class. This should be used only in the case where there either is no matching device_class or where the icon used for the device_class would be confusing or misleading.
        """
        return "mdi:amplifier"

    @property
    def should_poll(self) -> bool:
        """Should Home Assistant check with the entity for an updated state. If set to False, entity will need to notify Home Assistant of new updates by calling one of the schedule update methods."""
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.name)},
            name=self._device.name,
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version="10.1.0",
        )

    @property
    def available(self) -> bool:
        """Indicate if Home Assistant is able to read the state and control the underlying device."""
        time_since_last_update = datetime.now() - self._last_update
        return time_since_last_update.total_seconds() < UNAVAILABLE_TIMEOUT_S

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
        return self._device.volume_hass_scale()

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

    async def async_added_to_hass(self) -> None:
        """Call on adding to hass."""

        # Register for connect/disconnect/update events
        # @callback
        # def controller_disconnected(ctrl: Controller, ex: Exception) -> None:
        #     """Disconnected from controller."""
        #     if ctrl is not self._controller:
        #         return
        #     self.set_available(False, ex)

        # self.async_on_remove(
        #     async_dispatcher_connect(
        #         self.hass, DISPATCH_CONTROLLER_DISCONNECTED, controller_disconnected
        #     )
        # )

        # @callback
        # def controller_reconnected(ctrl: Controller) -> None:
        #     """Reconnected to controller."""
        #     if ctrl is not self._controller:
        #         return
        #     self.set_available(True)

        # self.async_on_remove(
        #     async_dispatcher_connect(
        #         self.hass, DISPATCH_CONTROLLER_RECONNECTED, controller_reconnected
        #     )
        # )

        @callback
        def device_update(device: Device, new_state: bool) -> None:
            """Handle Device data updates."""
            # Ignore device updates for other devices:
            if self._device.name != device.name:
                return
            self._last_update = datetime.now()
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(self.hass, DISPATCH_DEVICE_UPDATE, device_update)
        )

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
