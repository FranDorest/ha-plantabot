"""Botón de PlantaBot: registrar un riego realizado a mano.

Mientras no haya caudalímetro/válvula, este botón es la forma de decirle al
acumulador de déficit que ya se regó (lo pone a cero y guarda la fecha/hora).
"""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlantaBotConfigEntry
from .const import CONF_NAME, DOMAIN
from .coordinator import PlantaBotCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantaBotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([PBIrrigationDoneButton(coordinator, entry)])


class PBIrrigationDoneButton(ButtonEntity):
    """Al pulsarlo, el déficit acumulado se pone a cero."""

    _attr_has_entity_name = True
    _attr_translation_key = "riego_registrado"
    _attr_icon = "mdi:watering-can"

    def __init__(self, coordinator: PlantaBotCoordinator, entry: PlantaBotConfigEntry) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_riego_registrado"
        name = entry.data.get(CONF_NAME, entry.title)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"PlantaBot {name}",
            manufacturer="PlantaBot",
        )

    async def async_press(self) -> None:
        await self.coordinator.async_register_irrigation()
