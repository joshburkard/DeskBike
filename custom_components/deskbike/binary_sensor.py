"""Support for DeskBike binary sensors."""
from __future__ import annotations

import logging
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="is_active",
        name="Is Active",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:bike",
    ),
    BinarySensorEntityDescription(
        key="is_connected",
        name="Is Connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:bluetooth",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

class DeskBikeBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a DeskBike binary sensor."""

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
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
        )

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.key, False)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DeskBike binary sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for description in BINARY_SENSOR_TYPES:
        entities.append(DeskBikeBinarySensor(coordinator, entry, description))

    async_add_entities(entities)