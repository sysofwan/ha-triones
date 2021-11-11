import logging
import voluptuous as vol
from typing import Any, Optional, Tuple

from .triones import TrionesInstance
from .const import DOMAIN

from homeassistant.const import CONF_MAC
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.light import (COLOR_MODE_RGB, PLATFORM_SCHEMA,
                                            LightEntity, ATTR_RGB_COLOR, ATTR_BRIGHTNESS, COLOR_MODE_WHITE, ATTR_WHITE)
from homeassistant.util.color import (_match_max_scale)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC): cv.string
})

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add sensors for passed config_entry in HA."""
    instance = TrionesInstance(config_entry.data[CONF_MAC])
    async_add_devices([TrionesLight(instance, config_entry.data["name"])])

# def setup_platform(
#     hass: HomeAssistant,
#     config: ConfigType,
#     add_entities: AddEntitiesCallback,
#     discovery_info: DiscoveryInfoType
# ) -> None:
#     # Assign configuration variables.
#     # The configuration check takes care they are present.
#     mac = config[CONF_MAC]

#     instance = TrionesInstance(mac)

#     add_entities([TrionesLight(instance, mac)])

class TrionesLight(LightEntity):
    """Representation of an Awesome Light."""

    def __init__(self, trionesInstance: TrionesInstance, name: str) -> None:
        """Initialize an AwesomeLight."""
        self._instance = trionesInstance
        self._state = None
        self._brightness = None
        self._attr_supported_color_modes = {COLOR_MODE_RGB, COLOR_MODE_WHITE}
        self._color_mode = None
        self._attr_name = name
        self._attr_unique_id = self._instance.mac

    @property
    def available(self):
        return self._instance.is_on != None

    @property
    def brightness(self):
        if self._instance.white_brightness:
            return self._instance.white_brightness
        
        if self._instance._rgb_color:
            return max(self._instance.rgb_color)
        
        return None

    @property
    def is_on(self) -> Optional[bool]:
        """Return true if light is on."""
        return self._instance.is_on

    @property
    # TODO: https://github.com/home-assistant/core/issues/51175
    def rgb_color(self):
        if self._instance.rgb_color:
            return _match_max_scale((255,), self._instance.rgb_color)
        return None

    @property
    def color_mode(self):
        if self._instance.rgb_color:
            if self._instance.rgb_color == (0, 0, 0):
                return COLOR_MODE_WHITE
            return COLOR_MODE_RGB
        return None

    def _transform_color_brightness(self, color: Tuple[int, int, int], set_brightness: int):
        rgb = _match_max_scale((255,), color)
        res = tuple(color * set_brightness // 255 for color in rgb)
        return res

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on.
        You can skip the brightness part if your light does not support
        brightness control.
        """
        if not self.is_on:
            await self._instance.turn_on()

        if ATTR_WHITE in kwargs:
            if kwargs[ATTR_WHITE] != self.brightness:
                await self._instance.set_white(kwargs[ATTR_WHITE])

        elif ATTR_RGB_COLOR in kwargs:
            if kwargs[ATTR_RGB_COLOR] != self.rgb_color:
                color = kwargs[ATTR_RGB_COLOR]
                if ATTR_BRIGHTNESS in kwargs:
                    color = self._transform_color_brightness(color, kwargs[ATTR_BRIGHTNESS])
                else:
                    color = self._transform_color_brightness(color, self.brightness)
                await self._instance.set_color(color)
        
        elif ATTR_BRIGHTNESS in kwargs and kwargs[ATTR_BRIGHTNESS] != self.brightness and self.rgb_color != None:
            await self._instance.set_color(self._transform_color_brightness(self.rgb_color, kwargs[ATTR_BRIGHTNESS]))


    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._instance.turn_off()

    async def async_update(self) -> None:
        await self._instance.update()
