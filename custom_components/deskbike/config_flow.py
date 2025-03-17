"""Config flow for DeskBike integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

class DeskBikeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DeskBike."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle discovery via bluetooth."""
        _LOGGER.debug("Discovered BLE device: %s", discovery_info.name)

        # Check if device name starts with "deskbike" (case insensitive)
        if discovery_info.name and discovery_info.name.lower().startswith("deskbike"):
            await self.async_set_unique_id(discovery_info.address)
            self._abort_if_unique_id_configured()

            self._discovered_devices[discovery_info.address] = discovery_info
            return await self.async_step_user()

        return self.async_abort(reason="not_deskbike_device")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        errors = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_ADDRESS: address,
                },
            )

        # Get all discovered Bluetooth devices
        current_addresses = self._discovered_devices.keys()
        for discovery_info in async_discovered_service_info(self.hass):
            if (
                discovery_info.name
                and discovery_info.name.lower().startswith("deskbike")
                and discovery_info.address not in current_addresses
            ):
                self._discovered_devices[discovery_info.address] = discovery_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        # Create selection list
        devices = {
            discovery_info.address: f"{discovery_info.name} ({discovery_info.address})"
            for discovery_info in self._discovered_devices.values()
        }

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.In(devices),
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
