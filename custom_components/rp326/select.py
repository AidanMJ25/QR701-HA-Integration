"""QR error-correction control."""

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import RP326Entity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([RP326Correction(entry.runtime_data, entry)])


class RP326Correction(RP326Entity, SelectEntity, RestoreEntity):
    _attr_options = ["L", "M", "Q", "H"]
    _attr_icon = "mdi:qrcode"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "qr_error_correction", "QR error correction")

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) and state.state in self.options:
            self.coordinator.qr_error_correction = state.state

    @property
    def current_option(self):
        return self.coordinator.qr_error_correction

    async def async_select_option(self, option):
        self.coordinator.qr_error_correction = option
        self.async_write_ha_state()
