"""Support for DeskBike sensors."""
from __future__ import annotations

import asyncio
import logging
import struct
from datetime import datetime, timedelta
from typing import Any

from bleak import BleakClient
from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
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
    DEFAULT_RESISTANCE,
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
        icon="mdi:timer-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="total_active_time",
        name="Total Active Time",
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
    SensorEntityDescription(
        key="daily_crank_rotations",
        name="Daily Crank Rotations",
        native_unit_of_measurement="",
        icon="mdi:rotate-right",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="total_crank_rotations",
        name="Total Crank Rotations",
        native_unit_of_measurement="",
        icon="mdi:rotate-right",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

def format_seconds_to_time(seconds: int) -> str:
    """Format seconds to d.HH:mm:ss format."""
    if seconds is None:
        return None

    days = seconds // (24 * 3600)
    remaining = seconds % (24 * 3600)
    hours = remaining // 3600
    remaining %= 3600
    minutes = remaining // 60
    remaining %= 60

    if days > 0:
        result = f"{days}.{hours:02d}:{minutes:02d}:{remaining:02d}"
    else:
        result = f"{hours:02d}:{minutes:02d}:{remaining:02d}"
    return result

class DeskBikeSensor(CoordinatorEntity, RestoreSensor):
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
        self._attr_unique_id = f"{config_entry.data[CONF_ADDRESS]}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.data[CONF_ADDRESS])},
            name=config_entry.data[CONF_NAME],
            manufacturer="DeskBike",
            model=coordinator.device_info.get("model", "DeskBike"),
            sw_version=coordinator.device_info.get("firmware_version"),
            hw_version=coordinator.device_info.get("hardware_version"),
            connections={("bluetooth", config_entry.data[CONF_ADDRESS])},
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        # Restore previous state for total/cumulative sensors
        if (last_state := await self.async_get_last_state()) is not None:
            # Only restore certain sensors that should persist
            if self.entity_description.key in [
                "distance",
                "total_active_time",
                "total_calories",
                "total_crank_rotations",
            ]:
                try:
                    if last_state.state not in (None, "unknown", "unavailable"):
                        self.coordinator._data[self.entity_description.key] = float(last_state.state)
                        _LOGGER.debug(
                            "Restored %s state: %s",
                            self.entity_description.key,
                            last_state.state
                        )
                except (ValueError, TypeError) as err:
                    _LOGGER.debug(
                        "Could not restore %s state: %s",
                        self.entity_description.key,
                        err
                    )

    @property
    def native_value(self) -> float | str | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        value = self.coordinator.data.get(self.entity_description.key)
        if value is not None:

            if isinstance(value, (int, float)):
                if self.entity_description.key in ["daily_distance"]:
                    return round(value, 2)
                elif self.entity_description.key in ["distance"]:
                    return round(value, 1)
                elif self.entity_description.key in ["speed", "cadence"]:
                    return round(value, 1)
                elif self.entity_description.key in ["daily_calories", "total_calories"]:
                    return round(value, 1)

                return value
            return value
        return None

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        if self.entity_description.key in ["daily_active_time", "total_active_time"]:
            if self.native_value is not None:
                return format_seconds_to_time(int(self.native_value))
        return str(self.native_value) if self.native_value is not None else None

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
        self._resistance = DEFAULT_RESISTANCE
        self._client: BleakClient | None = None
        self._connected = False
        self.device_info = {}
        self._last_wheel_rev = 0
        self._last_wheel_event = 0
        self._last_crank_rev = 0
        self._last_crank_event = 0
        self._wheel_circumference = 2.096
        self._last_activity_check = None
        self._last_active = None
        self._activity_start_time = None
        self._reconnect_task = None
        self._last_connection_attempt = None
        self._retry_interval = timedelta(minutes=1)
        self._connection_lock = asyncio.Lock()
        self._force_reconnect = False  # Add this flag

        # Define sensors
        self._daily_sensors = [
            "daily_distance",
            "daily_active_time",
            "daily_calories",
            "daily_crank_rotations"
        ]

        self._persistent_sensors = [
            "total_active_time",
            "total_crank_rotations",
            "distance",
            "total_calories"
        ]

        # Initialize data structure
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
            "daily_crank_rotations": 0,
            "total_crank_rotations": 0,
        }

        self._last_saved_daily_values = None

    def _should_attempt_connection(self) -> bool:
        """Determine if connection attempt should be made."""
        now = dt_util.utcnow()

        # Always attempt if forced reconnect is set
        if self._force_reconnect:
            self._force_reconnect = False  # Reset flag
            self._connection_attempts = 0   # Reset counter
            return True

        # If we're already connected, no need to attempt
        if self._connected:
            return False

        # If we have recent activity, attempt connection
        if self._last_activity_time and (now - self._last_activity_time) < self._activity_timeout:
            return True

        # If we haven't exceeded max attempts, try anyway
        if self._connection_attempts < self._max_connection_attempts:
            self._connection_attempts += 1
            return True

        # Otherwise, don't attempt connection
        return False

    async def _save_persistent_data(self) -> None:
        """Save persistent sensor values including daily values."""
        try:
            # Don't save if we haven't properly initialized yet
            if any(self._data[key] is None for key in self._daily_sensors + self._persistent_sensors):
                _LOGGER.debug("Skipping save as not all values are initialized yet")
                return

            current_date = dt_util.now().date().isoformat()

            daily_data = {
                key: self._data[key]
                for key in self._daily_sensors
            }

            persistent_data = {
                "daily_values": {
                    "date": current_date,
                    "values": daily_data
                },
                "last_daily_reset": self._daily_reset_time.isoformat(),
                "_version": "1.0",
                "_last_updated": dt_util.utcnow().isoformat()
            }

            # Add regular persistent values
            for key in self._persistent_sensors:
                persistent_data[key] = self._data[key]

            _LOGGER.debug(
                "Saving persistent data - Daily values: %s, Date: %s, Reset time: %s",
                daily_data,
                current_date,
                self._daily_reset_time.isoformat()
            )

            store = self.hass.helpers.storage.Store(
                version=1,
                key=f"{DOMAIN}_persistent_data_{self.address}",
                private=True,
                atomic_writes=True
            )
            await store.async_save(persistent_data)
        except Exception as err:
            _LOGGER.error("Error saving persistent data: %s", err)

    async def _restore_persistent_data(self) -> None:
        """Restore persistent sensor values including daily values."""
        try:
            store = self.hass.helpers.storage.Store(
                version=1,
                key=f"{DOMAIN}_persistent_data_{self.address}",
                private=True
            )
            stored_data = await store.async_load()

            _LOGGER.debug("Loaded stored data: %s", stored_data)

            if stored_data:
                current_date = dt_util.now().date().isoformat()

                # Restore regular persistent values
                for key in self._persistent_sensors:
                    if key in stored_data:
                        self._data[key] = stored_data[key]
                        _LOGGER.debug("Restored persistent value %s = %s", key, stored_data[key])

                # Handle daily values
                if "daily_values" in stored_data:
                    stored_date = stored_data["daily_values"]["date"]
                    _LOGGER.debug(
                        "Checking daily values - Stored date: %s, Current date: %s",
                        stored_date,
                        current_date
                    )

                    if stored_date == current_date:
                        for key, value in stored_data["daily_values"]["values"].items():
                            self._data[key] = value
                            _LOGGER.debug("Restored daily value %s = %s", key, value)
                    else:
                        _LOGGER.debug(
                            "Daily values from different date (stored: %s, current: %s), resetting to 0",
                            stored_date,
                            current_date
                        )
                        for key in self._daily_sensors:
                            self._data[key] = 0.0
                            _LOGGER.debug("Reset daily value %s to 0", key)

                # Restore last reset time
                if "last_daily_reset" in stored_data:
                    try:
                        self._daily_reset_time = dt_util.parse_datetime(stored_data["last_daily_reset"])
                        _LOGGER.debug("Restored daily reset time: %s", self._daily_reset_time)
                    except Exception as err:
                        _LOGGER.error("Error parsing stored reset time: %s", err)
                        self._daily_reset_time = dt_util.start_of_local_day()
                else:
                    self._daily_reset_time = dt_util.start_of_local_day()
                    _LOGGER.debug("Using default daily reset time: %s", self._daily_reset_time)

            else:
                _LOGGER.debug("No stored data found, using default values")
                self._daily_reset_time = dt_util.start_of_local_day()
                for key in self._daily_sensors:
                    self._data[key] = 0.0

            _LOGGER.debug("Final data after restore: %s", {
                key: self._data[key] for key in self._daily_sensors
            })

        except Exception as err:
            _LOGGER.error("Error restoring persistent data: %s", err)

    @property
    def weight(self) -> float:
        """Get the current weight setting."""
        return self._weight

    @weight.setter
    def weight(self, value: float) -> None:
        """Set the current weight setting."""
        self._weight = value

    @property
    def resistance(self) -> float:
        """Get the current resistance setting."""
        return self._resistance

    @resistance.setter
    def resistance(self, value: float) -> None:
        """Set the current resistance setting."""
        self._resistance = value

    def _calculate_calories(self, speed: float, time_diff: float, resistance: int) -> float:
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

        # Calculate calories: MET * weight * time(hours) * resistance %
        return met * self.weight * hours * resistance / 100

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
        _LOGGER.debug(
            "Checking daily reset - Current time: %s, Last reset: %s",
            now,
            self._daily_reset_time
        )

        if now > self._daily_reset_time + timedelta(days=1):
            _LOGGER.debug(
                "Performing daily reset. Old values: %s",
                {key: self._data[key] for key in self._daily_sensors}
            )
            for key in self._daily_sensors:
                self._data[key] = 0.0
            self._daily_reset_time = dt_util.start_of_local_day()
            # Save the reset state
            asyncio.create_task(self._save_persistent_data())
            _LOGGER.debug("Daily values reset completed")

    async def _reload_sensor_values(self):
        """Reload sensor values."""
        try:
            battery_bytes = await self._client.read_gatt_char(CHAR_BATTERY)
            self._data["battery"] = int.from_bytes(battery_bytes, byteorder='little')

            for char_uuid, key in [
                (CHAR_MODEL_NUMBER, "model"),
                (CHAR_SERIAL_NUMBER, "serial_number"),
                (CHAR_FIRMWARE, "firmware_version"),
                (CHAR_HARDWARE, "hardware_version"),
                (CHAR_SOFTWARE, "software_version"),
            ]:
                value = await self._client.read_gatt_char(char_uuid)
                self.device_info[key] = value.decode('utf-8').strip()
                self._data[key] = self.device_info[key]

            self.async_set_updated_data(self._data.copy())

            # Dynamically add sensors if they were unavailable during setup
            await self._add_missing_sensors()
        except Exception as e:
            _LOGGER.debug("Error reloading sensor values: %s", e)

    def _notification_handler(self, _: int, data: bytearray) -> None:
        """Handle incoming CSC measurement notifications."""
        try:
            # Update activity timestamp when we receive data
            self._last_activity_time = dt_util.utcnow()

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
                        # Calculate time difference
                        time_diff = wheel_event_diff / 1024.0

                        # Handle wheel revolution counter wrapping
                        if wheel_revs >= self._last_wheel_rev:
                            wheel_rev_diff  = wheel_revs - self._last_wheel_rev
                        else:
                            # Counter wrapped around (uint32 max = 4294967295)
                            wheel_rev_diff  = (4294967295 - self._last_wheel_rev) + wheel_revs + 1

                        # Sanity check: If wheel_rev_diff  is unreasonably large, ignore this update
                        if wheel_rev_diff  > 1000:  # More than 1000 revolutions in one update is unlikely
                            _LOGGER.warning(
                                "Ignoring suspicious wheel revolution difference: %d (previous: %d, current: %d)",
                                wheel_rev_diff , self._last_wheel_rev, wheel_revs
                            )
                            self._last_wheel_rev = wheel_revs
                            self._last_wheel_event = wheel_event
                            return
                        else:
                            distance = wheel_rev_diff  * self._wheel_circumference # in meters
                            speed = (distance / time_diff) * 3.6

                            # Update sensors if speed is reasonable
                            if 0 <= speed <= 100:  # Reasonable speed range for a bike
                                self._data["speed"] = round(speed, 1)
                                distance_km = distance / 1000
                                self._data["distance"] += distance_km
                                self._data["daily_distance"] += distance_km
                                activity_detected = True

                self._last_wheel_rev = wheel_revs
                self._last_wheel_event = wheel_event
                offset += 6

            if crank_rev_present:
                crank_revs, crank_event = struct.unpack_from("<HH", data, offset)
                if self._last_crank_event != 0:
                    crank_event_diff = (crank_event - self._last_crank_event) & 0xFFFF
                    if crank_event_diff > 0:
                        # Calculate revolution difference
                        if crank_revs >= self._last_crank_rev:
                            crank_rev_diff = crank_revs - self._last_crank_rev
                        else:
                            # Handle counter wrap-around (uint16 max = 65535)
                            crank_rev_diff = (65535 - self._last_crank_rev) + crank_revs + 1

                        # Update rotation counters if the difference is reasonable
                        if crank_rev_diff < 100:  # Sanity check: limit to 100 revolutions per update
                            self._data["daily_crank_rotations"] += crank_rev_diff
                            self._data["total_crank_rotations"] += crank_rev_diff
                        else:
                            _LOGGER.warning(
                                "Ignoring suspicious crank revolution difference: %d (previous: %d, current: %d)",
                                crank_rev_diff, self._last_crank_rev, crank_revs
                            )

                        time_diff = crank_event_diff / 1024.0
                        cadence = (crank_rev_diff / time_diff) * 60
                        self._data["cadence"] = round(cadence, 1)
                        if cadence > 0:
                            activity_detected = True

                self._last_crank_rev = crank_revs
                self._last_crank_event = crank_event

            # Update activity status and timing
            if activity_detected:
                self._last_active = now
                self._data["last_active"] = self._last_active

                if not self._data["is_active"]:
                    self._data["is_active"] = True
                    # Reload sensor values when activity starts
                    asyncio.create_task(self._reload_sensor_values())

                # Start or update activity timing
                if self._activity_start_time is None:
                    self._activity_start_time = now
                else:
                    # Calculate time difference since last activity check
                    time_diff = (now - self._last_activity_check).total_seconds()
                    self._data["daily_active_time"] += time_diff
                    self._data["total_active_time"] += time_diff

                self._last_activity_check = now

                # Calculate and add calories if speed is available
                if self._data["speed"] > 0:
                    resistance = self._resistance  # Assuming resistance is stored in the coordinator
                    calories_burned = self._calculate_calories(self._data["speed"], 1, resistance)  # 1 second of activity
                    self._data["daily_calories"] += calories_burned
                    self._data["total_calories"] += calories_burned
            else:
                self._check_activity_timeout()

            self._check_daily_reset()
            self.async_set_updated_data(self._data.copy())

            # Save current state periodically if values changed
            if self._data != self._last_saved_daily_values:
                self._last_saved_daily_values = self._data.copy()
                asyncio.create_task(self._save_persistent_data())
        except Exception as e:
            _LOGGER.error("Error processing CSC notification: %s", e)

    async def force_reconnect(self) -> None:
        """Force a reconnection attempt."""
        _LOGGER.debug("Forcing reconnection to DeskBike")

        # Clean up existing connection if any
        if self._client:
            try:
                await self._async_disconnect()
            except Exception as e:
                _LOGGER.debug("Error during disconnect: %s", e)

        # Reset connection state
        self._connected = False
        self._data["is_connected"] = False
        self._client = None
        self._force_reconnect = True  # Set the flag

        # Force a new connection attempt immediately
        try:
            await self._async_connect()
        except Exception as e:
            _LOGGER.debug("Force reconnect connect attempt failed: %s", e)

        # Trigger a data refresh
        self.async_set_updated_data(self._data)

    async def _save_sensor_values(self):
        """Save sensor values to Home Assistant storage."""
        store = self.hass.helpers.storage.Store(1, f"{DOMAIN}_sensor_values_{self.address}")
        await store.async_save(self._data)

    async def _restore_sensor_values(self):
        """Restore sensor values from Home Assistant storage."""
        store = self.hass.helpers.storage.Store(1, f"{DOMAIN}_sensor_values_{self.address}")
        restored_data = await store.async_load()
        if restored_data:
            self._data.update(restored_data)
            self.device_info.update({
                "model": restored_data.get("model"),
                "serial_number": restored_data.get("serial_number"),
                "firmware_version": restored_data.get("firmware_version"),
                "hardware_version": restored_data.get("hardware_version"),
                "software_version": restored_data.get("software_version"),
            })
            self.async_set_updated_data(self._data.copy())

    async def async_setup(self) -> None:
        """Set up the coordinator."""
        _LOGGER.debug("Starting coordinator setup")

        # First restore any saved data
        await self._restore_persistent_data()

        # Now initialize any missing values to 0
        for key in self._daily_sensors + self._persistent_sensors:
            if self._data[key] is None:
                self._data[key] = 0.0
                _LOGGER.debug("Initialized missing value %s to 0", key)

        _LOGGER.debug("Coordinator setup complete with data: %s",
                     {key: self._data[key] for key in self._daily_sensors + self._persistent_sensors})

    async def _add_missing_sensors(self):
        """Add missing sensors dynamically."""
        entities = []
        for char_name, info_key in [
            ("Model Number", "model"),
            ("Serial Number", "serial_number"),
            ("Firmware Version", "firmware_version"),
            ("Hardware Version", "hardware_version"),
            ("Software Version", "software_version"),
        ]:
            if info_key in self.device_info and self.device_info[info_key]:
                entities.append(
                    DeskBikeDiagnosticSensor(
                        self,
                        self._config_entry,
                        char_name,
                        self.device_info[info_key]
                    )
                )
        if entities:
            async_add_entities = self.hass.data[DOMAIN][self._config_entry.entry_id].async_add_entities
            async_add_entities(entities)

    async def _async_connect(self) -> None:
        """Connect to the DeskBike device."""
        now = dt_util.utcnow()

        # Check if we should attempt reconnection
        if not self._force_reconnect and (
            self._last_connection_attempt and
            now - self._last_connection_attempt < self._retry_interval
        ):
            return

        self._last_connection_attempt = now
        self._force_reconnect = False  # Reset the flag

        if self._connected:
            return

        async with self._connection_lock:
            if self._connected:
                return

            try:
                if self._client:
                    try:
                        await asyncio.wait_for(self._client.disconnect(), timeout=2.0)
                    except (Exception, asyncio.TimeoutError):
                        pass
                    self._client = None

                self._client = BleakClient(
                    self.address,
                    disconnected_callback=self._handle_disconnection,
                    timeout=5.0
                )

                await asyncio.wait_for(self._client.connect(), timeout=5.0)
                self._connected = True
                self._data["is_connected"] = True

                # Read device info and subscribe to notifications
                try:
                    battery_read = await asyncio.wait_for(
                        self._client.read_gatt_char(CHAR_BATTERY),
                        timeout=3.0
                    )
                    self._data["battery"] = int.from_bytes(battery_read, byteorder='little')
                except (Exception, asyncio.TimeoutError) as e:
                    _LOGGER.debug("Error reading battery level: %s", e)

                if not self.device_info:
                    await self._read_device_info()

                await asyncio.wait_for(
                    self._client.start_notify(
                        CHAR_CSC_MEASUREMENT,
                        self._notification_handler,
                    ),
                    timeout=3.0
                )

                _LOGGER.debug("Connected to DeskBike")
                return

            except Exception as e:
                self._cleanup_connection()
                raise

    def _cleanup_connection(self) -> None:
        """Clean up the connection state."""
        self._connected = False
        self._data["is_connected"] = False
        if self._client:
            self._client = None

    def _handle_disconnection(self, client: BleakClient) -> None:
        """Handle disconnection event."""
        self._connected = False
        self._data["is_connected"] = False
        self._data["is_active"] = False
        self.async_set_updated_data(self._data.copy())

        # Only schedule reconnection if we have recent activity
        if (self._last_activity_time and
            (dt_util.utcnow() - self._last_activity_time) < self._activity_timeout):
            if self._reconnect_task is None or self._reconnect_task.done():
                self._reconnect_task = asyncio.create_task(self._async_handle_reconnect())

    async def async_config_entry_first_refresh(self):
        """Perform the first refresh of the config entry."""
        await self._restore_sensor_values()
        await super().async_config_entry_first_refresh()

    async def _async_handle_reconnect(self) -> None:
        """Handle reconnection attempts."""
        while not self._connected:
            try:
                _LOGGER.debug("Attempting to reconnect to DeskBike...")
                await self._async_connect()
                if self._connected:
                    _LOGGER.debug("Successfully reconnected to DeskBike")
                    break
            except Exception as e:
                _LOGGER.debug("Reconnection attempt failed: %s", e)
                await asyncio.sleep(5)  # Wait before next attempt

    async def _read_device_info(self) -> None:
        """Read device information characteristics with timeouts."""
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
                    value = await asyncio.wait_for(
                        self._client.read_gatt_char(char_uuid),
                        timeout=3.0
                    )
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
                except (Exception, asyncio.TimeoutError) as e:
                    _LOGGER.debug("Error reading characteristic %s: %s", char_uuid, e)
        except Exception as e:
            _LOGGER.debug("Failed to read device info: %s", e)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data from DeskBike."""
        try:
            if not self._connected and self._should_attempt_connection():
                try:
                    await self._async_connect()
                except Exception as connect_error:
                    _LOGGER.debug("Connection attempt failed: %s", connect_error)
                    return self._data

            # Save persistent data periodically
            now = dt_util.utcnow()
            if not hasattr(self, '_last_save') or (now - self._last_save > timedelta(minutes=5)):
                await self._save_persistent_data()
                self._last_save = now

            return self._data
        except Exception as error:
            _LOGGER.debug("Error fetching DeskBike data: %s", error)
            return self._data

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

    # Ensure missing sensors are added dynamically
    coordinator.hass = hass
    coordinator._config_entry = entry
    coordinator.async_add_entities = async_add_entities
