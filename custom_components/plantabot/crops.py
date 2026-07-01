"""Curvas de Kc por cultivo.

Los valores son ESTIMACIONES DE PARTIDA pensadas para árbol joven en suelo, clima
mediterráneo continental (Zaragoza), y están para calibrarse con el tiempo comparando
la recomendación por ETo con lo que marca el Watermark (ver filosofía de calibración
del brief). No son verdades absolutas: son el punto de arranque.

Índice del mes: 1 = enero ... 12 = diciembre.
"""
from __future__ import annotations

from .const import CROP_CEREZO, CROP_NISPERO

# Cerezo (caducifolio): sin hoja en invierno (Kc ~ evaporación de suelo), brotación en
# primavera, pico en verano, senescencia en otoño. Árbol joven -> pico ~0.5.
KC_CEREZO: dict[int, float] = {
    1: 0.15, 2: 0.15, 3: 0.30, 4: 0.45, 5: 0.55, 6: 0.55,
    7: 0.55, 8: 0.50, 9: 0.40, 10: 0.30, 11: 0.20, 12: 0.15,
}

# Níspero (perenne): hoja todo el año, menos variación estacional; floración en otoño
# y cuajado en invierno. Árbol joven -> banda ~0.55-0.65.
KC_NISPERO: dict[int, float] = {
    1: 0.60, 2: 0.60, 3: 0.65, 4: 0.65, 5: 0.60, 6: 0.60,
    7: 0.65, 8: 0.65, 9: 0.60, 10: 0.55, 11: 0.55, 12: 0.55,
}

KC_CURVES: dict[str, dict[int, float]] = {
    CROP_CEREZO: KC_CEREZO,
    CROP_NISPERO: KC_NISPERO,
}


def get_kc(crop: str, month: int, override: float | None = None) -> float:
    """Devuelve el Kc a usar.

    - Si hay `override` (Kc fijo configurado por el usuario), manda ese.
    - Si el cultivo tiene curva, se usa el valor del mes.
    - Si el cultivo es desconocido/custom y no hay override, se usa 0.5 como neutro.
    """
    if override is not None:
        return override
    curve = KC_CURVES.get(crop)
    if curve is None:
        return 0.5
    return curve.get(month, 0.5)
