"""Editable receipt, QR, and barcode drafts. Use actions for long payloads."""

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import QR701Entity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            QR701Text(entry.runtime_data, entry, key, name)
            for key, name in (
                ("print_text", "Print text"),
                ("qr_data", "QR data"),
                ("barcode_data", "Barcode data"),
            )
        ]
    )


class QR701Text(QR701Entity, TextEntity, RestoreEntity):
    _attr_native_max = 255
    _attr_mode = TextMode.TEXT
    _attr_icon = "mdi:text-box-edit-outline"

    def __init__(self, coordinator, entry, key, name):
        super().__init__(coordinator, entry, key, name)
        self.key = key

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) and state.state not in (
            "unknown",
            "unavailable",
        ):
            self.coordinator.drafts[self.key] = state.state

    @property
    def native_value(self):
        return self.coordinator.drafts[self.key]

    async def async_set_value(self, value):
        self.coordinator.drafts[self.key] = value
        self.async_write_ha_state()
