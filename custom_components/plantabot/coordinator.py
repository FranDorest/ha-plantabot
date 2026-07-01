"""Motor de cálculo de PlantaBot.

A diferencia de SiAR, PlantaBot NO consulta ninguna API: deriva sus valores de otras
entidades de HA (la ETo de SiAR y la telemetría del nodo LoRaWAN). Por eso no hay
polling: se usa un DataUpdateCoordinator sin intervalo, que se refresca cuando cambian
las entidades de las que depende (async_track_state_change_event).

Diseño clave (según brief):
- 0..3 Watermark (kPa) y 0..3 DS18B20 (°C), auto-resueltos desde el device del nodo.
- Si falta un tipo de sensor, NO peta: se cae en modo degradado y se marca en el estado.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AREA,
    CONF_CROP,
    CONF_DRY_THRESHOLD,
    CONF_EFFICIENCY,
    CONF_ETO_ENTITY,
    CONF_FERT_MAX,
    CONF_FERT_MIN,
    CONF_FLOW_DAILY_ENTITY,
    CONF_FLOW_TOTAL_ENTITY,
    CONF_KC_OVERRIDE,
    CONF_NODE_DEVICE,
    CONF_RAIN_ENTITY,
    CONF_SOIL_TEMP_ENTITIES,
    CONF_WATERMARK_ENTITIES,
    DEFAULT_AREA,
    DEFAULT_DRY_THRESHOLD,
    DEFAULT_EFFICIENCY,
    DEFAULT_FERT_MAX,
    DEFAULT_FERT_MIN,
    DOMAIN,
    FERT_COLD,
    FERT_GOOD,
    FERT_HOT,
    FERT_NO_DATA,
    FLOW_TOTAL_MATCH,
    MAX_SOIL_TEMP,
    MAX_WATERMARK,
    NODE_FIELD_KEYS,
    DS_FIELDS,
    WM_FIELDS,
    REC_IRRIGATE,
    REC_IRRIGATE_NO_SOIL,
    REC_NO_IRRIGATE,
    SOIL_TEMP_REGEX,
    WATERMARK_MATCH,
    META_DEFAULTS,
    META_PH,
    META_CE,
    META_FENOLOGIA,
    NODE_ONLINE_MAX_AGE_S,
    STORE_VERSION,
)
from .crops import get_kc
from .health import harvest_progress, tree_health

_LOGGER = logging.getLogger(__name__)


def _classify(object_id: str, name: str) -> str | None:
    """Clasifica una entidad del nodo por su NOMBRE (no por unidad).

    Los sensores de TTN llegan como texto sin unidades, así que la única pista
    fiable es el nombre. Devuelve 'watermark' | 'soil_temp' | 'flow_total' | None.

    Ejemplos con los nombres reales del nodo:
      wm1_kpa/wm2_kpa/wm3_kpa -> watermark
      ds1_temp_c/ds2/ds3      -> soil_temp
      bmp_temp_c / cpu_temp_c -> None (temperatura que NO es de suelo)
      bmp_pres_hpa            -> None ('hpa' != 'kpa')
      litros                  -> flow_total
    """
    hay = f"{object_id} {name}".lower()
    if WATERMARK_MATCH in hay:
        return "watermark"
    if re.search(SOIL_TEMP_REGEX, hay):
        return "soil_temp"
    if any(m in hay for m in FLOW_TOTAL_MATCH):
        return "flow_total"
    return None


@dataclass
class ResolvedEntities:
    """Entidades del nodo resueltas (auto o por override manual)."""

    flow_total: str | None = None
    flow_daily: str | None = None
    watermarks: list[str] = field(default_factory=list)
    soil_temps: list[str] = field(default_factory=list)
    node_map: dict[str, str] = field(default_factory=dict)  # campo canónico -> entity_id

    def all_tracked(self, extra: list[str | None]) -> list[str]:
        """Lista de entity_ids a vigilar (sin None ni duplicados)."""
        ids = [
            self.flow_total,
            self.flow_daily,
            *self.watermarks,
            *self.soil_temps,
            *self.node_map.values(),
            *extra,
        ]
        seen: list[str] = []
        for eid in ids:
            if eid and eid not in seen:
                seen.append(eid)
        return seen


@dataclass
class PlantaBotData:
    """Resultado del cálculo que consumen los sensores."""

    kc: float | None = None
    eto: float | None = None
    rain_eff: float | None = None
    etc: float | None = None
    litros_objetivo: float | None = None
    watermark_kpa: float | None = None
    soil_temp_c: float | None = None
    n_watermark: int = 0
    n_soil_temp: int = 0
    watermark_values: list[float] = field(default_factory=list)
    soil_temp_values: list[float] = field(default_factory=list)
    irrigation_rec: str | None = None
    fertilizer_rec: str = FERT_NO_DATA
    balance_l: float | None = None
    litros_medidos_dia: float | None = None
    # Telemetría del nodo reflejada (campo canónico -> valor) + última lectura
    node_values: dict[str, float | None] = field(default_factory=dict)
    last_read: datetime | None = None
    # Índices calculados
    health_pct: float | None = None
    health_detail: dict[str, float] = field(default_factory=dict)
    harvest_pct: float | None = None


def _to_float(state: State | None) -> float | None:
    """Convierte un State a float o None si no es numérico/disponible."""
    if state is None or state.state in (None, "unknown", "unavailable", ""):
        return None
    try:
        return float(state.state)
    except (ValueError, TypeError):
        return None


def _meta_float(value: object) -> float | None:
    """Convierte un metadato a float o None."""
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None


class PlantaBotCoordinator(DataUpdateCoordinator[PlantaBotData]):
    """Coordinator sin polling; se refresca ante cambios de las fuentes."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.title}",
            update_interval=None,  # no polling: refresco por eventos de estado
        )
        self.entry = entry
        self.resolved = ResolvedEntities()
        self._store: Store = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.metadata: dict[str, object] = dict(META_DEFAULTS)

    # ---- ajustes efectivos (data + options) --------------------------------
    def _opt(self, key: str, default):
        return self.entry.options.get(key, self.entry.data.get(key, default))

    # ---- resolución de entidades del nodo ----------------------------------
    def _resolve_node_entities(self) -> ResolvedEntities:
        """Auto-resuelve las entidades del nodo desde su device.

        Los overrides manuales (options) tienen prioridad. Todo es opcional:
        si no se encuentra algo, se deja vacío y el cálculo lo tolera.
        """
        res = ResolvedEntities()

        # 1) Overrides manuales (flujo avanzado / opciones)
        res.flow_total = self._opt(CONF_FLOW_TOTAL_ENTITY, None)
        res.flow_daily = self._opt(CONF_FLOW_DAILY_ENTITY, None)
        wm_override = self._opt(CONF_WATERMARK_ENTITIES, None)
        st_override = self._opt(CONF_SOIL_TEMP_ENTITIES, None)
        if wm_override:
            res.watermarks = list(wm_override)[:MAX_WATERMARK]
        if st_override:
            res.soil_temps = list(st_override)[:MAX_SOIL_TEMP]

        # 2) Auto-resolución desde el device (para lo que no venga por override)
        device_id = self.entry.data.get(CONF_NODE_DEVICE)
        if not device_id:
            return res

        ent_reg = er.async_get(self.hass)
        entries = er.async_entries_for_device(ent_reg, device_id, include_disabled_entities=False)

        # Mapa completo campo canónico -> entity_id (por substring del object_id)
        node_map: dict[str, str] = {}
        for ent in entries:
            object_id = ent.entity_id.split(".", 1)[-1].lower()
            for field_key in NODE_FIELD_KEYS:
                if field_key in object_id and field_key not in node_map:
                    node_map[field_key] = ent.entity_id
                    break
        res.node_map = node_map

        # Listas derivadas (respetando overrides manuales)
        if not wm_override:
            res.watermarks = [node_map[f] for f in WM_FIELDS if f in node_map][:MAX_WATERMARK]
        if not st_override:
            res.soil_temps = [node_map[f] for f in DS_FIELDS if f in node_map][:MAX_SOIL_TEMP]
        if res.flow_total is None:
            res.flow_total = node_map.get("litros")

        return res

    # ---- ciclo de vida ------------------------------------------------------
    async def async_setup(self) -> None:
        """Resuelve entidades, carga metadatos y engancha el seguimiento de estados."""
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            # solo claves conocidas, respetando defaults para las que falten
            for k in META_DEFAULTS:
                if k in stored:
                    self.metadata[k] = stored[k]

        self.resolved = self._resolve_node_entities()
        extra = [
            self.entry.data.get(CONF_ETO_ENTITY),
            self.entry.data.get(CONF_RAIN_ENTITY),
        ]
        tracked = self.resolved.all_tracked(extra)
        if tracked:
            self.entry.async_on_unload(
                async_track_state_change_event(self.hass, tracked, self._handle_source_change)
            )
        _LOGGER.debug(
            "%s resuelto: flow=%s wm=%s soil=%s",
            self.entry.title,
            self.resolved.flow_total,
            self.resolved.watermarks,
            self.resolved.soil_temps,
        )

    @callback
    def _handle_source_change(self, event: Event) -> None:
        """Recalcula cuando cambia una fuente."""
        self.async_set_updated_data(self._compute())

    async def async_set_metadata(self, key: str, value: object) -> None:
        """Actualiza un metadato editable, lo persiste y recalcula."""
        self.metadata[key] = value
        await self._store.async_save(self.metadata)
        self.async_set_updated_data(self._compute())

    # ---- cálculo ------------------------------------------------------------
    async def _async_update_data(self) -> PlantaBotData:
        return self._compute()

    def _values_of(self, entity_ids: list[str]) -> list[float]:
        return [
            v for v in (_to_float(self.hass.states.get(e)) for e in entity_ids) if v is not None
        ]

    def _compute(self) -> PlantaBotData:
        data = PlantaBotData()

        # Fuentes principales
        data.eto = _to_float(self.hass.states.get(self.entry.data.get(CONF_ETO_ENTITY, "")))
        data.rain_eff = _to_float(self.hass.states.get(self.entry.data.get(CONF_RAIN_ENTITY, "")))

        # Kc del mes (o override)
        crop = self.entry.data.get(CONF_CROP)
        kc_override = self._opt(CONF_KC_OVERRIDE, None)
        month = datetime.now().month
        data.kc = get_kc(crop, month, kc_override)

        # ETc = ETo * Kc
        if data.eto is not None and data.kc is not None:
            data.etc = round(data.eto * data.kc, 3)

        # Litros objetivo = max(ETc - precip_efectiva, 0) * área / eficiencia
        area = float(self._opt(CONF_AREA, DEFAULT_AREA))
        eff = float(self._opt(CONF_EFFICIENCY, DEFAULT_EFFICIENCY)) / 100.0
        if data.etc is not None:
            rain = data.rain_eff or 0.0
            deficit_mm = max(data.etc - rain, 0.0)
            # 1 mm sobre 1 m² = 1 litro
            if eff > 0:
                data.litros_objetivo = round(deficit_mm * area / eff, 1)

        # Suelo: Watermark (kPa) y temperatura (°C). Media para decidir; se guardan
        # además los valores individuales (wm1/2/3, ds1/2/3) como diagnóstico.
        data.watermark_values = self._values_of(self.resolved.watermarks)
        data.n_watermark = len(data.watermark_values)
        if data.watermark_values:
            data.watermark_kpa = round(sum(data.watermark_values) / data.n_watermark, 1)

        data.soil_temp_values = self._values_of(self.resolved.soil_temps)
        data.n_soil_temp = len(data.soil_temp_values)
        if data.soil_temp_values:
            data.soil_temp_c = round(sum(data.soil_temp_values) / data.n_soil_temp, 1)

        # Recomendación de riego (cruce cálculo x Watermark)
        dry_th = float(self._opt(CONF_DRY_THRESHOLD, DEFAULT_DRY_THRESHOLD))
        if data.watermark_kpa is None:
            # Sin dato de suelo aún: recomendar por ETo y avisar
            data.irrigation_rec = REC_IRRIGATE_NO_SOIL if (data.litros_objetivo or 0) > 0 else REC_NO_IRRIGATE
        elif data.watermark_kpa >= dry_th:
            data.irrigation_rec = REC_IRRIGATE
        else:
            data.irrigation_rec = REC_NO_IRRIGATE

        # Recomendación de abonado (por temperatura de suelo del DS18B20)
        fert_min = float(self._opt(CONF_FERT_MIN, DEFAULT_FERT_MIN))
        fert_max = float(self._opt(CONF_FERT_MAX, DEFAULT_FERT_MAX))
        if data.soil_temp_c is None:
            data.fertilizer_rec = FERT_NO_DATA
        elif data.soil_temp_c < fert_min:
            data.fertilizer_rec = FERT_COLD
        elif data.soil_temp_c > fert_max:
            data.fertilizer_rec = FERT_HOT
        else:
            data.fertilizer_rec = FERT_GOOD

        # Balance hídrico: litros medidos hoy vs objetivo (si hay contador diario)
        if self.resolved.flow_daily:
            data.litros_medidos_dia = _to_float(self.hass.states.get(self.resolved.flow_daily))
            if data.litros_medidos_dia is not None and data.litros_objetivo is not None:
                data.balance_l = round(data.litros_medidos_dia - data.litros_objetivo, 1)

        # Reflejo de la telemetría del nodo (tipada) + timestamp de última lectura
        last: datetime | None = None
        for field_key, eid in self.resolved.node_map.items():
            st = self.hass.states.get(eid)
            data.node_values[field_key] = _to_float(st)
            if st is not None and st.last_updated is not None:
                last = st.last_updated if last is None else max(last, st.last_updated)
        data.last_read = last

        # Índices calculados: salud del árbol y progreso de cosecha
        age_s = None
        if last is not None:
            age_s = (dt_util.utcnow() - last).total_seconds()
        data.health_pct, data.health_detail = tree_health(
            wm_kpa=data.watermark_kpa,
            soil_t=data.soil_temp_c,
            battery_pct=data.node_values.get("bateria_pct"),
            node_age_s=age_s,
            ph=_meta_float(self.metadata.get(META_PH)),
            ce=_meta_float(self.metadata.get(META_CE)),
            dry_threshold=dry_th,
            max_age_s=NODE_ONLINE_MAX_AGE_S,
        )
        data.harvest_pct = harvest_progress(self.metadata.get(META_FENOLOGIA))

        return data
