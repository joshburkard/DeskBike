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

global _lastcrankrevolution
global _lastcalories
global _lastcsctimestamp
_lastcrankrevolution = 0
_lastcalories = 0
_lastcsctimestamp = datetime.now()

global _dailycrankrevolution
global _dailycalories
global _dailymeters
_dailycrankrevolution = 0
_dailycalories = 0
_dailymeters = 0

READ_UUID = "00002a00-0000-1000-8000-00805f9b34fb"
CSC_CHARACTERISTIC_UUID_READ = "00002a5b-0000-1000-8000-00805f9b34fb"
CSC_CHARACTERISTIC_UUID_WRITE = "00002a55-0000-1000-8000-00805f9b34fb"
WRITE_VALUE = b"\x50"

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

    def notification_handler(self, _: Any, data: bytearray) -> None:
        """Helper for command events"""

        # device.sensors["cscmeasurement"] = data

        self._command_data = data

        # self._lastcrankrevolution = self._csccrankrevolution

        #hexstring = ''.join( format(x, '02x') for x in data )
        #csccrankrevolutionhex = "0x{0}{1}".format( hexstring[4:6], hexstring[2:4] )

        #newcsccrankrevolution = int( csccrankrevolutionhex, 0)
        #self._csccrankrevolution = newcsccrankrevolution

        if self._event is None:
            return
        self._event.set()

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

        if 1 == 0:
            for service in client.services:
                _LOGGER.debug("[Service] %s", service)
                for char in service.characteristics:
                    _LOGGER.debug("[characteristic] %s", char)
                    if "read" in char.properties:
                        try:
                            value = await client.read_gatt_char(char.uuid)
                            extra = f", Value: {value}"
                        except Exception as e:
                            extra = f", Error: {e}"
                    else:
                        extra = ""
                    _LOGGER.debug("[value] %s", extra)

        device = await self._get_ble_notify(client, device)

        await client.disconnect()

        return device








    async def _get_ble_notify(self, client: BleakClient, device: DeskBikeDevice) -> DeskBikeDevice:

        self._event = asyncio.Event()
        try:
            await client.start_notify(
                CSC_CHARACTERISTIC_UUID_READ, self.notification_handler
            )
        except:
            _LOGGER.debug("_get_radon Bleak error 1")

        await client.write_gatt_char(CSC_CHARACTERISTIC_UUID_WRITE, WRITE_VALUE)

        # Wait for up to fice seconds to see if a
        # callback comes in.
        try:
            await asyncio.wait_for(self._event.wait(), 10)
        except asyncio.TimeoutError:
            _LOGGER.debug("Timeout getting command data.")
            self.logger.warn("Timeout getting command data.")
        except:
            _LOGGER.debug("_get_radon Bleak error 2")
            self.logger.warn("_get_radon Bleak error 2")

        await client.stop_notify(CSC_CHARACTERISTIC_UUID_READ)

        _LOGGER.debug( "CSC datas: {0}".format( self._command_data ) )

        if self._command_data is not None:
            _LOGGER.debug( "CSC datas 0-1:  {0}".format( self._command_data[0:1] ) )
            _LOGGER.debug( "CSC datas 0-1: {0}".format( int.from_bytes( self._command_data[0:1] , byteorder='little')  ) )

            hexstring = ''.join( format(x, '02x') for x in self._command_data )
            csccrankrevolutionhex = "0x{0}{1}".format( hexstring[4:6], hexstring[2:4] )
            csccalorieshex = "0x{0}{1}".format( hexstring[12:14], hexstring[10:12] )
            _LOGGER.debug( "hexstring:  {0}".format( hexstring ) )
            _LOGGER.debug( "csccalorieshex:  {0}".format( csccalorieshex ) )

            csctimestamp = datetime.now()

            csccrankrevolution = int( csccrankrevolutionhex, 0)
            csccalories = int( csccalorieshex, 0)
            # device.sensors["csctimestamp"] = csctimestamp

            device.sensors["csccrankrevolution"] = csccrankrevolution
            device.sensors["csccalories"] = csccalories

            # check if it's midnight with a tolerance
            # reset daily counters
            #global _dailycrankrevolution
            #global _dailycalories
            #global _dailymeters
            #now = datetime.datetime.now()
            #time1 = now.replace(hour=0, minute=0, second=10, microsecond=0)
            # zero = timedelta(seconds = secs+mins*60+hrs*3600)
            #st = csctimestamp - zero # this take me to 0 hours.
            #time1 = st + timedelta(seconds=60)
            #if csctimestamp >= st or csctimestamp <= time1:
            #    _dailycrankrevolution = 0
            #    _dailycalories = 0
            #    _dailymeters = 0
            # end check if it's midnight with a tolerance

            global _lastcsctimestamp
            difcsctimestamp = csctimestamp - _lastcsctimestamp
            device.sensors["difcsctimestamp"] = difcsctimestamp
            _lastcsctimestamp = csctimestamp

            global _lastcrankrevolution
            if _lastcrankrevolution == 0:
                dif_crank_revolution = 0
            elif csccrankrevolution == _lastcrankrevolution:
                dif_crank_revolution = 0
            elif csccrankrevolution > _lastcrankrevolution:
                dif_crank_revolution = csccrankrevolution - _lastcrankrevolution
            else:
                dif_crank_revolution = csccrankrevolution - _lastcrankrevolution + 65536
            device.sensors["csc_dif_crank"] = dif_crank_revolution
            _lastcrankrevolution = csccrankrevolution

            global _lastcalories
            if _lastcalories == 0:
                dif_calories = 0
            elif csccalories == _lastcalories:
                dif_calories = 0
            elif csccalories > _lastcalories:
                dif_calories = csccalories - _lastcalories
            else:
                dif_calories = csccalories - _lastcalories + 65536
            device.sensors["csc_dif_calories"] = dif_calories
            _lastcalories = csccalories

            #_dailycrankrevolution = _dailycrankrevolution + cscdifcrank
            #_dailymeters = _dailycrankrevolution * 2.5
            #_dailycalories = _dailycalories + cscdifkcal


            device.sensors["cscmeasurement"] = hexstring


        else:
            device.sensors["cscmeasurement"] = None

        self._command_data = None
        return device
