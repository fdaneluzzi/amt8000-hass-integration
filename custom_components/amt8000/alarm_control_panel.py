"""Defines the sensors for amt-8000."""
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity, AlarmControlPanelEntityFeature

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
    async_add_entities([AmtAlarmPanel(coordinator, isec_client, config["password"])])


class AmtAlarmPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Define a Amt Alarm Panel."""

    _attr_supported_features = (
          AlarmControlPanelEntityFeature.ARM_AWAY
        # | AlarmControlPanelEntityFeature.ARM_NIGHT
        # | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.TRIGGER
    )

    def __init__(self, coordinator, isec_client: ISecClient, password):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.status = None
        self.isec_client = isec_client
        self.password = password
        self._is_on = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the stored value on coordinator updates."""
        self.status = self.coordinator.data
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return "AMT-8000"

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return "amt8000.control_panel"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.status is not None

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        if self.status is None:
            return "unknown"

        if self.status['siren'] == True:
            return "triggered"

        if(self.status["status"].startswith("armed_")):
          self._is_on = True

        return self.status["status"]

    def _arm_away(self):
        """Arm AMT in away mode"""
        self.isec_client.connect()
        self.isec_client.auth(self.password)
        result = self.isec_client.arm_system(0)
        self.isec_client.close()
        if result == "armed":
            return 'armed_away'

    def _disarm(self):
        """Arm AMT in away mode"""
        self.isec_client.connect()
        self.isec_client.auth(self.password)
        result = self.isec_client.disarm_system(0)
        self.isec_client.close()
        if result == "disarmed":
            return 'disarmed'


    def _trigger_alarm(self):
        """Trigger Alarm"""
        self.isec_client.connect()
        self.isec_client.auth(self.password)
        result = self.isec_client.panic(1)
        self.isec_client.close()
        if result == "triggered":
            return "triggered"


    def alarm_disarm(self, code=None) -> None:
        """Send disarm command."""
        self._disarm()

    async def async_alarm_disarm(self, code=None) -> None:
        """Send disarm command."""
        self._disarm()

    def alarm_arm_away(self, code=None) -> None:
        """Send arm away command."""
        self._arm_away()

    async def async_alarm_arm_away(self, code=None) -> None:
        """Send arm away command."""
        self._arm_away()

    def alarm_trigger(self, code=None) -> None:
        """Send alarm trigger command."""
        self._trigger_alarm()

    async def async_alarm_trigger(self, code=None) -> None:
        """Send alarm trigger command."""
        self._trigger_alarm()

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self._is_on

    def turn_on(self, **kwargs: Any) -> None:
        self._arm_away()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._arm_away()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._disarm()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._disarm()

