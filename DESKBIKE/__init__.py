"""Parser for DeskBike BLE advertisements."""
from __future__ import annotations
from homeassistant.core import HomeAssistant

from .parser import DeskBikeBluetoothDeviceData, DeskBikeDevice

__version__ = "0.0.7"

__all__ = ["DeskBikeBluetoothDeviceData", "DeskBikeDevice"]

_lastcsc01 = 0
_lastcsc02 = 0
# lastcsctime = datetime.now()