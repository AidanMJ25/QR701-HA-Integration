"""UI setup, using the same serial selector and serialx route as LG TV."""

from __future__ import annotations

import hashlib

import probatio as vol
import serialx
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_DEVICE, CONF_NAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialPortSelector,
)

from .const import (
    CONF_BAUDRATE,
    CONF_MODEL,
    CONF_STATUS,
    DEFAULT_BAUDRATE,
    DEFAULT_MODEL,
    DOMAIN,
)
from .models import MODELS, PRINTER_MODELS, SUPPORTED_BAUDRATES
from .printer import PrinterTransport


def schema(defaults):
    return vol.Schema(
        {
            vol.Required(
                CONF_MODEL, default=defaults.get(CONF_MODEL, DEFAULT_MODEL)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[{"value": key, "label": label} for key, label in MODELS.items()],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "Receipt printer")): str,
            vol.Required(CONF_DEVICE, default=defaults.get(CONF_DEVICE, "")): SerialPortSelector(),
            vol.Required(
                CONF_BAUDRATE, default=defaults.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
            ): vol.In(SUPPORTED_BAUDRATES),
            vol.Required(CONF_STATUS, default=defaults.get(CONF_STATUS, True)): bool,
        }
    )


def port_is_configured(hass, device: str, excluding_entry_id: str | None = None) -> bool:
    """Prevent two configured entries from owning the same serial port."""
    return any(
        entry.entry_id != excluding_entry_id
        and entry.domain == DOMAIN
        and entry.data.get(CONF_DEVICE) == device
        for entry in hass.config_entries.async_entries()
    )


class ReceiptPrinterConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, data):
        try:
            model = PRINTER_MODELS[data.get(CONF_MODEL, DEFAULT_MODEL)]
        except KeyError:
            return "unsupported_model"
        if data[CONF_BAUDRATE] not in model.baudrates:
            return "unsupported_baudrate"
        printer = PrinterTransport(data[CONF_DEVICE], data[CONF_BAUDRATE], data[CONF_STATUS], model)
        try:
            await printer.check()
        except ConfigEntryNotReady:
            return "proxy_not_ready"
        except TimeoutError:
            return "no_response"
        except ValueError:
            return "invalid_response"
        except OSError, EOFError, ConnectionError, serialx.SerialException:
            return "cannot_connect"
        finally:
            await printer.close()
        return None

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(
                hashlib.sha256(user_input[CONF_DEVICE].encode()).hexdigest()
            )
            self._abort_if_unique_id_configured()
            if port_is_configured(self.hass, user_input[CONF_DEVICE]):
                return self.async_abort(reason="already_configured")
            error = await self._validate(user_input)
            if error is None:
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
            errors["base"] = error
        return self.async_show_form(
            step_id="user", data_schema=schema(user_input or {}), errors=errors
        )

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            unique_id = hashlib.sha256(user_input[CONF_DEVICE].encode()).hexdigest()
            if port_is_configured(self.hass, user_input[CONF_DEVICE], entry.entry_id):
                return self.async_abort(reason="already_configured")
            # The loaded coordinator owns the proxy exclusively. Unload before
            # testing the replacement configuration; restore on validation error.
            if not await self.hass.config_entries.async_unload(entry.entry_id):
                return self.async_abort(reason="cannot_unload")
            updated = False
            try:
                error = await self._validate(user_input)
                if error is None:
                    updated = True
                    return self.async_update_reload_and_abort(
                        entry,
                        title=user_input[CONF_NAME],
                        data_updates=user_input,
                        unique_id=unique_id,
                    )
                errors["base"] = error
            finally:
                if not updated:
                    await self.hass.config_entries.async_setup(entry.entry_id)
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema(user_input or entry.data), errors=errors
        )
