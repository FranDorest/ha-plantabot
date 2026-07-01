"""Entidad date editable de PlantaBot (fecha de cuajado del fruto)."""
from __future__ import annotations

from datetime import date

from homeassistant.components.date import DateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlantaBotConfigEntry
from .const import CONF_NAME, DOMAIN, META_FECHA_CUAJADO
from .coordinator import PlantaBotCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantaBotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([PBDateCuajado(coordinator, entry)])


class PBDateCuajado(DateEntity):
    """Fecha de cuajado, editable y persistida (ISO en el store)."""

    _attr_has_entity_name = True
    _attr_translation_key = "fecha_cuajado"
    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator: PlantaBotCoordinator, entry: PlantaBotConfigEntry) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_fecha_cuajado"
        name = entry.data.get(CONF_NAME, entry.title)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"PlantaBot {name}",
            manufacturer="PlantaBot",
        )

    @property
    def native_value(self) -> date | None:
        raw = self.coordinator.metadata.get(META_FECHA_CUAJADO)
        if not raw:
            return None
        try:
            return date.fromisoformat(str(raw))
        except ValueError:
            return None

    async def async_set_value(self, value: date) -> None:
        await self.coordinator.async_set_metadata(META_FECHA_CUAJADO, value.isoformat())
        self.async_write_ha_state()
