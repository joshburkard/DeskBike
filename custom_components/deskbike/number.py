"""Support for DeskBike number entities."""
from __future__ import annotations

import logging
from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MASS_KILOGRAMS, CONF_NAME, CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DEFAULT_WEIGHT

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DeskBike number entities."""
    _LOGGER.debug("Setting up DeskBike number entities")
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DeskBikeWeightSetting(coordinator, entry)])

class DeskBikeWeightSetting(RestoreNumber):
    """Representation of the cyclist weight setting."""

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the weight setting."""
        super().__init__()
        self.coordinator = coordinator
        self._entry = entry

        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_weight"
        self._attr_has_entity_name = True
        self._attr_native_min_value = 10
        self._attr_native_max_value = 150
        self._attr_native_step = 0.5
        self._attr_mode = "slider"
        self._attr_native_unit_of_measurement = MASS_KILOGRAMS
        self._attr_name = "Cyclist Weight kg"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_icon = "mdi:human-male"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_ADDRESS])},
            name=entry.data[CONF_NAME],
            manufacturer="DeskBike",
            model=coordinator.device_info.get("model", "DeskBike"),
            sw_version=coordinator.device_info.get("firmware_version"),
            hw_version=coordinator.device_info.get("hardware_version"),
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        # Restore previous state
        if last_state := await self.async_get_last_state():
            try:
                restored_value = float(last_state.state)
                self.coordinator.weight = restored_value
                _LOGGER.debug("Restored weight value: %s", restored_value)
            except (ValueError, TypeError):
                self.coordinator.weight = DEFAULT_WEIGHT
                _LOGGER.debug("Using default weight: %s", DEFAULT_WEIGHT)

    @property
    def native_value(self) -> float:
        """Return the current weight setting."""
        return self.coordinator.weight

    async def async_set_native_value(self, value: float) -> None:
        """Update the current weight setting."""
        self.coordinator.weight = value
        self.async_write_ha_state()