"""Defines the sensors for amt-8000."""
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.helpers.device_registry import DeviceInfo

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)


from .const import DOMAIN
from .coordinator import AmtCoordinator
from .isec2.client import Client as ISecClient


LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the AMT-8000 alarm control panel."""
    data = hass.data[DOMAIN][entry.entry_id]
    config = data["config"]
    coordinator = data["coordinator"]

    isec_client = ISecClient(config["host"], config["port"])
    async_add_entities([AmtAlarmPanel(coordinator, isec_client, config["password"], config["host"])])


class AmtAlarmPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Define a Amt Alarm Panel."""

    _attr_supported_features = (
          AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.TRIGGER
    )

    def __init__(self, coordinator, isec_client: ISecClient, password: str, host: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.status = None
        self.isec_client = isec_client
        self.password = password
        
        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"amt8000_{host}")},
            name="AMT-8000",
            manufacturer="Intelbras",
            model="AMT-8000"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the stored value on coordinator updates."""
        self.status = self.coordinator.data
        LOGGER.debug("Received coordinator update: %s", self.status)
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return "AMT-8000"

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"amt8000_{self.isec_client.host}_control_panel"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.status is not None

    @property
    def alarm_state(self) -> AlarmControlPanelState:
        """Return the state of the entity."""
        if self.status is None:
            LOGGER.debug("Status is None")
            return AlarmControlPanelState.UNKNOWN

        try:
            status_data = self.status.get("status", {})
            LOGGER.debug("Status data: %s", status_data)

            if not status_data:
                LOGGER.debug("Status data is empty")
                return AlarmControlPanelState.UNKNOWN

            # Check if alarm is triggered
            if status_data.get("siren", False):
                LOGGER.debug("Alarm is triggered")
                return AlarmControlPanelState.TRIGGERED

            # Get alarm status
            alarm_status = status_data.get("status", "unknown")
            LOGGER.debug("Alarm status: %s", alarm_status)

            if alarm_status == "armed_away":
                LOGGER.debug("Alarm is armed away")
                return AlarmControlPanelState.ARMED_AWAY
            elif alarm_status == "partial_armed":
                LOGGER.debug("Alarm is partially armed")
                return AlarmControlPanelState.ARMED_HOME
            elif alarm_status == "disarmed":
                LOGGER.debug("Alarm is disarmed")
                return AlarmControlPanelState.DISARMED
            else:
                LOGGER.debug("Alarm is in unknown state")
                return AlarmControlPanelState.UNKNOWN

        except Exception as e:
            LOGGER.error("Error getting state: %s", str(e))
            return AlarmControlPanelState.UNKNOWN

    async def async_alarm_disarm(self, code=None) -> None:
        """Send disarm command."""
        self.isec_client.connect()
        self.isec_client.auth(self.password)
        result = self.isec_client.disarm_system(0)
        self.isec_client.close()
        if result == "disarmed":
            await self.coordinator.async_request_refresh()

    async def async_alarm_arm_away(self, code=None) -> None:
        """Send arm away command."""
        self.isec_client.connect()
        self.isec_client.auth(self.password)
        result = self.isec_client.arm_system(0)
        self.isec_client.close()
        if result == "armed":
            await self.coordinator.async_request_refresh()

    async def async_alarm_trigger(self, code=None) -> None:
        """Send alarm trigger command."""
        self.isec_client.connect()
        self.isec_client.auth(self.password)
        result = self.isec_client.panic(1)
        self.isec_client.close()
        if result == "triggered":
            await self.coordinator.async_request_refresh()

