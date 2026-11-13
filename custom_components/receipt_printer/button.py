"""Print drafts, feed paper, and refresh status."""

from homeassistant.components.button import ButtonEntity

from .entity import ReceiptPrinterEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.runtime_data.capabilities.supports_cut:
        async_add_entities([ReceiptPrinterButton(entry.runtime_data, entry, "cut", "Cut paper")])
    async_add_entities(
        [
            ReceiptPrinterButton(entry.runtime_data, entry, key, name)
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


class ReceiptPrinterButton(ReceiptPrinterEntity, ButtonEntity):
    _attr_icon = "mdi:printer-pos"

    def __init__(self, coordinator, entry, key, name):
        super().__init__(coordinator, entry, key, name)
        self.key = key

    async def async_press(self):
        c = self.coordinator
        if self.key == "refresh_status":
            await c.async_request_refresh()
        elif self.key == "cut":
            await c.async_print("cut", 3)
        elif self.key == "feed":
            await c.async_print("feed", 3)
        elif self.key == "print_qr":
            await c.async_print("print_qr", c.drafts["qr_data"], c.qr_size, c.qr_error_correction)
        elif self.key == "print_barcode":
            await c.async_print("print_barcode", c.drafts["barcode_data"])
        else:
            await c.async_print(self.key, c.drafts["print_text"])
