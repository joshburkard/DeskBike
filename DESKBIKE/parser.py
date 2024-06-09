"""Parser for DeskBike BLE devices"""

from __future__ import annotations

import asyncio
import dataclasses
import struct
from collections import namedtuple
from datetime import datetime
import logging

# from logging import Logger
from math import exp
from typing import Any, Callable, Tuple

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from .const import (
    BATT_100, BATT_0
)


READ_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class DeskBikeDevice:
    """Response data with information about the DeskBike device"""

    hw_version: str = ""
    sw_version: str = ""
    name: str = ""
    identifier: str = ""
    address: str = ""
    sensors: dict[str, str | float | None] = dataclasses.field(
        default_factory=lambda: {}
    )

# pylint: disable=too-many-locals
# pylint: disable=too-many-branches
class DeskBikeBluetoothDeviceData:
    """Data for DeskBike BLE sensors."""

    _event: asyncio.Event | None
    _command_data: bytearray | None

    def __init__(
        self,
        logger: Logger,
    ):
        super().__init__()
        self.logger = logger
        self.logger.debug("In Device Data")

    def decode(self, byte_frame : bytes ):

        frame_array = [int(x) for x in byte_frame]
        size = len(frame_array)

        for i in range(size-1, 0 , -1):
            tmp=frame_array[i]
            hibit1=(tmp&0x55)<<1
            lobit1=(tmp&0xAA)>>1
            tmp=frame_array[i-1]
            hibit=(tmp&0x55)<<1
            lobit=(tmp&0xAA)>>1
            frame_array[i]=0xff -(hibit1|lobit)
            frame_array[i-1]= 0xff -(hibit|lobit1)

        return frame_array

    def reverse_bytes(self, bytes : list):
        return (bytes[0] << 8) + bytes[1]

    def decode_position(self,decodedData,idx):
        return self.reverse_bytes(decodedData[idx:idx+2])

    async def _get_status(self, client: BleakClient, device: DeskBikeDevice) -> DeskBikeDevice:

        _LOGGER.debug("Getting Status")

        #Product Name
        data = await client.read_gatt_char("00002a00-0000-1000-8000-00805f9b34fb")
        decodedData = self.decode(data)
        product_name_code = data

        # Device Name
        devicename = await client.read_gatt_char("00002a00-0000-1000-8000-00805f9b34fb")
        device.sensors["devicename"] = str(devicename, 'utf-8')
        device.name = devicename

        # Battery Status
        batterybytes = await client.read_gatt_char("00002a19-0000-1000-8000-00805f9b34fb")
        battery = int.from_bytes(batterybytes, byteorder='little')
        device.sensors["battery"] = battery

        modelnumber = await client.read_gatt_char("00002a24-0000-1000-8000-00805f9b34fb")
        serialnumber = await client.read_gatt_char("00002a25-0000-1000-8000-00805f9b34fb")
        firmware = await client.read_gatt_char("00002a26-0000-1000-8000-00805f9b34fb")
        hardware = await client.read_gatt_char("00002a27-0000-1000-8000-00805f9b34fb")
        software = await client.read_gatt_char("00002a28-0000-1000-8000-00805f9b34fb")
        device.sensors["modelnumber"] = str(modelnumber, 'utf-8')
        device.sensors["serialnumber"] = str(serialnumber, 'utf-8')
        device.sensors["firmware"] = str(firmware, 'utf-8')
        device.sensors["hardware"] = str(hardware, 'utf-8')
        device.sensors["software"] = str(software, 'utf-8')



        _LOGGER.debug("Got Status")
        return device


    async def update_device(self, ble_device: BLEDevice) -> DeskBikeDevice:
        """Connects to the device through BLE and retrieves relevant data"""
        _LOGGER.debug("Update Device")
        client = await establish_connection(BleakClient, ble_device, ble_device.address)
        _LOGGER.debug("Got Client")
        #await client.pair()
        device = DeskBikeDevice()
        _LOGGER.debug("Made Device")

        device = await self._get_status(client, device)
        _LOGGER.debug("got Status")
        device.name = ble_device.address
        device.address = ble_device.address
        _LOGGER.debug("device.name: %s", device.name)
        _LOGGER.debug("device.address: %s", device.address)

        await client.disconnect()

        return device

