"""Constants for the DeskBike integration."""
from typing import Final

DOMAIN: Final = "deskbike"
DEFAULT_NAME: Final = "DeskBike"
DEFAULT_WEIGHT: Final = 70.0  # Default weight in kg

# BLE Characteristic UUIDs
CHAR_PRODUCT_NAME: Final = "00002a00-0000-1000-8000-00805f9b34fb"
CHAR_DEVICE_NAME: Final = "00002a00-0000-1000-8000-00805f9b34fb"
CHAR_MODEL_NUMBER: Final = "00002a24-0000-1000-8000-00805f9b34fb"
CHAR_SERIAL_NUMBER: Final = "00002a25-0000-1000-8000-00805f9b34fb"
CHAR_FIRMWARE: Final = "00002a26-0000-1000-8000-00805f9b34fb"
CHAR_HARDWARE: Final = "00002a27-0000-1000-8000-00805f9b34fb"
CHAR_SOFTWARE: Final = "00002a28-0000-1000-8000-00805f9b34fb"
CHAR_BATTERY: Final = "00002a19-0000-1000-8000-00805f9b34fb"
CHAR_CSC_MEASUREMENT: Final = "00002a5b-0000-1000-8000-00805f9b34fb"

# Calories calculation constants
# MET values for different cycling intensities
MET_LIGHT: Final = 4.0  # Light effort (<10 mph)
MET_MODERATE: Final = 6.0  # Moderate effort (10-12 mph)
MET_VIGOROUS: Final = 8.0  # Vigorous effort (12-14 mph)
MET_VERY_VIGOROUS: Final = 10.0  # Very vigorous effort (14-16 mph)
MET_RACING: Final = 12.0  # Racing/high intensity (>16 mph)