"""Rongta RP326 model driver."""

from .base import PrinterModel

MODEL = PrinterModel(
    model_id="rp326",
    label="Rongta RP326",
    manufacturer="Rongta",
    device_model="RP326 80 mm RS-232",
    text_columns=48,
    baudrates=(9600, 19200, 38400, 115200),
    status_queries=tuple(bytes([0x10, 0x04, query]) for query in range(1, 5)),
    supports_cut=True,
)
