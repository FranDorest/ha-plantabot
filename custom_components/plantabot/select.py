"""Entidades select editables de PlantaBot (ciclo de vida y fenología)."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlantaBotConfigEntry
from .const import (
    CICLO_OPTIONS,
    CONF_NAME,
    DOMAIN,
    FENO_OPTIONS,
    META_CICLO,
    META_FENOLOGIA,
)
from .coordinator import PlantaBotCoordinator


@dataclass(frozen=True, kw_only=True)
class PBSelectDescription(SelectEntityDescription):
    meta_key: str


SELECTS: tuple[PBSelectDescription, ...] = (
    PBSelectDescription(
        key="ciclo_vida", translation_key="ciclo_vida", meta_key=META_CICLO,
        options=CICLO_OPTIONS, icon="mdi:tree-outline",
    ),
    PBSelectDescription(
        key="fenologia", translation_key="fenologia", meta_key=META_FENOLOGIA,
        options=FENO_OPTIONS, icon="mdi:leaf",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantaBotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(PBSelect(coordinator, entry, d) for d in SELECTS)


class PBSelect(SelectEntity):
    """Desplegable editable persistido en el coordinator."""

    _attr_has_entity_name = True
    entity_description: PBSelectDescription

    def __init__(self, coordinator: PlantaBotCoordinator, entry: PlantaBotConfigEntry,
                 description: PBSelectDescription) -> None:
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        name = entry.data.get(CONF_NAME, entry.title)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"PlantaBot {name}",
            manufacturer="PlantaBot",
        )

    @property
    def current_option(self) -> str | None:
        return self.coordinator.metadata.get(self.entity_description.meta_key)  # type: ignore[return-value]

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_metadata(self.entity_description.meta_key, option)
        self.async_write_ha_state()
