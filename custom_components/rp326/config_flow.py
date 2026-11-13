"""UI setup, using the same serial selector and serialx route as LG TV."""

from __future__ import annotations

import hashlib

import probatio as vol
import serialx
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_DEVICE, CONF_NAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.selector import SerialPortSelector

from .const import CONF_BAUDRATE, CONF_STATUS, DEFAULT_BAUDRATE, DOMAIN
from .printer import RP326Printer


def schema(defaults):
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "RP326")): str,
            vol.Required(CONF_DEVICE, default=defaults.get(CONF_DEVICE, "")): SerialPortSelector(),
            vol.Required(
                CONF_BAUDRATE, default=defaults.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
            ): vol.In([9600, 19200, 38400, 115200]),
            vol.Required(CONF_STATUS, default=defaults.get(CONF_STATUS, True)): bool,
        }
    )


class RP326ConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, data):
        printer = RP326Printer(data[CONF_DEVICE], data[CONF_BAUDRATE], data[CONF_STATUS])
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
            if any(
                other.entry_id != entry.entry_id and other.unique_id == unique_id
                for other in self._async_current_entries()
            ):
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
