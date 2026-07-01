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
# IMPORTANTE: las entidades de TTN llegan como TEXTO, sin unit_of_measurement ni
# device_class. Por eso NO se puede resolver por unidad: se resuelve por NOMBRE
# (object_id / friendly name), comparado en minúsculas.
#
# Nombres reales del nodo RAK:
#   Watermark  -> wm1_kpa, wm2_kpa, wm3_kpa
#   DS18B20    -> ds1_temp_c, ds2_temp_c, ds3_temp_c   (NO bmp_temp_c / cpu_temp_c)
#   Caudalím.  -> litros (acumulado)   [puede no venir en todos los uplinks]
WATERMARK_MATCH = "kpa"                 # 'kpa' aparece en wmN_kpa y NO en bmp_pres_hpa
SOIL_TEMP_REGEX = r"ds\d+.*temp"        # dsN_temp_c; excluye bmp_temp_c / cpu_temp_c
FLOW_TOTAL_MATCH = ("litros", "liters", "volumen")
FLOW_RATE_MATCH = ("caudal", "lpm")

# Catálogo de campos del nodo que PlantaBot refleja como entidades tipadas.
# Se emparejan por substring del object_id (rakXXXX_<campo>). Claves = nombres del payload.
WM_FIELDS = ("wm1_kpa", "wm2_kpa", "wm3_kpa")
DS_FIELDS = ("ds1_temp_c", "ds2_temp_c", "ds3_temp_c")
AMBIENT_FIELDS = ("bmp_temp_c", "bmp_pres_hpa")
DIAG_FIELDS = (
    "bateria_pct", "bateria_v", "bateria_mv",
    "cpu_temp_c", "ciclo_ms", "uptime_s",
    "latitude", "longitude",
)
FLOW_FIELD = ("litros",)
# Todos los campos a resolver desde el device del nodo:
NODE_FIELD_KEYS = (*WM_FIELDS, *DS_FIELDS, *AMBIENT_FIELDS, *DIAG_FIELDS, *FLOW_FIELD)

# --- Metadatos editables del árbol (entidades number/select/date, persistidos) ---
META_ALTURA = "altura_m"
META_COPA = "copa_m"
META_ANIO = "anio_plantacion"
META_PH = "ph"
META_CE = "ce"
META_N = "n"
META_P = "p"
META_K = "k"
META_CICLO = "ciclo_vida"
META_FENOLOGIA = "fenologia"
META_FECHA_CUAJADO = "fecha_cuajado"

# Opciones de los desplegables
CICLO_OPTIONS = ["planton", "formacion", "produccion", "adulto", "senescente"]
FENO_OPTIONS = [
    "reposo", "brotacion", "floracion", "cuajado",
    "engorde", "maduracion", "cosecha", "postcosecha",
]

# Valores por defecto de los metadatos
META_DEFAULTS: dict[str, object] = {
    META_ALTURA: 1.5,
    META_COPA: 1.0,
    META_ANIO: 2024,
    META_PH: 7.5,
    META_CE: 1.0,
    META_N: 0.0,
    META_P: 0.0,
    META_K: 0.0,
    META_CICLO: "formacion",
    META_FENOLOGIA: "reposo",
    META_FECHA_CUAJADO: None,
}

# Progreso de cosecha (0-100) por estado fenológico
HARVEST_MAP: dict[str, int] = {
    "reposo": 0, "brotacion": 5, "floracion": 15, "cuajado": 30,
    "engorde": 55, "maduracion": 85, "cosecha": 100, "postcosecha": 0,
}

# Persistencia y "online"
STORE_VERSION = 1
NODE_ONLINE_MAX_AGE_S = 6 * 3600  # nodo online si reportó en las últimas 6 h
