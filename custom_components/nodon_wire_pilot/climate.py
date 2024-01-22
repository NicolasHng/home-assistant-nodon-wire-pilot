"""Platform for Nodon Wire Pilot."""
import logging

import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_START,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Nodon Thermostat"

CONF_HEATER = "heater"
CONF_SENSOR = "sensor"
CONF_ADDITIONAL_MODES = "additional_modes"

PRESET_COMFORT_1 = "Comfort -1"
PRESET_COMFORT_2 = "Comfort -2"

VALUE_OFF = "off"
VALUE_FROST = "frost_protection"
VALUE_ECO = "eco"
VALUE_COMFORT_2 = "comfort_-2"
VALUE_COMFORT_1 = "comfort_-1"
VALUE_COMFORT = "comfort"

ATTR_MODE = "pilot_wire_mode"
SELECT_OPTION = "option"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HEATER): cv.entity_ids,
        vol.Optional(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_ADDITIONAL_MODES, default=False): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the wire pilot climate platform."""
    unique_id = config.get(CONF_UNIQUE_ID)
    name = config.get(CONF_NAME)
    heater_entity_ids = config.get(CONF_HEATER)
    sensor_entity_id = config.get(CONF_SENSOR)
    additional_modes = config.get(CONF_ADDITIONAL_MODES)

    async_add_entities(
        [
            NodonPilotClimate(
                unique_id, name, heater_entity_ids, sensor_entity_id, additional_modes
            )
        ]
    )


class NodonPilotClimate(ClimateEntity, RestoreEntity):
    """Representation of a Nodon Wire Pilot device."""

    def __init__(
        self, unique_id, name, heater_entity_ids, sensor_entity_id, additional_modes
    ) -> None:
        """Initialize the climate device."""
        if isinstance(heater_entity_ids, str):
            self.heater_entity_ids = [ent_id.strip() for ent_id in heater_entity_ids.split(",")]
        else:
            self.heater_entity_ids = heater_entity_ids
        self.sensor_entity_id = sensor_entity_id
        self.additional_modes = additional_modes
        self._cur_modes = None
        self._cur_temperature = None

        self._attr_unique_id = (
            unique_id if unique_id else "nodon_wire_pilot_" + heater_entity_ids[0]
        )
        self._attr_name = name

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Add listener
        for heater_entity_id in self.heater_entity_ids[::-1]:
            async_track_state_change(
                self.hass, heater_entity_id, self._async_heater_changed
            )
        if self.sensor_entity_id is not None and False:  # To uncomment
            async_track_state_change(
                self.hass, self.sensor_entity_id, self._async_temperature_changed
            )

        @callback
        def _async_startup(event):
            """Init on startup."""
            if self.sensor_entity_id is not None:
                sensor_state = self.hass.states.get(self.sensor_entity_id)
                if sensor_state:
                    self._async_update_temperature(sensor_state)

            self.async_schedule_update_ha_state()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        return ClimateEntityFeature.PRESET_MODE

    def update(self) -> None:
        """Update unit attributes."""

    # Temperature
    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the sensor temperature."""
        return self._cur_temperature

    @property
    def heater_value(self) -> int | None:
        """Return entity mode."""
        if len(self.heater_entity_ids) == 1:
            state = self.hass.states.get(self.heater_entity_ids[0])

            if state is None:
                return

            return state.attributes.get(ATTR_MODE)
        return self._cur_modes

    # Presets
    @property
    def preset_modes(self) -> list[str] | None:
        """List of available preset modes."""
        if self.additional_modes:
            return [
                PRESET_COMFORT,
                PRESET_COMFORT_1,
                PRESET_COMFORT_2,
                PRESET_ECO,
                PRESET_AWAY,
                PRESET_NONE,
            ]
        else:
            return [PRESET_COMFORT, PRESET_ECO, PRESET_AWAY, PRESET_NONE]

    @property
    def preset_mode(self) -> str | None:
        """Preset current mode."""
        value = self.heater_value

        if value is None:
            return None
        if value == VALUE_OFF:
            return PRESET_NONE
        elif value == VALUE_FROST:
            return PRESET_AWAY
        elif value == VALUE_ECO:
            return PRESET_ECO
        elif value == VALUE_COMFORT_2 and self.additional_modes:
            return PRESET_COMFORT_2
        elif value == VALUE_COMFORT_1 and self.additional_modes:
            return PRESET_COMFORT_1
        else:
            return PRESET_COMFORT

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        value = VALUE_OFF

        if preset_mode == PRESET_AWAY:
            value = VALUE_FROST
        elif preset_mode == PRESET_ECO:
            value = VALUE_ECO
        elif preset_mode == PRESET_COMFORT_2 and self.additional_modes:
            value = VALUE_COMFORT_2
        elif preset_mode == PRESET_COMFORT_1 and self.additional_modes:
            value = VALUE_COMFORT_1
        elif preset_mode == PRESET_COMFORT:
            value = VALUE_COMFORT

        await self._async_set_heater_value(value)

    # Modes
    @property
    def hvac_modes(self) -> list[HVACMode]:
        """List of available operation modes."""
        return [HVACMode.HEAT, HVACMode.OFF]

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        value = VALUE_FROST

        if hvac_mode == HVACMode.HEAT:
            value = VALUE_COMFORT
        elif hvac_mode == HVACMode.OFF:
            value = VALUE_OFF

        await self._async_set_heater_value(value)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, off mode."""
        value = self.heater_value

        if value is None:
            return None
        if value == VALUE_OFF:
            return HVACMode.OFF
        else:
            return HVACMode.HEAT

    @callback
    async def _async_heater_changed(self, entity_id, old_state, new_state) -> None:
        if new_state is None:
            return
        self._cur_modes = new_state.state
        await self._async_set_heater_value(new_state.state)
        self.async_schedule_update_ha_state()

    async def _async_temperature_changed(self, entity_id, old_state, new_state) -> None:
        if new_state is None:
            return
        self._async_update_temperature(new_state)
        self.async_write_ha_state()

    @callback
    def _async_update_temperature(self, state):
        try:
            if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                self._cur_temperature = float(state.state)
            else:
                self._cur_temperature = None
        except ValueError as ex:
            _LOGGER.error("Unable to update from temperature sensor: %s", ex)

    async def _async_set_heater_value(self, value):
        """Turn heater toggleable device on."""
        for heater_entity_id in self.heater_entity_ids:
            data = {
                ATTR_ENTITY_ID: heater_entity_id,
                SELECT_OPTION: value,
            }

            await self.hass.services.async_call(SELECT_DOMAIN, SERVICE_SELECT_OPTION, data)
