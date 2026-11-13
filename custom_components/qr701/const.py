"""Shared thermal-printer integration constants and model capabilities."""

from dataclasses import dataclass

DOMAIN = "qr701"
# The repository previously shipped RP326 as a separate integration. Keep its
# domain here solely to prevent two integrations opening the same serial port.
LEGACY_RP326_DOMAIN = "rp326"
CONF_BAUDRATE = "baudrate"
CONF_STATUS = "status_enabled"
DEFAULT_BAUDRATE = 9600
BARCODES = {
    "UPC_A": 65,
    "UPC_E": 66,
    "EAN13": 67,
    "EAN8": 68,
    "CODE39": 69,
    "ITF": 70,
    "CODABAR": 71,
    "CODE93": 72,
    "CODE128": 73,
}
STATUS_OPTIONS = ["idle", "sending", "offline", "paper_out", "cover_open", "error", "unknown"]

CONF_MODEL = "model"
DEFAULT_MODEL = "qr701"


@dataclass(frozen=True)
class PrinterModel:
    """Hardware behaviour that varies between supported printer models.

    Add a model here rather than scattering model-name checks across platforms,
    services, entity metadata, and receipt rendering.
    """

    label: str
    manufacturer: str
    device_model: str
    text_columns: int
    baudrates: tuple[int, ...]
    supports_cut: bool = False


PRINTER_MODELS = {
    "qr701": PrinterModel(
        label="QR701",
        manufacturer="QR701",
        device_model="QR701 58 mm TTL",
        text_columns=32,
        baudrates=(9600, 19200, 38400, 57600, 115200),
    ),
    "rp326": PrinterModel(
        label="Rongta RP326",
        manufacturer="Rongta",
        device_model="RP326 80 mm RS-232",
        text_columns=48,
        baudrates=(9600, 19200, 38400, 115200),
        supports_cut=True,
    ),
}

# Kept as simple data for the config-flow selector.
MODELS = {model_id: model.label for model_id, model in PRINTER_MODELS.items()}
SUPPORTED_BAUDRATES = tuple(
    sorted({baudrate for model in PRINTER_MODELS.values() for baudrate in model.baudrates})
)


def get_model(model_id: str | None) -> PrinterModel:
    """Return a model capability record, defaulting old entries to QR701."""
    return PRINTER_MODELS[model_id or DEFAULT_MODEL]
