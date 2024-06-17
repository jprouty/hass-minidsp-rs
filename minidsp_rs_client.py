"""A simply py client for minidsp-rs"""

import aiohttp
import asyncio
import ipaddress
import json
import logging
import socket
from typing import Self
from websockets import WebSocketClientProtocol
from websockets.client import connect

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(relativeCreated)6d %(threadName)s %(message)s"
)


STATUS_PORT = 3999
MAX_VOL_DB = 0
MIN_VOL_DB = -127.5


class Device:
    name: str = None
    ip_address: ipaddress.IPv4Address = None
    port: int = 5380
    source: str = None
    sources: list[str] = ["Analog", "Toslink"]  # , "Usb", "Spdif", "Hdmi"]
    muted: bool = False
    preset: int = 0
    volume_db: float = 0
    websocket: WebSocketClientProtocol = None

    def __init__(self, discovery_packet: "DiscoveryPacket") -> None:
        self.name = discovery_packet.name
        self.ip_address = discovery_packet.ip_address
        self.volume_db = MIN_VOL_DB
        self.muted = True
        self.session = aiohttp.ClientSession()
        self.config_url = f"http://{self.ip_address}:{self.port}/devices/0/config"

    async def close(self):
        await self.session.close()
        if self.websocket:
            logger.info(f"Stopping websocket listener for '{self.name}'")
            await self.websocket.close()
            logger.info(f"Stopped")

    # async get get_sources(self):
    #     no api available for this? devices/0/get.schema doesn't correctly filter the available options based on model.

    async def start_websocket_listener(self):
        logger.info(f"Starting websocket listener for '{self.name}'")
        ws_url = f"ws://{self.ip_address}:{self.port}/devices/0?poll=true"
        self.websocket = await connect(ws_url, close_timeout=1)
        async for message in self.websocket:
            logger.info(f"Message: {message}")
            self.update(message)
            # while self.ws_listener_running:
            #     update = await websocket.recv()
            #     logger.info("Update!")
            #     self.update(update)
        logger.info(f"Websocket listener closed '{self.name}'")

    def update(self, update_json) -> bool:
        """Update this Device based on a status msg from the websocket protocol."""
        logger.info(f"Received minidsp update: {update_json}")
        update = json.loads(update_json)
        if "master" not in update:
            logger.warning("No master in update")
            return
        master = update["master"]
        if "source" in master:
            self.source = master["source"]
        if "mute" in master:
            self.muted = master["mute"]
        if "volume" in master:
            self.volume_db = master["volume"]
        if "preset" in master:
            self.preset = master["preset"]

    def get_sources(self):
        return self.sources

    def get_source(self):
        return self.source

    def volume_as_float(self):
        """Volume as a float 0-1."""
        vol_range = MAX_VOL_DB - MIN_VOL_DB
        return (self.volume_db - MIN_VOL_DB) / vol_range

    def volume_as_db(self):
        return f"{self.volume_db}dB"

    def __repr__(self) -> str:
        return f'miniDSP "{self.name}" at {self.ip_address}:{self.port}. Volume: {self.volume_as_db()} {self.volume_as_float()} Muted: {self.muted} Source: {"None" if self.source is None else self.get_source()} Preset: {self.preset}'

    async def async_mute(self, mute_state):
        await self.session.post(
            self.config_url, json={"master_status": {"mute": mute_state}}
        )

    async def async_volume_up(self):
        await self.async_set_volume_db(self.volume_db + 0.5)

    async def async_volume_down(self):
        await self.async_set_volume_db(self.volume_db - 0.5)

    async def async_set_volume_float(self, volume_float):
        if volume_float > 1:
            volume_float = 1
        elif volume_float < 0:
            volume_float = 0
        logger.info(f"setting volume to {volume_float}")
        vol_range = MAX_VOL_DB - MIN_VOL_DB
        volume = round(volume_float * vol_range * 2) / 2 + MIN_VOL_DB
        await self.async_set_volume_db(volume)

    async def async_set_volume_db(self, volume_db):
        if volume_db < MIN_VOL_DB:
            volume_db = MIN_VOL_DB
        elif volume_db > MAX_VOL_DB:
            volume_db = MAX_VOL_DB
        self.volume_db = volume_db
        logger.info(f"setting volume to {volume_db}")
        await self.session.post(
            self.config_url, json={"master_status": {"volume": volume_db}}
        )

    async def async_select_source(self, new_source_name):
        logger.info(f"Selecting source {new_source_name}")
        if new_source_name not in self.sources:
            raise ValueError(f"Source {new_source_name} is not one of: {self.sources}")
        self.source = new_source_name
        await self.session.post(
            self.config_url, json={"master_status": {"source": new_source_name}}
        )

    async def async_select_preset(self, preset):
        """Set the preset, 0 indexed (e.g. 0 is 'Preset 1')"""
        logger.info(f"Selecting preset {preset}")
        if preset < 0 or preset > 4:
            raise ValueError(f"Preset {preset} is not valid")
        self.preset = preset
        await self.session.post(
            self.config_url, json={"master_status": {"preset": preset}}
        )


class DiscoveryPacket:
    # 48-bit mac address
    mac_address: int
    ip_address: ipaddress.IPv4Address = None
    hwid: int = None
    dsp_id: int = None
    sn: int = None
    # XMOS Firmware
    fw_major: int = None
    # XMOS Firmware
    fw_minor: int = None
    name: str = None

    def __repr__(self) -> str:
        return f"DiscoveryPacket(name='{self.name}', mac_address={self.mac_address:012x}, ip_address={self.ip_address}, hwid={self.hwid}, dsp_id={self.dsp_id}, sn={self.sn}, fw_major={self.fw_major}, fw_minor={self.fw_minor})"

    @staticmethod
    def parse(data) -> Self:
        if len(data) < 36:
            raise ValueError(
                f"Discovery packet must be larger than 35 - got: {len(data)}"
            )

        name_len = data[35]
        if len(data) < 36 + name_len:
            raise ValueError("Name doesn't fit")

        result = DiscoveryPacket()
        result.name = data[36 : 36 + name_len].decode("UTF-8")
        result.ip_address = ipaddress.ip_address(
            (data[14] << 24) | (data[15] << 16) | (data[16] << 8) | data[17]
        )
        result.mac_address = (
            (data[6] << 40)
            | (data[7] << 32)
            | (data[8] << 24)
            | (data[9] << 16)
            | (data[10] << 8)
            | data[11]
        )
        result.hwid = data[18]
        result.dsp_id = data[21]
        result.sn = (data[22] << 8) | data[23]
        result.fw_major = data[19]
        result.fw_minor = data[20]
        return result


class DiscoveryProtocol:
    def __init__(self, network_controller) -> None:
        self.network_controller = network_controller

    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, transport):
        logger.info("Connection lost")
        # pass

    def error_received(self, exc):
        logger.info("Error")
        # pass

    def datagram_received(self, data, addr):
        # logger.info(f"Received {data}")
        packet = DiscoveryPacket.parse(data)
        # logger.info(f"Parsed {packet}")
        asyncio.ensure_future(self.network_controller.async_on_discovery_packet(packet))


class NetworkController:
    def __init__(self) -> None:
        # Device name -> Device object
        self.devices = {}
        self.status_transport = None
        self.status_protocol = None
        self.on_new_device = []
        self.on_device_update = []

    async def async_on_discovery_packet(self, packet):
        awaits = []
        if packet.name not in self.devices:
            logger.info(f"New minidsp device: {packet}")
            device = Device(packet)
            self.devices[packet.name] = device
            for listener in self.on_new_device:
                awaits.append(listener(device))
        await asyncio.gather(*awaits)

    async def listen(self):
        """Creates a UDP listener for minidsp-rs discovery messages."""
        logger.info("Starting minidsp-rs UDP Status Listening Service")
        loop = asyncio.get_running_loop()
        (
            self.status_transport,
            self.status_protocol,
        ) = await loop.create_datagram_endpoint(
            lambda: DiscoveryProtocol(self),
            allow_broadcast=True,
            local_addr=("0.0.0.0", STATUS_PORT),
            family=socket.AF_INET,
        )

    async def close(self):
        """Stops the UDP listener."""
        if self.status_transport:
            logger.info("Stopped minidsp-rs UDP Status Listening Service")
            self.status_transport.close()
            self.status_transport = None
            self.status_protocol = None

    def add_listener_on_new_device(self, callable):
        self.on_new_device.append(callable)

    def get_devices(self):
        return [v for v in self.devices.values()]


async def test_on_new_device(device):
    print(f"New device: {device}")
    asyncio.ensure_future(device.start_websocket_listener())
    loop = asyncio.get_event_loop()
    # t = loop.create_task(device.start_websocket_listener())

    # await asyncio.sleep(1)
    # await device.async_mute(True)
    # await asyncio.sleep(1)
    # await device.async_mute(False)

    # for v in range(0, 256):
    #     logger.info(f"Volume {v}")
    #     await device.async_set_volume_float(v / 255)
    #     await asyncio.sleep(0.1)

    # for v in range(-255, 1):
    #     v = v / 2.0
    #     logger.info(f"Volume {v}")
    #     await device.async_set_volume_db(v)
    #     logger.info(
    #         f"Volume as db: {device.volume_as_db()} and float: {device.volume_as_float()}"
    #     )
    #     await asyncio.sleep(0.1)

    # await device.async_set_volume_db(-100)
    # await asyncio.sleep(1)
    # await device.async_volume_up()
    # await device.async_volume_up()
    # await device.async_volume_up()
    # await device.async_volume_up()
    # await asyncio.sleep(1)
    # await device.async_volume_down()
    # await device.async_volume_down()

    # await device.async_select_source("Analog")
    # await device.async_select_source("Toslink")
    # await device.async_select_preset(0)
    # await asyncio.sleep(1)

    await asyncio.sleep(3)
    await device.close()


async def test_discovery():
    nc = NetworkController()
    nc.add_listener_on_new_device(test_on_new_device)
    await nc.listen()
    await asyncio.sleep(5)
    await nc.close()
    logger.info(f"Devices: {nc.get_devices()}")
    for t in asyncio.all_tasks():
        logger.info(t)


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    asyncio.run(test_discovery())
    logger.info("Done")
