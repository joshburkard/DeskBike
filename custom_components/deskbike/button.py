"""Support for DeskBike button entities."""
from __future__ import annotations

import logging
from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DeskBike button entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DeskBikeReconnectButton(coordinator, entry)])

class DeskBikeReconnectButton(ButtonEntity):
    """Representation of a DeskBike reconnect button."""

    def __init__(self, coordinator, config_entry: ConfigEntry) -> None:
        """Initialize the button."""
        self.coordinator = coordinator
        self._config_entry = config_entry

        self._attr_has_entity_name = True
        self._attr_name = "Reconnect"
        self._attr_unique_id = f"{config_entry.data[CONF_ADDRESS]}_reconnect"
        self._attr_device_class = ButtonDeviceClass.RESTART

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.data[CONF_ADDRESS])},
            name=config_entry.data[CONF_NAME],
            manufacturer="DeskBike",
            model=coordinator.device_info.get("model", "DeskBike"),
            sw_version=coordinator.device_info.get("firmware_version"),
            hw_version=coordinator.device_info.get("hardware_version"),
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.debug("Attempting manual reconnection to DeskBike")
        await self.coordinator.force_reconnect()