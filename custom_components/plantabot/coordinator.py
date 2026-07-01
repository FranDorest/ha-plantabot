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
from dataclasses import dataclass, field
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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
    FLOW_RATE_HINTS,
    FLOW_TOTAL_HINTS,
    MAX_SOIL_TEMP,
    MAX_WATERMARK,
    NON_SOIL_TEMP_HINTS,
    REC_IRRIGATE,
    REC_IRRIGATE_NO_SOIL,
    REC_NO_IRRIGATE,
    SOIL_TEMP_HINTS,
    WATERMARK_UNITS,
)
from .crops import get_kc

_LOGGER = logging.getLogger(__name__)


@dataclass
class ResolvedEntities:
    """Entidades del nodo resueltas (auto o por override manual)."""

    flow_total: str | None = None
    flow_daily: str | None = None
    watermarks: list[str] = field(default_factory=list)
    soil_temps: list[str] = field(default_factory=list)

    def all_tracked(self, extra: list[str | None]) -> list[str]:
        """Lista de entity_ids a vigilar (sin None ni duplicados)."""
        ids = [
            self.flow_total,
            self.flow_daily,
            *self.watermarks,
            *self.soil_temps,
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
    irrigation_rec: str | None = None
    fertilizer_rec: str = FERT_NO_DATA
    balance_l: float | None = None
    litros_medidos_dia: float | None = None


def _to_float(state: State | None) -> float | None:
    """Convierte un State a float o None si no es numérico/disponible."""
    if state is None or state.state in (None, "unknown", "unavailable", ""):
        return None
    try:
        return float(state.state)
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

        for ent in entries:
            eid = ent.entity_id
            low = eid.lower()
            name_low = (ent.original_name or ent.name or "").lower()
            state = self.hass.states.get(eid)
            unit = (state.attributes.get("unit_of_measurement", "") if state else "").lower()

            # Watermark -> unidad kPa (solo si no vino por override manual)
            if unit in WATERMARK_UNITS and not wm_override:
                if len(res.watermarks) < MAX_WATERMARK and eid not in res.watermarks:
                    res.watermarks.append(eid)
                continue

            # Temperatura de suelo (DS18B20) -> °C + pista de suelo, excluyendo BMP/CPU/aire
            is_soil_hint = any(h in low or h in name_low for h in SOIL_TEMP_HINTS)
            is_non_soil = any(h in low or h in name_low for h in NON_SOIL_TEMP_HINTS)
            if unit in ("°c", "c") and is_soil_hint and not is_non_soil and not st_override:
                if len(res.soil_temps) < MAX_SOIL_TEMP and eid not in res.soil_temps:
                    res.soil_temps.append(eid)
                continue

            # Litros acumulados (caudalímetro)
            if res.flow_total is None and any(h in low or h in name_low for h in FLOW_TOTAL_HINTS):
                res.flow_total = eid
                continue

        return res

    # ---- ciclo de vida ------------------------------------------------------
    async def async_setup(self) -> None:
        """Resuelve entidades y engancha el seguimiento de cambios de estado."""
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

    # ---- cálculo ------------------------------------------------------------
    async def _async_update_data(self) -> PlantaBotData:
        return self._compute()

    def _mean_of(self, entity_ids: list[str]) -> tuple[float | None, int]:
        vals = [
            v for v in (_to_float(self.hass.states.get(e)) for e in entity_ids) if v is not None
        ]
        if not vals:
            return None, 0
        return sum(vals) / len(vals), len(vals)

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

        # Suelo: Watermark (kPa) y temperatura (°C), agregados por media
        data.watermark_kpa, data.n_watermark = self._mean_of(self.resolved.watermarks)
        if data.watermark_kpa is not None:
            data.watermark_kpa = round(data.watermark_kpa, 1)
        data.soil_temp_c, data.n_soil_temp = self._mean_of(self.resolved.soil_temps)
        if data.soil_temp_c is not None:
            data.soil_temp_c = round(data.soil_temp_c, 1)

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

        return data
