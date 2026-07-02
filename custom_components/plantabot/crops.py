"""Coeficientes de cultivo Kc por ETAPA FENOLÓGICA (modelo FAO-56 simplificado).

En vez de una curva por mes, el Kc se toma de la etapa fenológica efectiva del árbol
(que el coordinator ya calcula cruzando calendario y ciclo de vida). Esto sigue el
patrón FAO de fases: inicial (bajo) -> desarrollo/media (máximo) -> final (decae).

Los valores son ESTIMACIONES DE PARTIDA (frutal en suelo, clima mediterráneo
continental) y están para calibrarse comparando la recomendación por ETo con el
Watermark. La curva mensual anterior se mantiene como respaldo (get_kc_by_month).
"""
from __future__ import annotations

from .const import CROP_CEREZO, CROP_NISPERO

# Kc por etapa fenológica. Claves = estados de FENO_STAGES (+ 'vegetativo').
KC_BY_STAGE: dict[str, dict[str, float]] = {
    CROP_CEREZO: {
        "reposo": 0.15, "brotacion": 0.30, "floracion": 0.45, "cuajado": 0.55,
        "engorde": 0.60, "maduracion": 0.50, "cosecha": 0.45, "postcosecha": 0.40,
        "vegetativo": 0.40,
    },
    CROP_NISPERO: {
        "reposo": 0.55, "brotacion": 0.60, "floracion": 0.65, "cuajado": 0.65,
        "engorde": 0.70, "maduracion": 0.65, "cosecha": 0.60, "postcosecha": 0.55,
        "vegetativo": 0.60,
    },
}

# Kc neutro por defecto si no hay curva de cultivo ni etapa conocida.
KC_DEFAULT = 0.5

# --- Respaldo: curva mensual (modelo anterior) -------------------------------
KC_CEREZO_MONTH: dict[int, float] = {
    1: 0.15, 2: 0.15, 3: 0.30, 4: 0.45, 5: 0.55, 6: 0.55,
    7: 0.55, 8: 0.50, 9: 0.40, 10: 0.30, 11: 0.20, 12: 0.15,
}
KC_NISPERO_MONTH: dict[int, float] = {
    1: 0.60, 2: 0.60, 3: 0.65, 4: 0.65, 5: 0.60, 6: 0.60,
    7: 0.65, 8: 0.65, 9: 0.60, 10: 0.55, 11: 0.55, 12: 0.55,
}
KC_CURVES_MONTH: dict[str, dict[int, float]] = {
    CROP_CEREZO: KC_CEREZO_MONTH,
    CROP_NISPERO: KC_NISPERO_MONTH,
}


def get_kc_by_stage(crop: str, stage: str | None) -> float | None:
    """Kc de la etapa fenológica. None si no hay curva/etapa (para hacer fallback)."""
    table = KC_BY_STAGE.get(crop)
    if table is None or stage is None:
        return None
    return table.get(stage)


def get_kc_by_month(crop: str, month: int) -> float:
    """Kc de respaldo por mes (modelo anterior)."""
    curve = KC_CURVES_MONTH.get(crop)
    if curve is None:
        return KC_DEFAULT
    return curve.get(month, KC_DEFAULT)


def get_kc(
    crop: str,
    month: int,
    override: float | None = None,
    stage: str | None = None,
) -> float:
    """Kc base a usar (SIN factor de cobertura).

    Prioridad: override manual > Kc por etapa fenológica > Kc por mes > neutro.
    """
    if override is not None:
        return override
    by_stage = get_kc_by_stage(crop, stage)
    if by_stage is not None:
        return by_stage
    return get_kc_by_month(crop, month)
