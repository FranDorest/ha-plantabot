"""Cálculo de la lámina de riego con corrección por cobertura (FAO-56 simplificado).

Idea:
  ETc = ETo * Kc_efectivo
  Kc_efectivo = Kc_fenologia * Kr
  Kr = factor de cobertura (árbol joven intercepta menos radiación que un adulto)

Kr se estima de la fracción de suelo sombreada por la copa:
  sombreo = área_copa / área_asignada
  Kr = min(1, sombreo / CANOPY_FULL_SHADING)

Para herbáceas/pradera de cobertura total (césped, maíz establecido) NO se aplica Kr
(cobertura ~ plena): en esos casos el llamador pasa canopy_auto=False -> Kr=1.
"""
from __future__ import annotations

import math

from .const import CANOPY_FULL_SHADING


def canopy_shading_fraction(copa_m: float | None, area_m2: float | None) -> float | None:
    """Fracción de suelo sombreada por la copa (0-1). None si faltan datos."""
    if not copa_m or not area_m2 or area_m2 <= 0:
        return None
    canopy_area = math.pi * (copa_m / 2.0) ** 2
    return min(1.0, canopy_area / area_m2)


def coverage_factor(
    copa_m: float | None,
    area_m2: float | None,
    canopy_auto: bool,
) -> tuple[float, float | None]:
    """Devuelve (Kr, fracción_sombreo).

    - canopy_auto=False -> Kr=1 (cobertura plena asumida; herbáceas, o usuario que
      no quiere la corrección).
    - canopy_auto=True pero sin copa/área -> Kr=1 y sombreo None (no penaliza si no
      hay dato, para no dejar el riego a cero por falta de información).
    """
    if not canopy_auto:
        return 1.0, None
    shading = canopy_shading_fraction(copa_m, area_m2)
    if shading is None:
        return 1.0, None
    kr = min(1.0, shading / CANOPY_FULL_SHADING)
    return kr, shading


def litros_objetivo(
    etc_mm: float | None,
    rain_eff_mm: float | None,
    area_m2: float,
    efficiency_frac: float,
    min_irrigation_l: float = 0.0,
) -> float | None:
    """Litros a aportar = max(ETc - lluvia efectiva, 0) * área / eficiencia.

    1 mm sobre 1 m² = 1 litro. Se aplica un suelo mínimo opcional (establecimiento).
    """
    if etc_mm is None or efficiency_frac <= 0:
        return None
    deficit_mm = max(etc_mm - (rain_eff_mm or 0.0), 0.0)
    litros = deficit_mm * area_m2 / efficiency_frac
    if min_irrigation_l and litros < min_irrigation_l:
        litros = min_irrigation_l
    return round(litros, 1)


def acumular_deficit(
    deficit_prev_l: float,
    necesidad_dia_l: float | None,
    litros_aportados_l: float | None,
    cap_l: float,
) -> float:
    """Balance del acumulador de déficit (riego por pulsos).

    deficit = deficit_anterior + necesidad_del_día - litros_aportados,
    acotado entre 0 y el techo (capacidad útil del bulbo: acumular más solo
    percolaría bajo raíces al reponerlo de golpe).
    """
    d = deficit_prev_l + (necesidad_dia_l or 0.0) - (litros_aportados_l or 0.0)
    d = max(0.0, d)
    if cap_l > 0:
        d = min(d, cap_l)
    return round(d, 1)


def lluvia_esperada(
    forecast: list[dict] | None, days: int = 2
) -> tuple[float | None, float | None]:
    """(mm esperados, probabilidad máx %) de los próximos `days` días de previsión.

    mm esperados = suma de precipitation * probability/100 (valor esperado). Si una
    entrada no trae probabilidad, se asume 100% (conservador: pospone antes).
    Devuelve (None, None) si no hay previsión utilizable.
    """
    if not forecast:
        return None, None
    mm = 0.0
    prob_max: float | None = None
    for item in forecast[:days]:
        if not isinstance(item, dict):
            continue
        precip = item.get("precipitation")
        prob = item.get("precipitation_probability")
        try:
            precip_f = float(precip) if precip is not None else 0.0
        except (TypeError, ValueError):
            precip_f = 0.0
        try:
            prob_f = float(prob) if prob is not None else 100.0
        except (TypeError, ValueError):
            prob_f = 100.0
        mm += precip_f * (prob_f / 100.0)
        if precip_f > 0:
            prob_max = prob_f if prob_max is None else max(prob_max, prob_f)
    return round(mm, 1), prob_max
