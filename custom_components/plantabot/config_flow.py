"""Config flow de PlantaBot (un árbol/punto de riego por entrada)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AREA,
    CONF_CANOPY_AUTO,
    CONF_CROP,
    CONF_DRY_THRESHOLD,
    CONF_EFFICIENCY,
    CONF_ETO_ENTITY,
    CONF_FERT_MAX,
    CONF_FERT_MIN,
    CONF_FLOW_DAILY_ENTITY,
    CONF_FLOW_TOTAL_ENTITY,
    CONF_KC_OVERRIDE,
    CONF_MIN_IRRIGATION,
    CONF_MAX_DEFICIT,
    CONF_NAME,
    CONF_NODE_DEVICE,
    CONF_RAIN_ENTITY,
    CONF_WEATHER_ENTITY,
    CONF_RAIN_SKIP,
    CONF_SOIL_TEMP_ENTITIES,
    CONF_WATERMARK_ENTITIES,
    CROPS,
    DEFAULT_AREA,
    DEFAULT_CANOPY_AUTO,
    DEFAULT_DRY_THRESHOLD,
    DEFAULT_EFFICIENCY,
    DEFAULT_FERT_MAX,
    DEFAULT_FERT_MIN,
    DEFAULT_MIN_IRRIGATION,
    DEFAULT_MAX_DEFICIT,
    DEFAULT_RAIN_SKIP,
    DOMAIN,
)

# Selector de la ETo y de la precip. efectiva: filtrado a la integración SiAR para
# que en el desplegable solo aparezcan esas entidades.
_ETO_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(integration="siar", domain="sensor")
)

# Selector del nodo por DEVICE (formulario corto): se elige "RAK4631 …" una vez y
# PlantaBot resuelve por dentro sus entidades (litros, Watermark, DS18B20).
_NODE_SELECTOR = selector.DeviceSelector(selector.DeviceSelectorConfig())

_WEATHER_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="weather")
)

_CROP_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=CROPS,
        translation_key="crop",
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=d.get(CONF_NAME, "")): str,
            vol.Required(CONF_NODE_DEVICE): _NODE_SELECTOR,
            vol.Required(CONF_ETO_ENTITY): _ETO_SELECTOR,
            vol.Optional(CONF_RAIN_ENTITY): _ETO_SELECTOR,
            vol.Optional(CONF_WEATHER_ENTITY): _WEATHER_SELECTOR,
            vol.Required(CONF_CROP, default=d.get(CONF_CROP, CROPS[0])): _CROP_SELECTOR,
        }
    )


def _number(min_v, max_v, step, unit=None):
    """NumberSelector en modo caja. La unidad SOLO se incluye si no es None:
    HA valida `unit_of_measurement` como str y rechaza None (era el 'Unknown error')."""
    cfg: dict[str, Any] = {
        "min": min_v,
        "max": max_v,
        "step": step,
        "mode": selector.NumberSelectorMode.BOX,
    }
    if unit is not None:
        cfg["unit_of_measurement"] = unit
    return selector.NumberSelector(cfg)


def _params_schema(cur: dict[str, Any]) -> vol.Schema:
    """Parámetros ajustables (también usados por el OptionsFlow)."""
    # Kc opcional: solo ponemos default si ya hay valor guardado (evita default=None).
    kc = cur.get(CONF_KC_OVERRIDE)
    kc_key = (
        vol.Optional(CONF_KC_OVERRIDE, default=kc)
        if kc is not None
        else vol.Optional(CONF_KC_OVERRIDE)
    )
    return vol.Schema(
        {
            kc_key: _number(0.0, 2.0, 0.01),
            vol.Required(
                CONF_AREA, default=cur.get(CONF_AREA, DEFAULT_AREA)
            ): _number(0.1, 200.0, 0.1, "m²"),
            vol.Required(
                CONF_EFFICIENCY, default=cur.get(CONF_EFFICIENCY, DEFAULT_EFFICIENCY)
            ): _number(10.0, 100.0, 1.0, "%"),
            vol.Required(
                CONF_DRY_THRESHOLD, default=cur.get(CONF_DRY_THRESHOLD, DEFAULT_DRY_THRESHOLD)
            ): _number(0.0, 200.0, 1.0, "kPa"),
            vol.Required(
                CONF_FERT_MIN, default=cur.get(CONF_FERT_MIN, DEFAULT_FERT_MIN)
            ): _number(-5.0, 40.0, 0.5, "°C"),
            vol.Required(
                CONF_FERT_MAX, default=cur.get(CONF_FERT_MAX, DEFAULT_FERT_MAX)
            ): _number(-5.0, 50.0, 0.5, "°C"),
            vol.Required(
                CONF_CANOPY_AUTO, default=cur.get(CONF_CANOPY_AUTO, DEFAULT_CANOPY_AUTO)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_MIN_IRRIGATION,
    CONF_MAX_DEFICIT,
                default=cur.get(CONF_MIN_IRRIGATION, DEFAULT_MIN_IRRIGATION),
            ): _number(0.0, 500.0, 0.5, "L"),
            vol.Required(
                CONF_MAX_DEFICIT,
                default=cur.get(CONF_MAX_DEFICIT, DEFAULT_MAX_DEFICIT),
            ): _number(0.0, 2000.0, 5.0, "L"),
            vol.Required(
                CONF_RAIN_SKIP,
                default=cur.get(CONF_RAIN_SKIP, DEFAULT_RAIN_SKIP),
            ): _number(0.0, 50.0, 0.5, "mm"),
        }
    )


class PlantaBotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Alta de un árbol: paso 1 fuentes, paso 2 parámetros."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_params()
        return self.async_show_form(step_id="user", data_schema=_user_schema())

    async def async_step_params(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            # Los parámetros ajustables van a options (editables luego sin reconfigurar)
            options = {k: v for k, v in user_input.items() if v is not None}
            return self.async_create_entry(
                title=self._data[CONF_NAME], data=self._data, options=options
            )
        return self.async_show_form(step_id="params", data_schema=_params_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return PlantaBotOptionsFlow(entry)


class PlantaBotOptionsFlow(OptionsFlow):
    """Editar parámetros y, en 'avanzado', forzar entidades del nodo a mano."""

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._pending = dict(user_input)
            return await self.async_step_advanced()
        cur = {**self.entry.options}
        return self.async_show_form(step_id="init", data_schema=_params_schema(cur))

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Overrides manuales opcionales. Si se dejan vacíos, se auto-resuelve."""
        if user_input is not None:
            merged = {**self._pending, **{k: v for k, v in user_input.items() if v}}
            return self.async_create_entry(title="", data=merged)

        cur = {**self.entry.options}
        multi_entity = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", multiple=True)
        )
        single_entity = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )

        def _opt_key(conf: str, empty_default):
            """vol.Optional con default SOLO si hay valor previo (default=None
            con EntitySelector lanza Invalid al validar -> 'Unknown error')."""
            val = cur.get(conf, empty_default)
            if val:
                return vol.Optional(conf, default=val)
            return vol.Optional(conf)

        schema = vol.Schema(
            {
                _opt_key(CONF_WATERMARK_ENTITIES, []): multi_entity,
                _opt_key(CONF_SOIL_TEMP_ENTITIES, []): multi_entity,
                _opt_key(CONF_FLOW_TOTAL_ENTITY, None): single_entity,
                _opt_key(CONF_FLOW_DAILY_ENTITY, None): single_entity,
                _opt_key(CONF_WEATHER_ENTITY, None): _WEATHER_SELECTOR,
            }
        )
        return self.async_show_form(step_id="advanced", data_schema=schema)
