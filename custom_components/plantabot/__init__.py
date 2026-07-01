"""Integración PlantaBot: riego de precisión por árbol para Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import PlantaBotCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.DATE,
]

type PlantaBotConfigEntry = ConfigEntry[PlantaBotCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PlantaBotConfigEntry) -> bool:
    """Configurar un árbol PlantaBot desde su config entry."""
    coordinator = PlantaBotCoordinator(hass, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Recargar si cambian las opciones (parámetros / overrides de entidades)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PlantaBotConfigEntry) -> bool:
    """Descargar el árbol."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: PlantaBotConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
