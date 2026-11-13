"""QR701 connection lifecycle and polling."""

from __future__ import annotations

import logging
from datetime import timedelta

import serialx
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import protocol
from .const import CONF_BAUDRATE, CONF_MODEL, CONF_STATUS, DEFAULT_MODEL, DOMAIN
from .printer import QR701Printer

LOGGER = logging.getLogger(__name__)


class QR701Coordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(
            hass, LOGGER, name=DOMAIN, config_entry=entry, update_interval=timedelta(seconds=30)
        )
        self.model = entry.data.get(CONF_MODEL, DEFAULT_MODEL)
        self.printer = QR701Printer(
            entry.data["device"], entry.data[CONF_BAUDRATE], entry.data[CONF_STATUS]
        )
        self.drafts = {"print_text": "", "qr_data": "", "barcode_data": ""}
        self.qr_size = 5
        self.qr_error_correction = "M"

    async def _async_update_data(self):
        try:
            status = await self.printer.check()
        except (
            OSError,
            EOFError,
            ConnectionError,
            TimeoutError,
            ValueError,
            serialx.SerialException,
        ):
            # Exception text may include a proxy URL/API key. Keep it out of logs.
            raise UpdateFailed(
                "Cannot read printer; check power, wiring, port and status setting"
            ) from None
        return status

    async def async_print(self, encoder, *args, **kwargs):
        if encoder is protocol.cut and self.model != "rp326":
            raise ServiceValidationError("Paper cutting is only available for Rongta RP326")
        if encoder in (protocol.text_receipt, protocol.markdown_receipt):
            kwargs["columns"] = 48 if self.model == "rp326" else 32
        try:
            payload = encoder(*args, **kwargs)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        try:
            await self.printer.send(payload, self._sending)
        except (
            OSError,
            EOFError,
            ConnectionError,
            TimeoutError,
            ValueError,
            serialx.SerialException,
        ):
            self.async_set_update_error(UpdateFailed("Print failed; receipt may be incomplete"))
            raise HomeAssistantError(
                "Printer operation failed. Check the printer before retrying; "
                "a partial receipt may have printed."
            ) from None
        finally:
            self.sending = False
            self.async_update_listeners()
        await self.async_request_refresh()

    sending = False

    def _sending(self):
        self.sending = True
        self.async_update_listeners()
