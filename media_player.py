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
from .minidsp_rs_client import Device

_LOGGER = logging.getLogger(__name__)

# SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

SUPPORT_MINIDSP_RS = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
)


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize an IZone Controller."""
    nc = hass.data[DATA_NETWORK_CONTROLLER]

    @callback
    def init_device(device: Device):
        """Register the minidsp-rs device."""
        _LOGGER.info(f"miniDSP RS device {device.name} discovered")

        device = MiniDspRsDevice(device)
        async_add_entities([device])

    # Create Entities for discovered devices.
    for device in nc.get_devices():
        init_device(device)

    # Connect to register any further components
    config.async_on_unload(
        async_dispatcher_connect(hass, DISPATCH_DEVICE_DISCOVERED, init_device)
    )


class MiniDspRsDevice(MediaPlayerEntity):
    """Representation of a minidsp-rs device."""

    def __init__(self, device: Device) -> None:
        """Initialize the minidsp-rs device."""
        self._device = device
        self._last_update = datetime.now()

    @property
    def state(self) -> MediaPlayerState | None:
        """State of the media player."""
        return MediaPlayerState.ON

    @property
    def entity_picture(self) -> str | None:
        """Url of a picture to show for the entity."""
        return "https://www.minidsp.com/images/stories/virtuemart/product/Flex-HTx-(front)-600px.png"

    @property
    def volume_step(self) -> float | None:
        """Volume step to use for the volume_up and volume_down services."""
        return 1 / 255

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
        return self._device.volume_as_float()

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
        return SUPPORT_MINIDSP_RS

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self._device.get_source()

    @property
    def sound_mode(self) -> str | None:
        """The current sound mode of the media player."""
        return f"Preset {self._device.preset + 1}"

    @property
    def sound_mode_list(self) -> str | None:
        """Dynamic list of available sound modes.."""
        return ["Preset 1", "Preset 2", "Preset 3", "Preset 4"]

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
        await self._device.async_set_volume_float(volume)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        await self._device.async_mute(mute)

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self._device.async_select_source(source)

    async def async_select_sound_mode(self, sound_mode):
        """Switch the sound mode of the entity."""
        sound_mode = int(sound_mode.split(" ")[1]) - 1
        await self._device.async_select_preset(sound_mode)
