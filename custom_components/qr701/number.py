"""QR module-size control."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import QR701Entity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([QR701Size(entry.runtime_data, entry)])


class QR701Size(QR701Entity, NumberEntity, RestoreEntity):
    _attr_native_min_value = 1
    _attr_native_max_value = 16
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:qrcode"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "qr_size", "QR size")

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if state := await self.async_get_last_state():
            try:
                self.coordinator.qr_size = max(1, min(16, int(float(state.state))))
            except ValueError, OverflowError:
                pass

    @property
    def native_value(self):
        return self.coordinator.qr_size

    async def async_set_native_value(self, value):
        self.coordinator.qr_size = int(value)
        self.async_write_ha_state()
