"""Support for DeskBike ble sensors."""
from __future__ import annotations

import logging

from .DESKBIKE import DeskBikeDevice

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfElectricPotential,
    CONDUCTIVITY,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSORS_MAPPING_TEMPLATE: dict[str, SensorEntityDescription] = {
    "serialnumber": SensorEntityDescription(
        key="serialnumber",
        name="Serial Number",
        icon="mdi:dots-grid",
    ),

    "firmware": SensorEntityDescription(
        key="firmware",
        name="Firmware Version",
        icon="mdi:dots-grid",
    ),
    "software": SensorEntityDescription(
        key="software",
        name="Software Version",
        icon="mdi:dots-grid",
    ),
    "hardware": SensorEntityDescription(
        key="hardware",
        name="Hardware Version",
        icon="mdi:dots-grid",
    ),

    "modelnumber": SensorEntityDescription(
        key="modelnumber",
        name="Model Number",
        icon="mdi:dots-grid",
    ),

    "devicename": SensorEntityDescription(
        key="devicename",
        name="Device Name",
        icon="mdi:dots-grid",
    ),

    "battery": SensorEntityDescription(
        key="battery",
        name="Battery",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
    ),

    "cscmeasurement": SensorEntityDescription(
        key="cscmeasurement",
        name="CscMeasurement",
        icon="mdi:dots-grid",
    ),





    "daily_crank_revolution": SensorEntityDescription(
        key="daily_crank_revolution",
        name="Daily Crank Revolutions",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:progress-pencil",
    ),
    "daily_distance": SensorEntityDescription(
        key="daily_distance",
        name="Daily Distance",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DISTANCE,
        # native_unit_of_measurement=UnitOfLength.METERS,
        # native_unit_of_measurement=UnitOfLength.KILOMETERS,
        # native_unit_of_measurement=km,
        # suggested_unit_of_measurement="km"
        icon="mdi:map-marker-distance",
    ),
    "daily_active_time": SensorEntityDescription(
        key="daily_active_time",
        name="Daily Active Time",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DURATION,
        # device_class=SensorDeviceClass.DATE,
        native_unit_of_measurement="s",
        icon="mdi:clock-time-eight-outline",
    ),

    "total_crank_revolution": SensorEntityDescription(
        key="total_crank_revolution",
        name="Total Crank Revolutions",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:progress-pencil",
    ),
    "total_distance": SensorEntityDescription(
        key="total_distance",
        name="Total Distance",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DISTANCE,
        # native_unit_of_measurement=UnitOfLength.METERS,
        # native_unit_of_measurement=UnitOfLength.KILOMETERS,
        # native_unit_of_measurement=km,
        # suggested_unit_of_measurement="km"
        icon="mdi:map-marker-distance",
    ),
    "total_active_time": SensorEntityDescription(
        key="total_active_time",
        name="Total Active Time",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DURATION,
        # device_class=SensorDeviceClass.DATE,
        native_unit_of_measurement="s",
        icon="mdi:clock-time-eight-outline",
    ),
    "cscratio": SensorEntityDescription(
        key="cscratio",
        name="Ratio between Crank and Calories",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:dots-grid",
    ),

    "cscvalue01": SensorEntityDescription(
        key="cscvalue01",
        name="cscvalue01",
        icon="mdi:dots-grid",
    ),
    "csc_dif_crank": SensorEntityDescription(
        key="csc_dif_crank",
        name="current Crank Revolution",
        icon="mdi:dots-grid",
    ),
    "csc_dif_calories": SensorEntityDescription(
        key="csc_dif_calories",
        name="current Calories",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:dots-grid",
    ),
    "cscdifkcal": SensorEntityDescription(
        key="cscdifkcal",
        name="Dif kCal",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:dots-grid",
    ),
    "difcsctimestamp": SensorEntityDescription(
        key="difcsctimestamp",
        name="difcsctimestamp",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:dots-grid",
    ),

    "current_speed": SensorEntityDescription(
        key="current_speed",
        name="Current Speed",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement="km/h",
        icon="mdi:speedometer",
    ),


}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DeskBike BLE sensors."""
    is_metric = hass.config.units is METRIC_SYSTEM

    coordinator: DataUpdateCoordinator[DeskBikeDevice] = hass.data[DOMAIN][entry.entry_id]
    sensors_mapping = SENSORS_MAPPING_TEMPLATE.copy()
    entities = []
    _LOGGER.debug("got sensors: %s", coordinator.data.sensors)
    for sensor_type, sensor_value in coordinator.data.sensors.items():
        if sensor_type not in sensors_mapping:
            _LOGGER.debug(
                "Unknown sensor type detected: %s, %s",
                sensor_type,
                sensor_value,
            )
            continue
        entities.append(
            DeskBikeSensor(coordinator, coordinator.data, sensors_mapping[sensor_type])
        )

    async_add_entities(entities)


class DeskBikeSensor(CoordinatorEntity[DataUpdateCoordinator[DeskBikeDevice]], SensorEntity):
    """DeskBike BLE sensors for the device."""

    #_attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        DeskBike_device: DeskBikeDevice,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Populate the DeskBike entity with relevant data."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        name = f"{DeskBike_device.name} {DeskBike_device.identifier}"

        self._attr_unique_id = f"{name}_{entity_description.key}"

        self._id = DeskBike_device.address
        self._attr_device_info = DeviceInfo(
            connections={
                (
                    CONNECTION_BLUETOOTH,
                    DeskBike_device.address,
                )
            },
            name=name,
            manufacturer="DeskBike",
            model="DeskBike",
            hw_version=DeskBike_device.hw_version,
            sw_version=DeskBike_device.sw_version,
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        try:
            return self.coordinator.data.sensors[self.entity_description.key]
        except KeyError:
            return None
