"""Sensores de PlantaBot.

Tres familias:
  1) CALCULADOS: Kc, ETc, litros, recomendaciones, medias de suelo (y balance si hay
     caudal). Siempre presentes (algunos condicionados a que haya datos).
  2) REFLEJO tipado de la telemetría del nodo: como TTN entrega texto sin unidades,
     PlantaBot re-expone cada campo con device_class/unit correctos (temp, presión,
     kPa individuales, temp de suelo individuales), para que entren en histórico.
  3) DIAGNÓSTICO (entity_category=diagnostic): batería, CPU, ciclo, uptime, GPS y
     timestamp de última lectura.

Las entidades de reflejo/diagnóstico SOLO se crean si el campo existe en el nodo.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PlantaBotConfigEntry
from .const import (
    CICLO_STAGES,
    CONF_NAME,
    DOMAIN,
    FENO_STAGES,
    FERT_STATES,
    IRRIGATION_STATES,
)
from .coordinator import PlantaBotCoordinator, PlantaBotData


@dataclass(frozen=True, kw_only=True)
class PlantaBotSensorDescription(SensorEntityDescription):
    """Descripción con extractor del valor desde PlantaBotData."""

    value_fn: Callable[[PlantaBotData], float | str | datetime | None]


def _node(field: str) -> Callable[[PlantaBotData], float | None]:
    """value_fn que lee un campo reflejado del nodo."""
    return lambda d: d.node_values.get(field)


# --- 1) CALCULADOS siempre presentes -----------------------------------------
COMPUTED_ALWAYS: tuple[PlantaBotSensorDescription, ...] = (
    PlantaBotSensorDescription(
        key="kc", translation_key="kc", icon="mdi:sprout",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.kc,
    ),
    PlantaBotSensorDescription(
        key="kc_efectivo", translation_key="kc_efectivo", icon="mdi:sprout-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.kc_efectivo,
    ),
    PlantaBotSensorDescription(
        key="cobertura", translation_key="cobertura", native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT, icon="mdi:tree",
        value_fn=lambda d: round(d.shading * 100, 1) if d.shading is not None else None,
    ),
    PlantaBotSensorDescription(
        key="etc", translation_key="etc", native_unit_of_measurement="mm",
        state_class=SensorStateClass.MEASUREMENT, icon="mdi:water-percent",
        value_fn=lambda d: d.etc,
    ),
    PlantaBotSensorDescription(
        key="litros_objetivo", translation_key="litros_objetivo",
        native_unit_of_measurement="L", state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cup-water", value_fn=lambda d: d.litros_objetivo,
    ),
    PlantaBotSensorDescription(
        key="deficit_acumulado", translation_key="deficit_acumulado",
        native_unit_of_measurement="L", state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-minus", value_fn=lambda d: d.deficit_l,
    ),
    PlantaBotSensorDescription(
        key="lluvia_prevista", translation_key="lluvia_prevista",
        native_unit_of_measurement="mm", state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-rainy", value_fn=lambda d: d.rain_forecast_mm,
    ),
    PlantaBotSensorDescription(
        key="recomendacion_riego", translation_key="recomendacion_riego",
        device_class=SensorDeviceClass.ENUM, options=IRRIGATION_STATES,
        icon="mdi:water-alert", value_fn=lambda d: d.irrigation_rec,
    ),
    PlantaBotSensorDescription(
        key="recomendacion_abono", translation_key="recomendacion_abono",
        device_class=SensorDeviceClass.ENUM, options=FERT_STATES,
        icon="mdi:nutrition", value_fn=lambda d: d.fertilizer_rec,
    ),
    PlantaBotSensorDescription(
        key="salud", translation_key="salud", native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT, icon="mdi:heart-pulse",
        value_fn=lambda d: d.health_pct,
    ),
    PlantaBotSensorDescription(
        key="cosecha", translation_key="cosecha", native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT, icon="mdi:fruit-cherries",
        value_fn=lambda d: d.harvest_pct,
    ),
    PlantaBotSensorDescription(
        key="ciclo_calc", translation_key="ciclo_calc",
        device_class=SensorDeviceClass.ENUM, options=CICLO_STAGES,
        icon="mdi:tree-outline", value_fn=lambda d: d.ciclo_efectivo,
    ),
    PlantaBotSensorDescription(
        key="feno_calc", translation_key="feno_calc",
        device_class=SensorDeviceClass.ENUM, options=FENO_STAGES,
        icon="mdi:leaf", value_fn=lambda d: d.fenologia_efectiva,
    ),
)

# Medias de suelo (condicionadas a que haya sensores)
AGG_TENSION = PlantaBotSensorDescription(
    key="tension_suelo", translation_key="tension_suelo",
    native_unit_of_measurement="kPa", state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:gauge", value_fn=lambda d: d.watermark_kpa,
)
AGG_TEMP = PlantaBotSensorDescription(
    key="temp_suelo", translation_key="temp_suelo",
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda d: d.soil_temp_c,
)
BALANCE = PlantaBotSensorDescription(
    key="balance_hidrico", translation_key="balance_hidrico",
    native_unit_of_measurement="L", state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:scale-balance", value_fn=lambda d: d.balance_l,
)
LAST_READ = PlantaBotSensorDescription(
    key="ultima_lectura", translation_key="ultima_lectura",
    device_class=SensorDeviceClass.TIMESTAMP, entity_category=EntityCategory.DIAGNOSTIC,
    icon="mdi:clock-outline", value_fn=lambda d: d.last_read,
)


# --- 2) y 3) REFLEJO/DIAGNÓSTICO por campo del nodo --------------------------
@dataclass(frozen=True)
class NodeSpec:
    field: str
    key: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT
    category: EntityCategory | None = None
    icon: str | None = None


NODE_SPECS: tuple[NodeSpec, ...] = (
    # Watermark individuales (kPa)
    NodeSpec("wm1_kpa", "wm_1", "kPa", icon="mdi:gauge"),
    NodeSpec("wm2_kpa", "wm_2", "kPa", icon="mdi:gauge"),
    NodeSpec("wm3_kpa", "wm_3", "kPa", icon="mdi:gauge"),
    # Temperatura de suelo individuales (°C)
    NodeSpec("ds1_temp_c", "ds_1", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    NodeSpec("ds2_temp_c", "ds_2", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    NodeSpec("ds3_temp_c", "ds_3", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    # Ambiente (BME)
    NodeSpec("bmp_temp_c", "amb_temp", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    NodeSpec("bmp_pres_hpa", "amb_pres", UnitOfPressure.HPA, SensorDeviceClass.PRESSURE),
    # Diagnóstico
    NodeSpec("bateria_pct", "bat_pct", "%", SensorDeviceClass.BATTERY,
             category=EntityCategory.DIAGNOSTIC),
    NodeSpec("bateria_v", "bat_v", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE,
             category=EntityCategory.DIAGNOSTIC),
    NodeSpec("bateria_mv", "bat_mv", UnitOfElectricPotential.MILLIVOLT, SensorDeviceClass.VOLTAGE,
             category=EntityCategory.DIAGNOSTIC),
    NodeSpec("cpu_temp_c", "cpu_temp", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE,
             category=EntityCategory.DIAGNOSTIC),
    NodeSpec("uptime_s", "uptime", UnitOfTime.SECONDS, SensorDeviceClass.DURATION,
             category=EntityCategory.DIAGNOSTIC),
    NodeSpec("ciclo_ms", "ciclo", "ms", None, category=EntityCategory.DIAGNOSTIC,
             icon="mdi:timer-sand"),
    NodeSpec("latitude", "lat", None, None, state_class=None,
             category=EntityCategory.DIAGNOSTIC, icon="mdi:latitude"),
    NodeSpec("longitude", "lon", None, None, state_class=None,
             category=EntityCategory.DIAGNOSTIC, icon="mdi:longitude"),
)


def _desc_from_spec(spec: NodeSpec) -> PlantaBotSensorDescription:
    return PlantaBotSensorDescription(
        key=spec.key,
        translation_key=spec.key,
        native_unit_of_measurement=spec.unit,
        device_class=spec.device_class,
        state_class=spec.state_class,
        entity_category=spec.category,
        icon=spec.icon,
        value_fn=_node(spec.field),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantaBotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    resolved = coordinator.resolved
    nm = resolved.node_map

    descs: list[PlantaBotSensorDescription] = list(COMPUTED_ALWAYS)
    if resolved.watermarks:
        descs.append(AGG_TENSION)
    if resolved.soil_temps:
        descs.append(AGG_TEMP)
    if resolved.flow_daily or resolved.flow_total:
        descs.append(BALANCE)
    if nm:
        descs.append(LAST_READ)
    # Reflejo/diagnóstico solo para campos presentes en el nodo
    descs.extend(_desc_from_spec(s) for s in NODE_SPECS if s.field in nm)

    async_add_entities(PlantaBotSensor(coordinator, entry, d) for d in descs)


class PlantaBotSensor(CoordinatorEntity[PlantaBotCoordinator], SensorEntity):
    """Una entidad derivada/reflejada de un árbol PlantaBot."""

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
    def native_value(self) -> float | str | datetime | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict | None:
        d = self.coordinator.data
        key = self.entity_description.key
        if key == "tension_suelo":
            return {"num_watermark": d.n_watermark, "valores_kpa": d.watermark_values}
        if key == "recomendacion_riego":
            return {
                "num_watermark": d.n_watermark,
                "valores_kpa": d.watermark_values,
                "litros_recomendados": d.deficit_l,
                "ultimo_riego": d.last_irrigation,
            }
        if key in ("temp_suelo", "recomendacion_abono"):
            return {"num_ds18b20": d.n_soil_temp, "valores_c": d.soil_temp_values}
        if key == "salud":
            return {"detalle": d.health_detail} if d.health_detail else None
        if key == "kc_efectivo":
            return {"kc_base": d.kc, "kr": d.kr, "sombreo": d.shading}
        if key == "deficit_acumulado":
            return {"ultimo_riego": d.last_irrigation}
        if key == "lluvia_prevista":
            return {"probabilidad_max": d.rain_forecast_prob}
        return None
