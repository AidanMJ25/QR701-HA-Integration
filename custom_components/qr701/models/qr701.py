"""QR701 model driver."""

from .base import PrinterModel

MODEL = PrinterModel(
    model_id="qr701",
    label="QR701",
    manufacturer="QR701",
    device_model="QR701 58 mm TTL",
    text_columns=32,
    baudrates=(9600, 19200, 38400, 57600, 115200),
    status_queries=tuple(bytes([0x10, 0x04, query]) for query in range(1, 5)),
)
