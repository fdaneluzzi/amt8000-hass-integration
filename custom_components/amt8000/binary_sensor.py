"""Binary sensors (zones) for the Intelbras AMT-8000."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AmtCoordinator

# ---------------------------- setup --------------------------------- #
async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Add a binary_sensor entity per zone."""
    coordinator: AmtCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Se ainda não houver dados (p.ex. logo após reboot), espere 1ª atualização
    await coordinator.async_config_entry_first_refresh()

    entities: list[BinarySensorEntity] = [
        AMTZoneBinarySensor(coordinator, zone_id)
        for zone_id in coordinator.data.get("zones", {}).keys()
    ]
    async_add_entities(entities)


# --------------------------- entidade -------------------------------- #
class AMTZoneBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representa uma zona (setor) da AMT-8000."""

    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.SAFETY  # use outro se preferir

    def __init__(self, coordinator: AMTCoordinator, zone_id: str) -> None:
        """Init."""
        super().__init__(coordinator)

        self._zone_id = zone_id
        self._attr_unique_id = f"{coordinator.serial}_zone_{zone_id}"
        self._attr_name = f"AMT-8000 Zona {zone_id}"

        # Faz o sensor aparecer dentro do mesmo dispositivo do painel
        self._attr_device_info = coordinator.device_info

    # -------------------------------------------------------------- #
    @property
    def is_on(self) -> bool:
        """Retorna True quando a zona está disparada."""
        return self.coordinator.data["zones"].get(self._zone_id) == "triggered"

    # O Coordinator já cuida da atualização: quando ele muda, a entidade recebe
    # async_write_ha_state() automaticamente via CoordinatorEntity.
