# PlantaBot para Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

Integración de Home Assistant para **riego de precisión por árbol frutal**. Cada árbol
(o punto de riego) es un *device* configurable por interfaz gráfica que cruza la **ETo**
de la integración [SiAR](https://github.com/FranDorest/ha-siar) con la telemetría de un
**nodo LoRaWAN** (caudalímetro, Watermark, DS18B20) para decidir cuánto regar y si es
buen momento para abonar.

Pensada para escalar a 20–100 árboles: dar de alta uno nuevo es rellenar un formulario,
no copiar YAML.

## Qué expone (por árbol)

| Sensor | Descripción |
|---|---|
| `Kc actual` | Coeficiente de cultivo del mes (curva por cultivo o valor fijo). |
| `ETc` | ETo × Kc — la "sed" real del árbol (mm). |
| `Litros a regar hoy` | `max(ETc − precip. efectiva, 0) × área / eficiencia`. |
| `Recomendación de riego` | `regar` / `no_regar` / `regar_sin_dato_suelo`, cruzando el cálculo con el Watermark. |
| `Tensión de suelo` | Media de los Watermark disponibles (kPa). |
| `Temperatura de suelo` | Media de los DS18B20 disponibles (°C). |
| `Recomendación de abonado` | `buen_momento` / `demasiado_frio` / `demasiado_calor` / `sin_dato`, según la temperatura de suelo. |
| `Balance hídrico` | Litros medidos hoy − objetivo (si hay contador diario). |

## Diseño

- **Sin polling ni API propia.** PlantaBot deriva de otras entidades de HA y se
  recalcula cuando cambian (la ETo de SiAR o la telemetría del nodo).
- **Nodo por *device*.** Se elige el device del nodo LoRaWAN y la integración resuelve
  por dentro sus entidades (litros, Watermark, DS18B20) por patrón de nombre/unidad.
- **Sensores múltiples y tolerancia a ausencia.** Admite **hasta 3 Watermark** y
  **hasta 3 DS18B20**. Si falta alguno, no falla:
  - Sin Watermark → recomienda por ETo y avisa (`regar_sin_dato_suelo`).
  - Sin DS18B20 → la recomendación de abonado queda en `sin_dato`.
- **Escape manual.** Si la auto-detección no acierta, en *Opciones → avanzado* puedes
  fijar a mano las entidades de Watermark, DS18B20 y caudalímetro.

## Instalación (HACS, repositorio personalizado)

1. HACS → Integraciones → menú ⋮ → *Repositorios personalizados*.
2. URL de este repo, categoría **Integration**.
3. Instala **PlantaBot** y reinicia Home Assistant.
4. *Ajustes → Dispositivos y servicios → Añadir integración → PlantaBot*.

## Configuración de un árbol

**Paso 1 — fuentes:** nombre, nodo LoRaWAN (device), ETo (EtPMon de SiAR), precip.
efectiva (PePMon, opcional) y tipo de cultivo (cerezo / níspero / otro).

**Paso 2 — parámetros:** Kc fijo opcional, área (m²), eficiencia (%), umbral de suelo
seco (kPa) y ventana de temperatura de suelo para abonar (°C).

Los parámetros se editan luego en *Opciones* sin reconfigurar el árbol.

## Calibración

El Kc de partida y los umbrales son **estimaciones**. La idea es afinarlos comparando la
recomendación por ETo con lo que marca el Watermark, y ajustar el Kc real de cada árbol
con el tiempo.

## Estado

`0.1.0` — esqueleto funcional. Pendiente: hardware del Watermark/DS18B20 en el nodo,
balance hídrico con `utility_meter` diario, y pulido de traducciones EN.
