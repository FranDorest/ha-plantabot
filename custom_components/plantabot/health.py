"""Índices de salud del árbol y progreso de cosecha.

Son HEURÍSTICOS y calibrables (como el Kc): cada sub-score va de 0 a 1, la salud es
la media de los sub-scores DISPONIBLES (los que no tienen dato no penalizan), y la
cosecha se mapea desde el estado fenológico. Se exponen los sub-scores como atributos
para que se vea de dónde sale cada número y poder afinarlos.
"""
from __future__ import annotations

from .const import HARVEST_MAP


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _band(x: float, lo_ok: float, hi_ok: float, lo_zero: float, hi_zero: float) -> float:
    """1.0 dentro de [lo_ok, hi_ok]; cae linealmente a 0 en lo_zero/hi_zero."""
    if lo_ok <= x <= hi_ok:
        return 1.0
    if x < lo_ok:
        return _clamp((x - lo_zero) / (lo_ok - lo_zero)) if lo_ok > lo_zero else 0.0
    return _clamp((hi_zero - x) / (hi_zero - hi_ok)) if hi_zero > hi_ok else 0.0


def water_score(wm_kpa: float | None, dry_threshold: float) -> float | None:
    """Estado hídrico por tensión de suelo. Óptimo entre ~10 kPa y el umbral seco."""
    if wm_kpa is None:
        return None
    # saturado (<10) penaliza suave; por encima del umbral, seco; a 2x umbral ~0
    return _band(wm_kpa, 10.0, dry_threshold, -5.0, 2.0 * dry_threshold)


def soiltemp_score(t_c: float | None) -> float | None:
    """Temperatura de suelo favorable a la actividad radicular."""
    if t_c is None:
        return None
    return _band(t_c, 12.0, 28.0, 2.0, 40.0)


def battery_score(pct: float | None) -> float | None:
    """Batería: 1.0 por encima del 40%, lineal por debajo."""
    if pct is None:
        return None
    return _clamp(pct / 40.0)


def online_score(age_s: float | None, max_age_s: float) -> float | None:
    """Nodo online si su última lectura es reciente."""
    if age_s is None:
        return None
    return 1.0 if age_s <= max_age_s else _clamp(1.0 - (age_s - max_age_s) / max_age_s)


def nutrient_score(ph: float | None, ce: float | None) -> float | None:
    """Química del suelo: pH en banda y conductividad (salinidad) baja.

    Relevante con agua dura/calcárea: CE alta y pH alto restan.
    """
    scores: list[float] = []
    if ph is not None:
        scores.append(_band(ph, 6.0, 7.5, 4.5, 9.0))
    if ce is not None:
        # <2 dS/m ideal; a 4 dS/m ~0.3; por encima muy salino
        scores.append(_clamp(1.0 - (ce - 2.0) / 2.0 * 0.7) if ce > 2.0 else 1.0)
    if not scores:
        return None
    return sum(scores) / len(scores)


def tree_health(
    wm_kpa: float | None,
    soil_t: float | None,
    battery_pct: float | None,
    node_age_s: float | None,
    ph: float | None,
    ce: float | None,
    dry_threshold: float,
    max_age_s: float,
) -> tuple[float | None, dict[str, float]]:
    """Salud global 0-100 = media de los sub-scores disponibles. Devuelve (pct, detalle)."""
    subs = {
        "hidrico": water_score(wm_kpa, dry_threshold),
        "temp_suelo": soiltemp_score(soil_t),
        "bateria": battery_score(battery_pct),
        "online": online_score(node_age_s, max_age_s),
        "nutrientes": nutrient_score(ph, ce),
    }
    available = {k: round(v, 2) for k, v in subs.items() if v is not None}
    if not available:
        return None, {}
    pct = round(100.0 * sum(available.values()) / len(available), 0)
    return pct, available


def harvest_progress(fenologia: str | None) -> float | None:
    """Progreso hacia la cosecha (0-100) según el estado fenológico."""
    if fenologia is None:
        return None
    return float(HARVEST_MAP.get(fenologia, 0))