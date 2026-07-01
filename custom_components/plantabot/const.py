"""Constantes de PlantaBot."""
from __future__ import annotations

DOMAIN = "plantabot"

# --- Claves de configuración (config_entry.data / .options) ---
CONF_NAME = "name"
CONF_NODE_DEVICE = "node_device_id"      # DeviceSelector -> device_id del nodo LoRaWAN (rakXXXX)
CONF_ETO_ENTITY = "eto_entity"           # EntitySelector -> EtPMon (ETo) de SiAR
CONF_RAIN_ENTITY = "rain_entity"         # EntitySelector -> PePMon (precip. efectiva) de SiAR
CONF_CROP = "crop"                       # cerezo | nispero | custom

# Parámetros ajustables (van en options para poder editarlos sin reconfigurar)
CONF_KC_OVERRIDE = "kc_override"         # None -> usar curva del cultivo
CONF_AREA = "area_m2"
CONF_EFFICIENCY = "efficiency_pct"
CONF_DRY_THRESHOLD = "dry_threshold_kpa"
CONF_FERT_MIN = "fert_min_temp_c"
CONF_FERT_MAX = "fert_max_temp_c"

# Overrides manuales de entidades del nodo (para el flujo avanzado / cuando la
# auto-resolución no acierta). Todas opcionales.
CONF_FLOW_TOTAL_ENTITY = "flow_total_entity"   # litros acumulados (caudalímetro)
CONF_FLOW_DAILY_ENTITY = "flow_daily_entity"   # litros del día (si existe utility_meter)
CONF_WATERMARK_ENTITIES = "watermark_entities"  # lista, hasta MAX_WATERMARK
CONF_SOIL_TEMP_ENTITIES = "soil_temp_entities"  # lista, hasta MAX_SOIL_TEMP

# --- Límites de sensores múltiples ---
MAX_WATERMARK = 3
MAX_SOIL_TEMP = 3

# --- Valores por defecto ---
DEFAULT_AREA = 4.0            # m² asignados por árbol
DEFAULT_EFFICIENCY = 90.0     # % eficiencia de riego (goteo alto)
DEFAULT_DRY_THRESHOLD = 40.0  # kPa; por encima => suelo seco => regar
DEFAULT_FERT_MIN = 10.0       # °C; por debajo => demasiado frío para abonar
DEFAULT_FERT_MAX = 30.0       # °C; por encima => demasiado calor / estrés radicular

# --- Cultivos ---
CROP_CEREZO = "cerezo"
CROP_NISPERO = "nispero"
CROP_CUSTOM = "custom"
CROPS = [CROP_CEREZO, CROP_NISPERO, CROP_CUSTOM]

# --- Estados de recomendación de riego ---
REC_IRRIGATE = "regar"
REC_NO_IRRIGATE = "no_regar"
REC_IRRIGATE_NO_SOIL = "regar_sin_dato_suelo"
IRRIGATION_STATES = [REC_IRRIGATE, REC_NO_IRRIGATE, REC_IRRIGATE_NO_SOIL]

# --- Estados de recomendación de abonado ---
FERT_GOOD = "buen_momento"
FERT_COLD = "demasiado_frio"
FERT_HOT = "demasiado_calor"
FERT_NO_DATA = "sin_dato"
FERT_STATES = [FERT_GOOD, FERT_COLD, FERT_HOT, FERT_NO_DATA]

# --- Patrones de auto-resolución de entidades del nodo ---
# Se comparan (en minúsculas) contra el entity_id / nombre de las entidades del device.
WATERMARK_UNITS = ("kpa",)
SOIL_TEMP_HINTS = ("suelo", "soil", "18b20", "ds18", "watermark_temp")
# Se excluyen temperaturas que NO son de suelo:
NON_SOIL_TEMP_HINTS = ("bmp", "cpu", "aire", "air", "gps")
FLOW_TOTAL_HINTS = ("litros", "liters", "volumen", "volume")
FLOW_RATE_HINTS = ("caudal", "lpm", "flow")
