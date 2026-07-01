"""Sensores derivados de PlantaBot (uno o varios por árbol)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PlantaBotConfigEntry
from .const import (
    CONF_NAME,
    DOMAIN,
    FERT_STATES,
    IRRIGATION_STATES,
)
from .coordinator import PlantaBotCoordinator, PlantaBotData


@dataclass(frozen=True, kw_only=True)
class PlantaBotSensorDescription(SensorEntityDescription):
    """Descripción de sensor con extractor del valor desde PlantaBotData."""

    value_fn: Callable[[PlantaBotData], float | str | None]


SENSORS: tuple[PlantaBotSensorDescription, ...] = (
    PlantaBotSensorDescription(
        key="kc",
        translation_key="kc",
        icon="mdi:sprout",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.kc,
    ),
    PlantaBotSensorDescription(
        key="etc",
        translation_key="etc",
        native_unit_of_measurement="mm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
        value_fn=lambda d: d.etc,
    ),
    PlantaBotSensorDescription(
        key="litros_objetivo",
        translation_key="litros_objetivo",
        native_unit_of_measurement="L",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cup-water",
        value_fn=lambda d: d.litros_objetivo,
    ),
    PlantaBotSensorDescription(
        key="recomendacion_riego",
        translation_key="recomendacion_riego",
        device_class=SensorDeviceClass.ENUM,
        options=IRRIGATION_STATES,
        icon="mdi:water-alert",
        value_fn=lambda d: d.irrigation_rec,
    ),
    PlantaBotSensorDescription(
        key="tension_suelo",
        translation_key="tension_suelo",
        native_unit_of_measurement="kPa",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge",
        value_fn=lambda d: d.watermark_kpa,
    ),
    PlantaBotSensorDescription(
        key="temp_suelo",
        translation_key="temp_suelo",
        native_unit_of_measurement="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.soil_temp_c,
    ),
    PlantaBotSensorDescription(
        key="recomendacion_abono",
        translation_key="recomendacion_abono",
        device_class=SensorDeviceClass.ENUM,
        options=FERT_STATES,
        icon="mdi:nutrition",
        value_fn=lambda d: d.fertilizer_rec,
    ),
    PlantaBotSensorDescription(
        key="balance_hidrico",
        translation_key="balance_hidrico",
        native_unit_of_measurement="L",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:scale-balance",
        value_fn=lambda d: d.balance_l,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantaBotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        PlantaBotSensor(coordinator, entry, desc) for desc in SENSORS
    )


class PlantaBotSensor(CoordinatorEntity[PlantaBotCoordinator], SensorEntity):
    """Un valor derivado de un árbol PlantaBot."""

    _attr_has_entity_name = True
    entity_description: PlantaBotSensorDescription

    def __init__(
        self,
        coordinator: PlantaBotCoordinator,
        entry: PlantaBotConfigEntry,
        description: PlantaBotSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        name = entry.data.get(CONF_NAME, entry.title)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"PlantaBot {name}",
            manufacturer="PlantaBot",
            model=entry.data.get("crop"),
        )

    @property
    def native_value(self) -> float | str | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, int] | None:
        """Diagnóstico útil: cuántos sensores de suelo se están usando."""
        if self.entity_description.key in ("tension_suelo", "recomendacion_riego"):
            return {"num_watermark": self.coordinator.data.n_watermark}
        if self.entity_description.key in ("temp_suelo", "recomendacion_abono"):
            return {"num_ds18b20": self.coordinator.data.n_soil_temp}
        return None
