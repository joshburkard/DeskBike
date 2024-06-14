"""Parser for DeskBike BLE advertisements."""
from __future__ import annotations
from homeassistant.core import HomeAssistant

from .parser import DeskBikeBluetoothDeviceData, DeskBikeDevice

__version__ = "0.0.5"

__all__ = ["DeskBikeBluetoothDeviceData", "DeskBikeDevice"]

