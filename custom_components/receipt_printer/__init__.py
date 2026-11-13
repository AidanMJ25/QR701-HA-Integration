"""Thermal receipt printers via ESPHome serial proxy or a local serial port."""

from __future__ import annotations

import probatio as vol
from homeassistant.const import Platform
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import BARCODES, DOMAIN
from .coordinator import ReceiptPrinterCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.TEXT,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass, config):
    """Register actions once, independent of device load/unload order."""
    common = {vol.Required("device_id"): str}
    specs = {
        "print_text": {vol.Required("text"): vol.All(str, vol.Length(max=32768))},
        "print_markdown": {vol.Required("text"): vol.All(str, vol.Length(max=32768))},
        "print_qr": {
            vol.Required("text"): str,
            vol.Optional("size", default=5): vol.All(vol.Coerce(int), vol.Range(min=1, max=16)),
            vol.Optional("error_correction", default="M"): vol.In(["L", "M", "Q", "H"]),
        },
        "print_barcode": {
            vol.Required("text"): str,
            vol.Optional("format", default="CODE128"): vol.In(list(BARCODES)),
            vol.Optional("height", default=80): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
            vol.Optional("width", default=2): vol.All(vol.Coerce(int), vol.Range(min=2, max=6)),
            vol.Optional("show_text", default=True): cv.boolean,
        },
        "feed": {
            vol.Optional("lines", default=3): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        },
        "cut": {
            vol.Optional("lines", default=3): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        },
        "refresh_status": {},
    }

    async def handle(call):
        device = dr.async_get(hass).async_get(call.data["device_id"])
        entries = (
            []
            if device is None
            else [
                entry
                for entry_id in device.config_entries
                if (entry := hass.config_entries.async_get_entry(entry_id)) is not None
                and entry.domain == DOMAIN
                and getattr(entry, "runtime_data", None) is not None
            ]
        )
        if len(entries) != 1:
            raise ServiceValidationError("Select a loaded thermal printer device")
        coordinator = entries[0].runtime_data
        if call.service == "refresh_status":
            await coordinator.async_request_refresh()
        else:
            await coordinator.async_print(
                call.service, **{k: v for k, v in call.data.items() if k != "device_id"}
            )

    for name, fields in specs.items():
        hass.services.async_register(DOMAIN, name, handle, schema=vol.Schema(common | fields))
    return True


async def async_setup_entry(hass, entry):
    coordinator = ReceiptPrinterCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.printer.close()
        raise
    return True


async def async_unload_entry(hass, entry):
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.printer.close()
    return unload_ok
