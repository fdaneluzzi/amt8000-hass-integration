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
        
        if zone_status == "triggered":
            return BinarySensorDeviceClass.SAFETY
        elif zone_status == "tamper":
            return BinarySensorDeviceClass.TAMPER
        elif zone_status == "open":
            return BinarySensorDeviceClass.DOOR
        elif zone_status == "low_battery":
            return BinarySensorDeviceClass.BATTERY
        elif zone_status == "comm_failure":
            return BinarySensorDeviceClass.CONNECTIVITY
        else:
            return BinarySensorDeviceClass.SAFETY

    @property
    def is_on(self) -> bool:
        """Return True when the zone has a problem."""
        zone_status = self.coordinator.data["zones"].get(self._zone_id, "normal")
        return zone_status != "normal"

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        zone_status = self.coordinator.data["zones"].get(self._zone_id, "normal")
        return {
            "status": zone_status,
            "zone_id": self._zone_id
        }

    # O Coordinator já cuida da atualização: quando ele muda, a entidade recebe
    # async_write_ha_state() automaticamente via CoordinatorEntity.
