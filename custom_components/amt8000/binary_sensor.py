"""Binary sensors (zones) for the Intelbras AMT-8000."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .coordinator import AmtCoordinator

# ---------------------------- setup --------------------------------- #
async def async_setup_entry(hass, entry, async_add_entities):
    """Adicionar um binary_sensor por zona."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    config = data["config"]

    await coordinator.async_request_refresh()

    entities = [
        AMTZoneBinarySensor(coordinator, zone_id, config["host"])
        for zone_id in coordinator.data.get("zones", {}).keys()
    ]   
    async_add_entities(entities)


# --------------------------- entidade -------------------------------- #
class AMTZoneBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representa uma zona (setor) da AMT-8000."""

    _attr_should_poll = False

    def __init__(self, coordinator: AmtCoordinator, zone_id: str, host: str) -> None:
        """Init."""
        super().__init__(coordinator)

        self._zone_id = zone_id
        self._attr_unique_id = f"amt8000_{host}_zone_{zone_id}"
        self._attr_name = f"AMT-8000 Zona {zone_id}"

        # Faz o sensor aparecer dentro do mesmo dispositivo do painel
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"amt8000_{host}")},
            name="AMT-8000",
            manufacturer="Intelbras",
            model="AMT-8000"
        )

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the device class of the sensor."""
        zone_status = self.coordinator.data["zones"].get(self._zone_id, "normal")
        
        # If there are multiple problems, prioritize the most critical one
        if isinstance(zone_status, str):
            problems = zone_status.split(",")
            
            if "triggered" in problems:
                return BinarySensorDeviceClass.SAFETY
            elif "tamper" in problems:
                return BinarySensorDeviceClass.TAMPER
            elif "open" in problems:
                return BinarySensorDeviceClass.DOOR
            elif "low_battery" in problems:
                return BinarySensorDeviceClass.BATTERY
            elif "comm_failure" in problems:
                return BinarySensorDeviceClass.CONNECTIVITY
            elif "bypassed" in problems:
                return BinarySensorDeviceClass.SAFETY
                
        return BinarySensorDeviceClass.SAFETY

    @property
    def is_on(self) -> bool:
        """Return True when the zone has a problem."""
        zone_status = self.coordinator.data["zones"].get(self._zone_id, "normal")
        return zone_status != "normal"

    @property
    def state(self) -> str:
        """Return the state of the sensor for automations."""
        zone_status = self.coordinator.data["zones"].get(self._zone_id, "normal")
        
        if zone_status == "normal":
            return "seguro"
            
        # If there are multiple problems, return the most critical one
        if isinstance(zone_status, str):
            problems = zone_status.split(",")
            
            if "triggered" in problems:
                return "disparado"
            elif "tamper" in problems:
                return "violado"
            elif "open" in problems:
                return "aberto"
            elif "low_battery" in problems:
                return "bateria_fraca"
            elif "comm_failure" in problems:
                return "falha_comunicacao"
            elif "bypassed" in problems:
                return "ignorado"
                
        return "inseguro"

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        zone_status = self.coordinator.data["zones"].get(self._zone_id, "normal")
        
        # Convert comma-separated status to list for better UI display
        if isinstance(zone_status, str) and "," in zone_status:
            problems = zone_status.split(",")
        else:
            problems = [zone_status]
            
        return {
            "status": zone_status,
            "problems": problems,
            "zone_id": self._zone_id
        }

    # O Coordinator já cuida da atualização: quando ele muda, a entidade recebe
    # async_write_ha_state() automaticamente via CoordinatorEntity.
