"""Support for DeskBike sensors."""
from __future__ import annotations

import asyncio
import logging
import struct
from datetime import datetime, timedelta
from typing import Any

from bleak import BleakClient
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_NAME,
    PERCENTAGE,
    LENGTH_KILOMETERS,
    SPEED_KILOMETERS_PER_HOUR,
    TIME_SECONDS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CHAR_PRODUCT_NAME,
    CHAR_DEVICE_NAME,
    CHAR_MODEL_NUMBER,
    CHAR_SERIAL_NUMBER,
    CHAR_FIRMWARE,
    CHAR_HARDWARE,
    CHAR_SOFTWARE,
    CHAR_BATTERY,
    CHAR_CSC_MEASUREMENT,
    DEFAULT_WEIGHT,
    MET_LIGHT,
    MET_MODERATE,
    MET_VIGOROUS,
    MET_VERY_VIGOROUS,
    MET_RACING,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="speed",
        name="Speed",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        icon="mdi:speedometer",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="distance",
        name="Total Distance",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:map-marker-distance",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="daily_distance",
        name="Daily Distance",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:map-marker-distance",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="cadence",
        name="Cadence",
        native_unit_of_measurement="rpm",
        icon="mdi:rotate-right",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="battery",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        icon="mdi:battery",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="last_active",
        name="Last Active",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="daily_active_time",
        name="Daily Active Time",
        native_unit_of_measurement=TIME_SECONDS,
        icon="mdi:timer-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="total_active_time",
        name="Total Active Time",
        native_unit_of_measurement=TIME_SECONDS,
        icon="mdi:timer",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="daily_calories",
        name="Daily Calories Burned",
        native_unit_of_measurement="kcal",
        icon="mdi:fire",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="total_calories",
        name="Total Calories Burned",
        native_unit_of_measurement="kcal",
        icon="mdi:fire",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

class DeskBikeSensor(CoordinatorEntity, SensorEntity):
    """Representation of a DeskBike sensor."""

    def __init__(
        self,
        coordinator: DeskBikeDataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._config_entry = config_entry
        self._attr_has_entity_name = True

        # Set unique_id
        self._attr_unique_id = f"{config_entry.data[CONF_ADDRESS]}_{description.key}"

        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.data[CONF_ADDRESS])},
            name=config_entry.data[CONF_NAME],
            manufacturer="DeskBike",
            model=coordinator.device_info.get("model", "DeskBike"),
            sw_version=coordinator.device_info.get("firmware_version"),
            hw_version=coordinator.device_info.get("hardware_version"),
        )

    @property
    def native_value(self) -> float | str | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        value = self.coordinator.data.get(self.entity_description.key)
        if value is not None:
            if isinstance(value, (int, float)):
                if self.entity_description.key in ["distance", "daily_distance"]:
                    return round(value, 2)
                elif self.entity_description.key in ["speed", "cadence"]:
                    return round(value, 1)
                elif self.entity_description.key in ["daily_calories", "total_calories"]:
                    return round(value, 1)
                return value
            return value
        return None

class DeskBikeDiagnosticSensor(DeskBikeSensor):
    """Representation of a DeskBike diagnostic sensor."""

    def __init__(
        self,
        coordinator: DeskBikeDataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: str,
        value: str,
    ) -> None:
        """Initialize the diagnostic sensor."""
        super().__init__(
            coordinator,
            config_entry,
            SensorEntityDescription(
                key=f"diagnostic_{description.lower().replace(' ', '_')}",
                name=description,
                icon="mdi:information",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        )
        self._value = value

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self._value

class DeskBikeDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching DeskBike data."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        address: str,
        name: str,
    ) -> None:
        """Initialize global DeskBike data updater."""
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=timedelta(seconds=30),
        )
        self.address = address
        self._weight = DEFAULT_WEIGHT
        self._client: BleakClient | None = None
        self._connected = False
        self.device_info = {}
        self._last_wheel_rev = 0
        self._last_wheel_event = 0
        self._last_crank_rev = 0
        self._last_crank_event = 0
        self._wheel_circumference = 2.096  # Meters - typical 700c wheel
        self._last_activity_check = None
        self._last_active = None
        self._daily_distance_date = dt_util.now().date()
        self._activity_start_time = None
        self._reconnect_task = None
        self._data = {
            "speed": 0.0,
            "distance": 0.0,
            "daily_distance": 0.0,
            "cadence": 0.0,
            "battery": 0,
            "last_active": None,
            "daily_active_time": 0,
            "total_active_time": 0,
            "daily_calories": 0.0,
            "total_calories": 0.0,
            "is_active": False,
            "is_connected": False,
        }
        self._connection_lock = asyncio.Lock()
        self._daily_reset_time = dt_util.start_of_local_day()

    @property
    def weight(self) -> float:
        """Get the current weight setting."""
        return self._weight

    @weight.setter
    def weight(self, value: float) -> None:
        """Set the current weight setting."""
        self._weight = value

    def _calculate_calories(self, speed: float, time_diff: float) -> float:
        """Calculate calories burned based on speed and time.

        Args:
            speed: Speed in km/h
            time_diff: Time difference in seconds

        Returns:
            Calories burned in kcal
        """
        # Convert time from seconds to hours
        hours = time_diff / 3600

        # Select MET based on speed
        if speed < 16:  # 10 mph
            met = MET_LIGHT
        elif speed < 19:  # 12 mph
            met = MET_MODERATE
        elif speed < 22.5:  # 14 mph
            met = MET_VIGOROUS
        elif speed < 25.7:  # 16 mph
            met = MET_VERY_VIGOROUS
        else:
            met = MET_RACING

        # Calculate calories: MET * weight * time(hours)
        return met * self.weight * hours

    def _check_activity_timeout(self) -> None:
        """Check if device is inactive and reset speed if needed."""
        now = dt_util.now()
        if self._last_activity_check is None:
            self._last_activity_check = now
            return

        # If no activity for 3 seconds, set speed and status to 0
        if (now - self._last_activity_check).total_seconds() > 3:
            self._data["speed"] = 0.0
            self._data["cadence"] = 0.0
            self._data["is_active"] = False

            # Just reset the activity start time
            self._activity_start_time = None

    def _check_daily_reset(self) -> None:
        """Check if we need to reset daily values."""
        now = dt_util.now()
        if now > self._daily_reset_time + timedelta(days=1):
            self._data["daily_distance"] = 0.0
            self._data["daily_active_time"] = 0
            self._data["daily_calories"] = 0.0
            self._daily_reset_time = dt_util.start_of_local_day()

    def _notification_handler(self, _: int, data: bytearray) -> None:
        """Handle incoming CSC measurement notifications."""
        try:
            flags = data[0]
            wheel_rev_present = bool(flags & 0x01)
            crank_rev_present = bool(flags & 0x02)
            offset = 1

            activity_detected = False
            now = dt_util.now()

            if wheel_rev_present:
                wheel_revs, wheel_event = struct.unpack_from("<LH", data, offset)
                if self._last_wheel_event != 0:
                    wheel_event_diff = (wheel_event - self._last_wheel_event) & 0xFFFF
                    if wheel_event_diff > 0:
                        time_diff = wheel_event_diff / 1024.0
                        rev_diff = wheel_revs - self._last_wheel_rev
                        distance = rev_diff * self._wheel_circumference
                        speed = (distance / time_diff) * 3.6

                        if speed > 0:
                            activity_detected = True

                        self._data["speed"] = round(speed, 1)
                        distance_km = distance / 1000
                        self._data["distance"] = round(self._data["distance"] + distance_km, 2)
                        self._data["daily_distance"] = round(self._data["daily_distance"] + distance_km, 2)

                self._last_wheel_rev = wheel_revs
                self._last_wheel_event = wheel_event
                offset += 6

            if crank_rev_present:
                crank_revs, crank_event = struct.unpack_from("<HH", data, offset)
                if self._last_crank_event != 0:
                    crank_event_diff = (crank_event - self._last_crank_event) & 0xFFFF
                    if crank_event_diff > 0:
                        time_diff = crank_event_diff / 1024.0
                        rev_diff = crank_revs - self._last_crank_rev
                        cadence = (rev_diff / time_diff) * 60
                        self._data["cadence"] = round(cadence, 1)
                        if cadence > 0:
                            activity_detected = True

                self._last_crank_rev = crank_revs
                self._last_crank_event = crank_event

            # Update activity status and timing
            if activity_detected:
                self._last_active = now
                self._data["last_active"] = self._last_active
                self._last_activity_check = now
                self._data["is_active"] = True

                # Start or update activity timing
                if self._activity_start_time is None:
                    self._activity_start_time = now

                # Always add 1 second to both daily and total time during activity
                self._data["daily_active_time"] += 1
                self._data["total_active_time"] += 1

                # Calculate and add calories if speed is available
                if self._data["speed"] > 0:
                    calories_burned = self._calculate_calories(self._data["speed"], 1)  # 1 second of activity
                    self._data["daily_calories"] += calories_burned
                    self._data["total_calories"] += calories_burned
            else:
                self._check_activity_timeout()

            self._check_daily_reset()
            self.async_set_updated_data(self._data.copy())

        except Exception as e:
            _LOGGER.error("Error processing CSC notification: %s", e)

    async def _async_connect(self) -> None:
        """Connect to the DeskBike device with retry mechanism."""
        if self._connected:
            return

        async with self._connection_lock:
            if self._connected:
                return

            max_retries = 3
            retry_delay = 2

            for attempt in range(max_retries):
                try:
                    if self._client:
                        try:
                            await self._client.disconnect()
                        except Exception:
                            pass
                        self._client = None

                    self._client = BleakClient(self.address, disconnected_callback=self._handle_disconnection)
                    await asyncio.sleep(0.5)
                    await self._client.connect()
                    self._connected = True
                    self._data["is_connected"] = True

                    # Restore saved values
                    try:
                        for key in ["distance", "total_active_time", "total_calories"]:
                            last_state = await self.hass.helpers.restore_state.async_get_last_state(
                                "sensor",
                                f"{self.address}_{key}"
                            )
                            if last_state is not None and last_state.state.replace(".", "").isdigit():
                                self._data[key] = float(last_state.state)
                    except Exception as e:
                        _LOGGER.debug("Error restoring saved values: %s", e)

                    # Read device info and subscribe to notifications
                    try:
                        battery_bytes = await self._client.read_gatt_char(CHAR_BATTERY)
                        self._data["battery"] = int.from_bytes(battery_bytes, byteorder='little')
                    except Exception as e:
                        _LOGGER.debug("Error reading battery level: %s", e)

                    if not self.device_info:
                        await self._read_device_info()

                    await self._client.start_notify(
                        CHAR_CSC_MEASUREMENT,
                        self._notification_handler,
                    )

                    _LOGGER.info("Connected to DeskBike")
                    return

                except Exception as e:
                    self._connected = False
                    self._data["is_connected"] = False
                    if self._client:
                        try:
                            await self._client.disconnect()
                        except Exception:
                            pass
                        self._client = None

                    if attempt < max_retries - 1:
                        _LOGGER.warning(
                            "Failed to connect to DeskBike (attempt %d/%d): %s. Retrying in %d seconds...",
                            attempt + 1,
                            max_retries,
                            str(e),
                            retry_delay
                        )
                        await asyncio.sleep(retry_delay)
                    else:
                        _LOGGER.error(
                            "Failed to connect to DeskBike after %d attempts: %s",
                            max_retries,
                            str(e)
                        )
                        raise

    def _handle_disconnection(self, client: BleakClient) -> None:
        """Handle disconnection event."""
        self._connected = False
        self._data["is_connected"] = False
        self._data["is_active"] = False
        self.async_set_updated_data(self._data.copy())

        # Schedule reconnection
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._async_handle_reconnect())

    async def _async_handle_reconnect(self) -> None:
        """Handle reconnection attempts."""
        while not self._connected:
            try:
                _LOGGER.info("Attempting to reconnect to DeskBike...")
                await self._async_connect()
                if self._connected:
                    _LOGGER.info("Successfully reconnected to DeskBike")
                    break
            except Exception as e:
                _LOGGER.error("Reconnection attempt failed: %s", e)
                await asyncio.sleep(5)  # Wait before next attempt

    async def _read_device_info(self) -> None:
        """Read device information characteristics."""
        try:
            for char_uuid in [
                CHAR_PRODUCT_NAME,
                CHAR_DEVICE_NAME,
                CHAR_MODEL_NUMBER,
                CHAR_SERIAL_NUMBER,
                CHAR_FIRMWARE,
                CHAR_HARDWARE,
                CHAR_SOFTWARE,
            ]:
                try:
                    value = await self._client.read_gatt_char(char_uuid)
                    value_str = value.decode('utf-8').strip()
                    if char_uuid == CHAR_MODEL_NUMBER:
                        self.device_info["model"] = value_str
                    elif char_uuid == CHAR_SERIAL_NUMBER:
                        self.device_info["serial_number"] = value_str
                    elif char_uuid == CHAR_FIRMWARE:
                        self.device_info["firmware_version"] = value_str
                    elif char_uuid == CHAR_HARDWARE:
                        self.device_info["hardware_version"] = value_str
                    elif char_uuid == CHAR_SOFTWARE:
                        self.device_info["software_version"] = value_str
                    elif char_uuid in [CHAR_PRODUCT_NAME, CHAR_DEVICE_NAME]:
                        self.device_info["name"] = value_str
                except Exception as e:
                    _LOGGER.debug("Error reading characteristic %s: %s", char_uuid, e)
        except Exception as e:
            _LOGGER.warning("Failed to read device info: %s", e)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data from DeskBike."""
        try:
            if not self._connected:
                try:
                    await self._async_connect()
                except Exception as connect_error:
                    _LOGGER.error("Failed to connect to DeskBike: %s", connect_error)
                    if self._data:
                        return self._data
                    raise
            return self._data
        except Exception as error:
            await self._async_disconnect()
            raise Exception(f"Error fetching DeskBike data: {error}")

    async def _async_disconnect(self) -> None:
        """Disconnect from the DeskBike device."""
        if self._client and self._connected:
            try:
                await self._client.stop_notify(CHAR_CSC_MEASUREMENT)
            except Exception as e:
                _LOGGER.debug("Error stopping notifications: %s", e)

            try:
                await self._client.disconnect()
            except Exception as e:
                _LOGGER.debug("Error disconnecting: %s", e)
            finally:
                self._connected = False
                self._data["is_connected"] = False
                self._client = None

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        await self._async_disconnect()
        await super().async_shutdown()

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DeskBike sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Add regular sensors
    for description in SENSOR_TYPES:
        entities.append(DeskBikeSensor(coordinator, entry, description))

    # Add diagnostic sensors if available
    device_info = coordinator.device_info
    if device_info:
        for char_name, info_key in [
            ("Model Number", "model"),
            ("Serial Number", "serial_number"),
            ("Firmware Version", "firmware_version"),
            ("Hardware Version", "hardware_version"),
            ("Software Version", "software_version"),
        ]:
            if info_key in device_info and device_info[info_key]:
                entities.append(
                    DeskBikeDiagnosticSensor(
                        coordinator,
                        entry,
                        char_name,
                        device_info[info_key]
                    )
                )

    async_add_entities(entities)

    # Store coordinator in hass.data for cleanup
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator