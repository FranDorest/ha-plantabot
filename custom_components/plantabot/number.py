"""Entidades number editables de PlantaBot (medidas y análisis de laboratorio)."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlantaBotConfigEntry
from .const import (
    CONF_NAME,
    DOMAIN,
    META_ALTURA,
    META_ANIO,
    META_CE,
    META_COPA,
    META_K,
    META_N,
    META_P,
    META_PH,
)
from .coordinator import PlantaBotCoordinator


@dataclass(frozen=True, kw_only=True)
class PBNumberDescription(NumberEntityDescription):
    meta_key: str


NUMBERS: tuple[PBNumberDescription, ...] = (
    PBNumberDescription(
        key="altura_m", translation_key="altura_m", meta_key=META_ALTURA,
        native_min_value=0.0, native_max_value=30.0, native_step=0.05,
        native_unit_of_measurement="m", icon="mdi:arrow-up-down", mode=NumberMode.BOX,
    ),
    PBNumberDescription(
        key="copa_m", translation_key="copa_m", meta_key=META_COPA,
        native_min_value=0.0, native_max_value=20.0, native_step=0.05,
        native_unit_of_measurement="m", icon="mdi:tree", mode=NumberMode.BOX,
    ),
    PBNumberDescription(
        key="anio_plantacion", translation_key="anio_plantacion", meta_key=META_ANIO,
        native_min_value=1950, native_max_value=2100, native_step=1,
        icon="mdi:calendar", mode=NumberMode.BOX,
    ),
    # Análisis de laboratorio
    PBNumberDescription(
        key="ph", translation_key="ph", meta_key=META_PH,
        native_min_value=0.0, native_max_value=14.0, native_step=0.1,
        icon="mdi:flask", mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG,
    ),
    PBNumberDescription(
        key="ce", translation_key="ce", meta_key=META_CE,
        native_min_value=0.0, native_max_value=20.0, native_step=0.1,
        native_unit_of_measurement="dS/m", icon="mdi:flash",
        mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG,
    ),
    PBNumberDescription(
        key="n", translation_key="n", meta_key=META_N,
        native_min_value=0.0, native_max_value=10000.0, native_step=1,
        native_unit_of_measurement="ppm", icon="mdi:alpha-n-box",
        mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG,
    ),
    PBNumberDescription(
        key="p", translation_key="p", meta_key=META_P,
        native_min_value=0.0, native_max_value=10000.0, native_step=1,
        native_unit_of_measurement="ppm", icon="mdi:alpha-p-box",
        mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG,
    ),
    PBNumberDescription(
        key="k", translation_key="k", meta_key=META_K,
        native_min_value=0.0, native_max_value=10000.0, native_step=1,
        native_unit_of_measurement="ppm", icon="mdi:alpha-k-box",
        mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantaBotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(PBNumber(coordinator, entry, d) for d in NUMBERS)


class PBNumber(NumberEntity):
    """Número editable persistido en el coordinator."""

    _attr_has_entity_name = True
    entity_description: PBNumberDescription

    def __init__(self, coordinator: PlantaBotCoordinator, entry: PlantaBotConfigEntry,
                 description: PBNumberDescription) -> None:
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
    def native_value(self) -> float | None:
        val = self.coordinator.metadata.get(self.entity_description.meta_key)
        return float(val) if val is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_metadata(self.entity_description.meta_key, value)
        self.async_write_ha_state()
