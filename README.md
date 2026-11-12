# QR701 Thermal Printer for Home Assistant

A custom Home Assistant integration for the QR701 58 mm thermal receipt printer.
Home Assistant renders receipts and sends ESC/POS commands through **ESPHome Serial
Proxy**. The ESP32 exposes the printer UART using the stock `serial_proxy`
component.

## Requirements

- Home Assistant **2026.11 or newer**. This targets its `SerialPortSelector`,
  `probatio`, and `serialx` APIs, following the LG TV via Serial integration.
- ESPHome firmware with `serial_proxy` support, already added to Home Assistant.
- Your working QR701 power supply and UART wiring. Default: **9600 baud, 8-N-1**.
- Printer RX is required. Printer TX is optional; enable hardware status only if
  printer TX is connected to ESP RX at a safe logic voltage.

## ESPHome configuration

The following configuration has been tested with the QR701 and this integration:

```yaml
uart:
  id: printer_uart
  tx_pin: GPIO17       # ESP32 TX → QR701 RXD
  rx_pin: GPIO16       # ESP32 RX ← QR701 TXD
  baud_rate: 9600
  data_bits: 8
  parity: NONE
  stop_bits: 1

serial_proxy:
  - id: printer_serial
    uart_id: printer_uart
    name: "Receipt Printer TTL"
    port_type: TTL
```

Merge this into your existing ESPHome configuration, keeping your board, Wi-Fi,
API, OTA and logger settings. The UART uses **9600 baud, 8 data bits, no parity,
and 1 stop bit**. `printer_serial` is the ESPHome component ID;
**Receipt Printer TTL** is the port name shown in Home Assistant.

For transmit-only wiring, omit `rx_pin` and disable hardware status in the
integration. With printer TXD connected safely to GPIO16, hardware status can be
enabled if the printer firmware supports the status commands.

The same configuration is available in [examples/esphome.yaml](examples/esphome.yaml).

## Install

1. Copy `custom_components/qr701` into `/config/custom_components/qr701` on Home
   Assistant. Restart Home Assistant.
2. Add the UART and serial proxy configuration above to your ESPHome device,
   then flash it. If `printer_uart` already exists, update that block instead of
   defining it twice.
3. Confirm the ESPHome device is connected in Home Assistant.
4. Open **Settings → Devices & services → Add integration → QR701 Thermal Printer**.
5. Select **Receipt Printer TTL**, set the baud rate to **9600**, and choose whether
   hardware status is enabled. Setup opens the port and, when enabled, verifies
   all four status replies. Setup does not print anything.

The serial selector supplies an `esphome-hass://...` URL. `serialx` uses Home
Assistant's existing ESPHome API connection, including its authentication; there
is no TCP-to-UART server, MQTT broker, or manually copied encryption key involved.
The `usb` dependency registers the transport while ESPHome starts. The integration
also accepts local serial paths and other serialx URLs through the selector.

The original QR701 ESPHome external component can remain configured alongside
`serial_proxy` on `printer_uart`; removing it is not required. Coordinate print
jobs and status polling so the two control paths do not send commands or consume
status replies at the same time. Keep UART logging off this printer UART.

For HACS, add `https://github.com/AidanMJ25/QR701-HA-Integration` as a custom
repository with category **Integration**, then install and restart. The original
ESPHome external-component repository is separate and remains available.

## Controls

The device exposes:

- Text drafts for receipts, QR data, and barcode data.
- Buttons to print literal text, Markdown, QR codes, or Code 128 barcodes.
- QR module size (1–16) and error correction (L/M/Q/H), restored after restart.
- Feed paper (three lines) and refresh status buttons.
- A status sensor, plus paper-out, cover-open and error sensors when status is on.

Drafts are restored after restart and limited to **255 characters**, matching
Home Assistant's entity-state limit. Use the actions below for longer receipts.
`sending` means Home Assistant is transmitting data; it is **not** a physical
printing-complete signal. With status disabled, the status sensor is `unknown`
outside transmission; a connected proxy cannot prove that the printer is powered.

## Automation actions

Choose the **QR701 printer device** in Developer Tools → Actions. Replace
`YOUR_QR701_DEVICE_ID` below with that device's ID. These actions take `device_id`
in `data`; they do not use a `target` entity ID.

```yaml
action: qr701.print_markdown
data:
  device_id: YOUR_QR701_DEVICE_ID
  text: |-
    # Shopping list
    **Remember the paper!**
    - Coffee
    - Milk
    ---
    Printed by Home Assistant
```

```yaml
action: qr701.print_qr
data:
  device_id: YOUR_QR701_DEVICE_ID
  text: https://blog.aidanmaurinjones.com
  size: 5
  error_correction: M
```

```yaml
action: qr701.print_barcode
data:
  device_id: YOUR_QR701_DEVICE_ID
  text: "123456789012"
  format: CODE128
  height: 80
  width: 2
  show_text: true
```

| Action | Other fields |
| --- | --- |
| `qr701.print_text` | `text`: literal text, wraps at 32 columns |
| `qr701.print_markdown` | `text`: headings, inline styles, lists, quotes, links, rules, fenced code |
| `qr701.print_qr` | `text`: 1–7092 UTF-8 bytes; `size`: 1–16; `error_correction`: L/M/Q/H |
| `qr701.print_barcode` | `text`: up to 252 printable ASCII bytes; `format`, `height`: 1–255, `width`: 2–6, `show_text` |
| `qr701.feed` | `lines`: 0–255, default 3 |
| `qr701.refresh_status` | No additional fields |

All actions require `device_id`. Text and Markdown actions accept up to 32,768
characters. Barcode formats: UPC_A, UPC_E, EAN13, EAN8, CODE39, ITF, CODABAR,
CODE93, CODE128. Code 128 uses Code Set B and treats braces literally; unlike the
original component it does not interpret `{A`, `{B`, or `{C` as code-set overrides.
UPC/EAN check digits are handled by the printer. Oversized symbols may not fit
the 384-dot print area; reduce module/bar width or payload length.

## Behaviour and limitations

- Literal text and Markdown use portable **ASCII**. Other characters become `?`;
  this does not claim UTF-8 text support on an ESC/POS printer. QR data uses UTF-8.
- Control characters in printable text are sanitized. Raw ESC/POS submission is
  intentionally not exposed as an action.
- H1 headings wrap at 16 columns; other text wraps at 32. Bold/italic/underline
  and font changes depend on the printer's firmware. Strikethrough uses underline.
  Images, tables, HTML and CSS are not rendered.
- Native QR and barcode commands match the original component. Firmware support
  varies by QR701 revision. There is no raster graphics fallback.
- Jobs and status polls are serialized. Writes are chunked and paced for small
  printer buffers; there is no DTR flow control. Start with short receipts and
  test long jobs on your unit before relying on them unattended.
- Hardware status uses `DLE EOT 1..4` with two seconds per reply. Some printer
  revisions do not support these queries; disable status for those units.
- Status is polled every 30 seconds. Broken connections are reopened on the next
  poll/action. A status timeout closes the port to discard untagged late replies.
- A failed or partially transmitted print is **never automatically replayed**.
- Use the integration's **Reconfigure** menu to change the port, baud, or status
  option. Existing ESPHome entity IDs will not migrate; update your automations.

## Development and validation

```sh
python3 -m unittest discover -s tests -p 'test_standalone.py' -v
```

The standalone suite checks receipt bytes, Markdown wrapping, input validation,
status decoding, in-memory async streams, and the real serialx socket transport
against a simulated printer, including concurrent jobs and failure recovery.
Socket tests skip when the execution environment forbids TCP listeners; the
in-memory transport tests still run. Install `serialx==1.15.1`
first. It does not require Home Assistant or physical printer hardware.

For Home Assistant tests, install `.[test]` in a separate environment and run
`pytest tests/test_integration.py`. CI runs both suites. Hardware testing remains
necessary before calling this release production-ready.

Initial local validation: 15 standalone tests passed; six socket tests were
skipped because the sandbox forbids TCP listeners. Ruff and Python compilation
passed. The Home Assistant lifecycle suite is provided for CI and was not run
locally; installation on a live Home Assistant instance and physical printer
output have not been verified.

## Sources

- [Original QR701 external component](https://github.com/AidanMJ25/QR701-ESPHome-External-Component),
  protocol reference at `e09da678a603e2266d961da6965eabb7c35f1178`.
- [Home Assistant LG TV via Serial](https://github.com/home-assistant/core/tree/2026.11.1/homeassistant/components/lg_tv_rs232),
  reference for config-entry setup, serial selection, and connection handling.
- [serialx](https://github.com/puddly/serialx), the asynchronous serial transport.
- [ESPHome Serial Proxy](https://esphome.io/components/serial_proxy/).
