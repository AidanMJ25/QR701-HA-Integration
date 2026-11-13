"""Model drivers available through the shared thermal-printer integration."""

from .base import PrinterModel
from .qr701 import MODEL as QR701_MODEL
from .rp326 import MODEL as RP326_MODEL

PRINTER_MODELS: dict[str, PrinterModel] = {
    QR701_MODEL.model_id: QR701_MODEL,
    RP326_MODEL.model_id: RP326_MODEL,
}
MODELS = {model_id: model.label for model_id, model in PRINTER_MODELS.items()}
SUPPORTED_BAUDRATES = tuple(
    sorted({baudrate for model in PRINTER_MODELS.values() for baudrate in model.baudrates})
)


def get_model(model_id: str | None) -> PrinterModel:
    """Return the driver for a configured model, defaulting old entries to QR701."""
    return PRINTER_MODELS[model_id or "qr701"]
