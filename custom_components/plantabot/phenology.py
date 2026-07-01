"""Cálculo automático de etapa de ciclo de vida y estado fenológico.

Ambos son ESTIMACIONES calibrables:
  - Ciclo de vida: función de la EDAD (año actual - año de plantación), con umbrales
    por cultivo. Bastante fiable.
  - Fenología: modelo por CALENDARIO y cultivo (mes -> estado). Aproximado y variable
    año a año; afinar en el futuro con grados-día del sensor de temperatura ambiente.
"""
from __future__ import annotations

from .const import CROP_CEREZO, CROP_NISPERO

# --- Ciclo de vida por edad (años). Cada tupla: (edad_máxima_exclusiva, etapa) ---
LIFECYCLE_THRESHOLDS: dict[str, list[tuple[float, str]]] = {
    CROP_CEREZO: [
        (1, "planton"), (4, "formacion"), (8, "produccion"), (30, "adulto"),
        (float("inf"), "senescente"),
    ],
    CROP_NISPERO: [
        (1, "planton"), (3, "formacion"), (7, "produccion"), (40, "adulto"),
        (float("inf"), "senescente"),
    ],
}
_LIFECYCLE_DEFAULT = LIFECYCLE_THRESHOLDS[CROP_CEREZO]

# --- Fenología por mes (1-12) y cultivo ---
# Cerezo (caducifolio): flor ~marzo-abril, cosecha ~junio.
PHENO_CEREZO = {
    1: "reposo", 2: "reposo", 3: "floracion", 4: "cuajado", 5: "engorde",
    6: "maduracion", 7: "cosecha", 8: "postcosecha", 9: "postcosecha",
    10: "postcosecha", 11: "reposo", 12: "reposo",
}
# Níspero (perenne): flor otoño, cuaja invierno, cosecha ~abril-mayo, reposo estival.
PHENO_NISPERO = {
    1: "engorde", 2: "engorde", 3: "maduracion", 4: "cosecha", 5: "cosecha",
    6: "postcosecha", 7: "reposo", 8: "reposo", 9: "brotacion",
    10: "floracion", 11: "cuajado", 12: "engorde",
}
PHENO_CURVES = {CROP_CEREZO: PHENO_CEREZO, CROP_NISPERO: PHENO_NISPERO}

# Etapas de ciclo de vida en las que el árbol SÍ da fruto.
PRODUCTIVE_STAGES = {"produccion", "adulto", "senescente"}
VEGETATIVE = "vegetativo"


def is_productive(ciclo: str | None) -> bool:
    """True si el árbol está en una etapa productiva (da fruto)."""
    return ciclo in PRODUCTIVE_STAGES


def effective_phenology(crop: str, month: int, ciclo: str | None) -> str | None:
    """Fenología efectiva teniendo en cuenta el ciclo de vida.

    Un árbol joven/no productivo (plantón o formación) no fructifica: no aplican las
    etapas de fruto (floración, cuajado, engorde, maduración, cosecha). Solo tiene
    sentido 'reposo' en invierno y 'vegetativo' (crecimiento) el resto del año.
    """
    stage = phenology_from_month(crop, month)
    if stage is None:
        return None
    if not is_productive(ciclo):
        return stage if stage == "reposo" else VEGETATIVE
    return stage


def lifecycle_from_age(crop: str, age_years: float | None) -> str | None:
    """Etapa de ciclo de vida a partir de la edad. None si no hay edad."""
    if age_years is None or age_years < 0:
        return None
    for max_age, stage in LIFECYCLE_THRESHOLDS.get(crop, _LIFECYCLE_DEFAULT):
        if age_years < max_age:
            return stage
    return "senescente"


def phenology_from_month(crop: str, month: int) -> str | None:
    """Estado fenológico estimado por mes y cultivo. None si el cultivo no tiene curva."""
    curve = PHENO_CURVES.get(crop)
    if curve is None:
        return None
    return curve.get(month)
