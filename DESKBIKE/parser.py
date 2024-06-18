"""Parser for DeskBike BLE devices"""

from __future__ import annotations

import asyncio
import dataclasses
import struct
from collections import namedtuple
from datetime import datetime, timedelta
import logging

import os.path
import json

# from logging import Logger
from math import exp
from typing import Any, Callable, Tuple

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfo,
    async_discovered_service_info,
)

# from .const import (
#     BATT_100, BATT_0
# )

global _last_crank_revolution
global _last_csc_timestamp
global _last_timestamp
global _last_save_timestamp
_last_crank_revolution = 0
_last_csc_timestamp = 0
_last_timestamp = datetime.now()
_last_save_timestamp = datetime.now()

global _daily_crank_revolution
global _daily_distance
global _total_crank_revolution
global _total_distance
_daily_crank_revolution = 0
_daily_distance = 0
_total_crank_revolution = 0
_total_distance = 0

global _daily_active_time
global _total_active_time
_daily_active_time = 0
_total_active_time = 0

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

        # self._last_crank_revolution = self._csc_crank_revolution

        #hexstring = ''.join( format(x, '02x') for x in data )
        #csc_crank_revolution_hex = "0x{0}{1}".format( hexstring[4:6], hexstring[2:4] )

        #newcsc_crank_revolution = int( csc_crank_revolution_hex, 0)
        #self._csc_crank_revolution = newcsc_crank_revolution

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
        device.name = ble_device.name
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

        global _daily_crank_revolution
        global _daily_distance
        global _daily_active_time
        global _total_crank_revolution
        global _total_distance
        global _total_active_time
        global _last_timestamp
        global _last_crank_revolution
        global _last_save_timestamp

        try:
            rssi = device.rssi
            _LOGGER.debug( f"rssi: {rssi}")
        except Exception as err:
            _LOGGER.debug(f"error: {err}")

        # if ( ( _total_active_time == 0 ) and ( _total_crank_revolution == 0 ) ):
        if _total_crank_revolution == 0:
            _LOGGER.debug("initializing datas")
            if os.path.isfile( r"/config/custom_components/deskbike/datas.json" ):
                _LOGGER.debug("datafile found")
                f = open( r"/config/custom_components/deskbike/datas.json" , "r")
                filecontent = f.read()
                f.close()
                jsondatas = json.loads(filecontent)
                if "total_crank_revolution" in jsondatas:
                    _LOGGER.debug("total_crank_revolution found")
                    _total_crank_revolution = jsondatas["total_crank_revolution"]
                else:
                    _total_crank_revolution = 0

                if "total_active_time" in jsondatas:
                    _LOGGER.debug("total_active_time found")
                    _total_active_time = jsondatas["total_active_time"]
                else:
                    _total_active_time = 0

                if "daily_crank_revolution" in jsondatas:
                    _LOGGER.debug("daily_crank_revolution found")
                    _daily_crank_revolution = jsondatas["daily_crank_revolution"]
                else:
                    _daily_crank_revolution = 0

                if "daily_active_time" in jsondatas:
                    _LOGGER.debug("daily_active_time found")
                    _daily_active_time = jsondatas["daily_active_time"]
                else:
                    _daily_active_time = 0
            else:
                _LOGGER.debug("datafile not found")
                _total_crank_revolution = 0
                _total_active_time = 0
                _daily_crank_revolution = 0
                _daily_active_time = 0


        _LOGGER.debug( f"_total_crank_revolution: {_total_crank_revolution}")
        _LOGGER.debug( f"_total_active_time:      {_total_active_time}")
        _LOGGER.debug( f"_daily_crank_revolution: {_daily_crank_revolution}")
        _LOGGER.debug( f"_daily_active_time:      {_daily_active_time}")

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

        try:

            if self._command_data is not None:
                _LOGGER.debug( "CSC datas 0-1:  {0}".format( self._command_data[0:1] ) )
                # _LOGGER.debug( "CSC datas 0-1: {0}".format( int.from_bytes( self._command_data[0:1] , byteorder='little')  ) )

                hexstring = ''.join( format(x, '02x') for x in self._command_data )
                # device.sensors["cscmeasurement"] = hexstring
                csc_crank_revolution_hex = "0x{0}{1}".format( hexstring[4:6], hexstring[2:4] )
                csc_timestamp_hex = "0x{0}{1}".format( hexstring[12:14], hexstring[10:12] )

                now = datetime.now()

                csc_crank_revolution = int( csc_crank_revolution_hex, 0)
                csc_timestamp = int( csc_timestamp_hex, 0)

                # check if it's midnight with a tolerance
                # reset daily counters
                now = datetime.now()
                time0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
                time1 = now.replace(hour=0, minute=0, second=10, microsecond=0)
                # st = now.replace(hour=0, minute=0, second=0, microsecond=0)
                #zero = timedelta(seconds = secs+mins*60+hrs*3600)
                #st = now - zero # this take me to 0 hours.
                #time1 = st + timedelta(seconds=60)
                if now >= time1 and _last_timestamp <= time1:
                    _daily_crank_revolution = 0
                    _daily_distance = 0
                    _daily_active_time = 0
                # end check if it's midnight with a tolerance

                dif_timestamp = now - _last_timestamp
                dif_timestamp_seconds = dif_timestamp.total_seconds()
                # device.sensors["dif_timestamp"] = dif_timestamp_seconds
                _last_timestamp = now

                _LOGGER.debug( f"_last_crank_revolution: {_last_crank_revolution}" )
                _LOGGER.debug( f"csc_crank_revolution:   {csc_crank_revolution}" )
                if _last_crank_revolution == 0:
                    dif_crank_revolution = 0
                elif csc_crank_revolution == _last_crank_revolution:
                    dif_crank_revolution = 0
                elif csc_crank_revolution > _last_crank_revolution:
                    dif_crank_revolution = csc_crank_revolution - _last_crank_revolution
                else:
                    dif_crank_revolution = csc_crank_revolution - _last_crank_revolution + 65536

                if dif_crank_revolution > 50:
                    dif_crank_revolution = 0

                # device.sensors["csc_dif_crank"] = dif_crank_revolution
                _last_crank_revolution = csc_crank_revolution
                _LOGGER.debug( f"dif_crank_revolution:   {dif_crank_revolution}" )
                _LOGGER.debug( f"_last_crank_revolution: {_last_crank_revolution}" )

                #global _last_csc_timestamp
                #if _last_csc_timestamp == 0:
                #    dif_csc_timestamp = 0
                #elif csc_timestamp == _last_csc_timestamp:
                #    dif_csc_timestamp = 0
                #elif csc_timestamp > _last_csc_timestamp:
                #    dif_csc_timestamp = csc_timestamp - _last_csc_timestamp
                #else:
                #    dif_csc_timestamp = csc_timestamp - _last_csc_timestamp + 65536
                # device.sensors["csc_dif_csc_timestamp"] = dif_csc_timestamp
                #_last_csc_timestamp = csc_timestamp

                if dif_crank_revolution != 0:
                    _daily_crank_revolution = _daily_crank_revolution + dif_crank_revolution
                    _total_crank_revolution = _total_crank_revolution + dif_crank_revolution
                device.sensors["daily_crank_revolution"] = _daily_crank_revolution
                device.sensors["total_crank_revolution"] = _total_crank_revolution

                _daily_distance = _daily_crank_revolution * 2.5 / 1000
                device.sensors["daily_distance"] = _daily_distance

                _total_distance = _total_crank_revolution * 2.5 / 1000
                device.sensors["total_distance"] = _total_distance


                if dif_crank_revolution > 0 and dif_timestamp_seconds > 0:
                    _daily_active_time = _daily_active_time + dif_timestamp_seconds
                    _total_active_time = _total_active_time + dif_timestamp_seconds
                    speed = dif_crank_revolution * 2.5 / dif_timestamp_seconds * 3600 / 1000
                else:
                    speed = 0
                device.sensors["current_speed"] = speed
                device.sensors["daily_active_time"] = _daily_active_time
                device.sensors["total_active_time"] = _total_active_time

                # save to file
                dif_save_timestamp = now - _last_save_timestamp
                dif_save_timestamp_seconds = dif_save_timestamp.total_seconds()
                if dif_save_timestamp_seconds > 60:
                    _LOGGER.debug("we will save now the current datas to the file")
                    _last_save_timestamp = now

                    datas = {
                        "total_crank_revolution" : _total_crank_revolution,
                        "total_active_time" : _total_active_time,
                        "daily_crank_revolution" : _daily_crank_revolution,
                        "daily_active_time" : _daily_active_time,
                    }
                    jsondatas = json.dumps(datas)
                    _LOGGER.debug(jsondatas)
                    f = open( r"/config/custom_components/deskbike/datas.json" ,"w")
                    f.write( jsondatas )
                    f.close()
                    _LOGGER.debug("saved data to file")
        except Exception as err:
            _LOGGER.debug(f"error: {err}")

        self._command_data = None
        return device
