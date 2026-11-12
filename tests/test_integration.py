"""Home Assistant config flow, entity, service and unload coverage."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.qr701.const import DOMAIN
from custom_components.qr701.protocol import PrinterStatus

DATA = {
    "name": "Receipt printer",
    "device": "esphome-hass://printer/?port_name=QR701",
    "baudrate": 9600,
    "status_enabled": True,
}
IDLE = PrinterStatus(False, False, False, False)


@pytest.fixture(autouse=True)
def enable_integration(enable_custom_integrations):
    """Load custom components in the Home Assistant test harness."""


@pytest.fixture
def printer():
    with (
        patch(
            "custom_components.qr701.printer.QR701Printer.check",
            new_callable=AsyncMock,
            return_value=IDLE,
        ) as check,
        patch(
            "custom_components.qr701.printer.QR701Printer.close", new_callable=AsyncMock
        ) as close,
        patch("custom_components.qr701.printer.QR701Printer.send", new_callable=AsyncMock) as send,
        patch(
            "homeassistant.components.usb.async_setup", new_callable=AsyncMock, return_value=True
        ),
    ):
        yield {"check": check, "close": close, "send": send}


async def load(hass, data=None):
    entry = MockConfigEntry(domain=DOMAIN, title="Receipt printer", data=data or DATA)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_user_flow(hass: HomeAssistant, printer):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    with patch("custom_components.qr701.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == DATA
    printer["close"].assert_awaited()


async def test_status_timeout_returns_form(hass: HomeAssistant, printer):
    printer["check"].side_effect = TimeoutError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_response"}
    printer["close"].assert_awaited_once()


async def test_setup_entities_print_action_and_unload(hass: HomeAssistant, printer):
    entry = await load(hass)
    states = hass.states.async_all()
    assert len(states) == 15
    assert any(state.state == "idle" for state in states if state.domain == "sensor")
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    await hass.services.async_call(
        DOMAIN, "print_text", {"device_id": device.id, "text": "Hello"}, blocking=True
    )
    assert printer["send"].await_args.args[0] == b"\x1b@Hello\n\n\n\n"
    await hass.config_entries.async_unload(entry.entry_id)
    printer["close"].assert_awaited_once()


async def test_tx_only_has_no_fault_sensors(hass: HomeAssistant, printer):
    printer["check"].return_value = None
    await load(hass, DATA | {"status_enabled": False})
    assert not hass.states.async_all("binary_sensor")
    assert hass.states.async_all("sensor")[0].state == "unknown"


async def test_unknown_device_and_invalid_barcode(hass: HomeAssistant, printer):
    entry = await load(hass)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "print_text", {"device_id": "missing", "text": "Hello"}, blocking=True
        )
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "print_barcode",
            {"device_id": device.id, "text": "123", "format": "ITF"},
            blocking=True,
        )
    printer["send"].assert_not_awaited()


async def test_setup_failure_closes_port(hass: HomeAssistant, printer):
    printer["check"].side_effect = TimeoutError
    entry = MockConfigEntry(domain=DOMAIN, title="Receipt printer", data=DATA)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    printer["close"].assert_awaited_once()


async def test_reconfigure_releases_exclusive_port(hass: HomeAssistant, printer):
    entry = await load(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DATA | {"baudrate": 19200}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert entry.data["baudrate"] == 19200
    assert printer["close"].await_count >= 2
