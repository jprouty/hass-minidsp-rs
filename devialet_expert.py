"""An unofficial remote control application for Devialet Expert amplifiers"""

import asyncio
import logging
import math
import socket
from typing import NamedTuple

logger = logging.getLogger(__name__)

# Volume is 0..255, corresponds to -97.5db..30db.

# DB        int float       set_volume
# -97.5dB     0 0.0         0xc2c3
# -40.0dB   115 0.44921875  0xc220
# -39.5db   116             0xc21e
# -39.0db   117             0xc21c
# -38.5db   118             0xc21a
# -35.0db   125             0xc20c
# -30.0dB   135 0.          0xc1f0
# -20.0dB   155 0.          0xc1a0
# -10.0dB   175 0.68627451  0xc120
# 0dB       195 0.76470588  0x0000
# 10.0dB    215 0.84313725  0x4120
# 20.0dB    235 0.          0x41a0
# 30.0dB    255 1           0x41f0

STATUS_PORT = 45454
COMMAND_PORT = 45455
MAX_VOLUME_DB = -10
MAX_VOLUME_INT = 175
NUM_OF_TRANSMITS_PER_COMMAND = 2


def _crc16(data: bytearray):
    """Internal function to calculate a CRC-16/CCITT-FALSE from the given bytearray"""
    if data is None:
        return 0
    crc = 0xFFFF
    for i in enumerate(data):
        crc ^= data[i[0]] << 8
        for _ in range(8):
            if (crc & 0x8000) > 0:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
    return crc & 0xFFFF


def _db_convert(db_value):
    """Internal function to convert dB to a 16-bit representation used by set_volume"""
    db_abs = math.fabs(db_value)
    if db_abs == 0:
        retval = 0
    elif db_abs == 0.5:
        retval = 0x3F00
    else:
        retval = (256 >> math.ceil(1 + math.log(db_abs, 2))) + _db_convert(db_abs - 0.5)
    return retval


class Source(NamedTuple):
    name: str
    index: int
    is_enabled: bool
    is_selected: bool


class Device:
    num_packets: int = 0
    num_commands: int = 0
    name: str = None
    source: int = None
    sources: list[Source] = []
    power: bool = False
    muted: bool = False
    volume: int = 0
    ip_address: str = None

    def __init__(self, status_data: bytearray, addr) -> None:
        self.ip_address = addr[0]
        self.name = status_data[19:50].decode("UTF-8").replace("\x00", "")
        self.sources = []
        self.source = (status_data[308] & 0x3C) >> 2
        for i in range(0, 15):
            is_enabled = int(chr(status_data[52 + i * 17]))
            is_selected = i == self.source
            name = (
                status_data[53 + i * 17 : 52 + (i + 1) * 17]
                .decode("UTF-8")
                .replace("\x00", "")
            )
            self.sources.append(Source(name, i, is_enabled, is_selected))
        self.power = (status_data[307] & 0x80) != 0
        self.muted = (status_data[308] & 0x2) != 0
        self.volume = status_data[310]

    def update(self, device_update) -> bool:
        """Update this Device object based on a newer UDP status update, provided as a Device.

        Returns True if the update contains any new information.
        """
        has_updated = False
        if device_update.name != self.name:
            # Device name mismatch. Exit early.
            return False
        if device_update.ip_address != self.ip_address:
            self.ip_address = device_update.ip_address
            has_updated = True
        if device_update.source != self.source:
            self.source = device_update.source
            has_updated = True
        if device_update.power != self.power:
            self.power = device_update.power
            has_updated = True
        if device_update.muted != self.muted:
            self.muted = device_update.muted
            has_updated = True
        if device_update.volume != self.volume:
            self.volume = device_update.volume
            has_updated = True
        # Always take the latest source list - these should change, expect for the is_selected indicator. However, that state is tracked above in self.source.
        self.sources = device_update.sources
        return has_updated

    def get_sources(self):
        return [s.name for s in self.sources if s.is_enabled]

    def get_source(self):
        return self.sources[self.source].name

    def volume_as_int(self):
        return self.volume

    def volume_as_float(self):
        """Volume as a float 0-1."""
        return self.volume / 255

    def volume_as_db(self):
        return f"{(self.volume - 195) / 2.0}dB"

    def __repr__(self) -> str:
        return f'Devialet Expert "{self.name}" at {self.ip_address}. Volume: {self.volume_as_int()} {self.volume_as_db()} {self.volume_as_float()} Power: {self.power} Muted: {self.muted} Curr Source: {self.get_source()}'

    async def async_turn_on(self):
        await self.async_set_power_state(True)

    async def async_turn_off(self):
        await self.async_set_power_state(False)

    async def async_toggle_power(self):
        await self.async_set_power_state(not self.power)

    async def async_set_power_state(self, power_state):
        data = bytearray(142)
        data[6] = int(power_state)
        data[7] = 0x01
        await self.async_send_command(data)

    async def async_mute(self, mute_state):
        data = bytearray(142)
        data[6] = int(mute_state)
        data[7] = 0x07
        await self.async_send_command(data)

    async def async_volume_up(self):
        await self.async_set_volume_int(self.volume + 1)

    async def async_volume_down(self):
        await self.async_set_volume_int(self.volume - 1)

    async def async_set_volume_float(self, volume_float):
        if volume_float > 1:
            volume_float = 1
        elif volume_float < 0:
            volume_float = 0
        volume = round(volume_float * 255)
        await self.async_set_volume_int(volume)

    async def async_set_volume_int(self, volume):
        if volume > MAX_VOLUME_INT:
            volume = MAX_VOLUME_INT
        
        await self.async_set_volume_db((volume - 195) / 2.0)

    async def async_set_volume_db(self, volume_db):
        if volume_db > MAX_VOLUME_DB:
            volume_db = MAX_VOLUME_DB

        volume = _db_convert(volume_db)

        if volume_db < 0:
            volume |= 0x8000

        data = bytearray(142)
        data[6] = 0x00
        data[7] = 0x04
        data[8] = (volume & 0xFF00) >> 8
        data[9] = volume & 0x00FF
        await self.async_send_command(data)

    async def async_select_source(self, new_source_name):
        logger.debug(f"Selecting source {new_source_name}")
        
        new_source = None
        for s in self.sources:
            if s.name == new_source_name:
                new_source = s
                break

        if new_source is None:
            raise ValueError(f"Invalid source {new_source_name}. Options: {self.get_sources()}")

        out_val = 0x4000 | (new_source.index << 5)
        data = bytearray(142)
        data[6] = 0x00
        data[7] = 0x05
        data[8] = (out_val & 0xFF00) >> 8
        if new_source.index > 7:
            data[9] = (out_val & 0x00FF) >> 1
        else:
            data[9] = out_val & 0x00FF
        await self.async_send_command(data)

    async def async_send_command(self, command: bytearray, times: int = 2):
        loop = asyncio.get_running_loop()

        on_close = loop.create_future()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: SendCommandProtocol(command, on_close, times, self),
            remote_addr=(self.ip_address, COMMAND_PORT),
        )

        try:
            await on_close
        finally:
            transport.close()


class SendCommandProtocol:
    def __init__(self, command, on_close, times, device):
        self.command = command
        self.on_close = on_close
        self.times = times
        self.device = device
        self.transport = None

    def prepare_command(self):
        self.command[0] = 0x44
        self.command[1] = 0x72

        if self.device.num_packets > 0xffff:
            self.device.num_packets = 0
        if self.device.num_commands > 0xffff:
            self.device.num_commands = 0

        self.command[2] = (self.device.num_packets & 0xff00) >> 8
        self.command[3] = self.device.num_packets & 0x00ff
        self.command[4] = (self.device.num_commands & 0xff00) >> 8
        self.command[5] = self.device.num_commands & 0x00ff
        
        crc = _crc16(self.command[0:12])
        self.command[12] = (crc & 0xFF00) >> 8
        self.command[13] = crc & 0x00FF

    def connection_made(self, transport):
        self.transport = transport
        for i in range(self.times):
            self.prepare_command()
            self.device.num_packets += 1
            self.transport.sendto(self.command)
        self.device.num_commands += 1
        self.transport.close()  # Queue up the transport to be closed once tx buffers are cleared.

    def datagram_received(self, data, addr):
        logger.info("SendCommandProtocol - Received response?!")

    def error_received(self, exc):
        logger.error("Error received:", exc)

    def connection_lost(self, exc):
        self.on_close.set_result(True)


class StatusProtocol:
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
        # logger.info("datagram_received")
        asyncio.ensure_future(self.network_controller.async_on_status(data, addr))
        # self.network_controller.on_status(Device(data, addr))


class NetworkController:
    def __init__(self) -> None:
        # Device name -> Device object
        self.devices = {}
        self.status_transport = None
        self.status_protocol = None
        self.on_new_device = []
        self.on_device_update = []

    async def async_on_status(self, data, addr):
        device_update = Device(data, addr)
        aws = []
        if device_update.name not in self.devices:
            # logger.info(f"New expert device: {device_update}")
            self.devices[device_update.name] = device_update
            for listener in self.on_new_device:
                aws.append(listener(device_update))
        else:
            new_state = self.devices[device_update.name].update(device_update)
            # if new_state:
            #     logger.info(f"Expert device has update w/ new state: {device_update}")
            for listener in self.on_device_update:
                aws.append(listener(self.devices[device_update.name], new_state))
        await asyncio.gather(*aws)


    def on_status(self, device_update):
        if device_update.name not in self.devices:
            logger.info(f"New expert device: {device_update}")
            self.devices[device_update.name] = device_update
            for listener in self.on_new_device:
                listener(device_update)
        else:
            new_state = self.devices[device_update.name].update(device_update)
            if new_state:
                logger.info(f"Expert device has update w/ new state: {device_update}")
            for listener in self.on_device_update:
                listener(self.devices[device_update.name], new_state)

    async def listen(self):
        """Creates a UDP listener for Devialet status messages."""
        logger.info("Starting Devialet UDP Status Listening Service")
        loop = asyncio.get_running_loop()
        (
            self.status_transport,
            self.status_protocol,
        ) = await loop.create_datagram_endpoint(
            lambda: StatusProtocol(self),
            allow_broadcast=True,
            local_addr=("0.0.0.0", STATUS_PORT),
            family=socket.AF_INET,
        )

    async def close(self):
        """Stops the UDP listener."""
        if self.status_transport:
            logger.info("Stopped Devialet UDP Status Listening Service")
            self.status_transport.close()
            self.status_transport = None
            self.status_protocol = None

    def add_listener_on_new_device(self, callable):
        self.on_new_device.append(callable)

    def add_listener_on_device_update(self, callable):
        self.on_device_update.append(callable)

    def get_devices(self):
        return [v for v in self.devices.values()]


async def test_on_new_device(device):
    print(f"New device: {device}")
    # await device.async_turn_on()
    # for v in range(0, 235):
    #     await device.async_set_volume_float(v/255)
    #     await asyncio.sleep(0.1)
    
    # logger.info(f'Source {device.get_source()}')
    # logger.info(f'Sources {device.get_sources()}')
    
    # await asyncio.sleep(1)
    # await device.async_mute(True)
    # await asyncio.sleep(1)
    # await device.async_mute(False)
    # await asyncio.sleep(1)
    # await device.async_set_volume_float(115)


async def test_on_device_update(device, new_state):
    if new_state:
        print(f"Device update: {device}")
    # else:
    #     print(f"Device ping: {device.name}")


async def test_discovery():
    nc = NetworkController()
    nc.add_listener_on_device_update(test_on_device_update)
    nc.add_listener_on_new_device(test_on_new_device)
    await nc.listen()
    await asyncio.sleep(5)
    await nc.close()
    logger.info(f"Devices: {nc.get_devices()}")


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    asyncio.run(test_discovery())
