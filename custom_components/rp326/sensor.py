"""Printer status; sending is local transmission, not mechanical completion."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity

from .const import CONF_STATUS, STATUS_OPTIONS
from .entity import RP326Entity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([RP326Status(entry.runtime_data, entry)])


class RP326Status(RP326Entity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUS_OPTIONS
    _attr_icon = "mdi:printer-pos"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "status", "Status")
        self._attr_extra_state_attributes = {"status_enabled": entry.data[CONF_STATUS]}

    @property
    def native_value(self):
        if self.coordinator.sending:
            return "sending"
        return self.coordinator.data.state if self.coordinator.data is not None else "unknown"
