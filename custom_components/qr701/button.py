"""Print drafts, feed paper, and refresh status."""

from homeassistant.components.button import ButtonEntity

from . import protocol
from .entity import QR701Entity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.runtime_data.capabilities.supports_cut:
        async_add_entities([QR701Button(entry.runtime_data, entry, "cut", "Cut paper")])
    async_add_entities(
        [
            QR701Button(entry.runtime_data, entry, key, name)
            for key, name in (
                ("print", "Print"),
                ("print_markdown", "Print Markdown"),
                ("print_qr", "Print QR"),
                ("print_barcode", "Print barcode"),
                ("feed", "Feed paper"),
                ("refresh_status", "Refresh status"),
            )
        ]
    )


class QR701Button(QR701Entity, ButtonEntity):
    _attr_icon = "mdi:printer-pos"

    def __init__(self, coordinator, entry, key, name):
        super().__init__(coordinator, entry, key, name)
        self.key = key

    async def async_press(self):
        c = self.coordinator
        if self.key == "refresh_status":
            await c.async_request_refresh()
        elif self.key == "cut":
            await c.async_print(protocol.cut, 3)
        elif self.key == "feed":
            await c.async_print(protocol.feed, 3)
        elif self.key == "print_qr":
            await c.async_print(
                protocol.qr_receipt, c.drafts["qr_data"], c.qr_size, c.qr_error_correction
            )
        elif self.key == "print_barcode":
            await c.async_print(protocol.barcode_receipt, c.drafts["barcode_data"])
        else:
            encoder = (
                protocol.markdown_receipt if self.key == "print_markdown" else protocol.text_receipt
            )
            await c.async_print(encoder, c.drafts["print_text"])
