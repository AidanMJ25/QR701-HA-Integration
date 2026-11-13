"""Base contract for a printer model driver.

Each model owns its electrical/protocol differences here. Shared Home Assistant
setup, entities, and transport lifecycle stay outside the model drivers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrinterModel:
    """Capabilities and ESC/POS behaviour for one supported printer model."""

    model_id: str
    label: str
    manufacturer: str
    device_model: str
    text_columns: int
    baudrates: tuple[int, ...]
    status_queries: tuple[bytes, ...]
    supports_cut: bool = False

    def encode(self, operation: str, *args, **kwargs) -> bytes:
        """Encode an integration operation for this printer model.

        Override this method in a model module when a printer uses different
        ESC/POS commands, text encoding, or a model-specific operation.
        """
        from .. import protocol

        encoders = {
            "print_text": lambda: protocol.text_receipt(*args, columns=self.text_columns, **kwargs),
            "print_markdown": lambda: protocol.markdown_receipt(
                *args, columns=self.text_columns, **kwargs
            ),
            "print_qr": lambda: protocol.qr_receipt(*args, **kwargs),
            "print_barcode": lambda: protocol.barcode_receipt(*args, **kwargs),
            "feed": lambda: protocol.feed(*args, **kwargs),
            "cut": lambda: protocol.cut(*args, **kwargs),
        }
        if operation == "cut" and not self.supports_cut:
            raise ValueError(f"Paper cutting is not available for {self.label}")
        try:
            return encoders[operation]()
        except KeyError as err:
            raise ValueError(f"Unsupported printer operation: {operation}") from err

    def parse_status(self, values: bytes):
        """Decode status replies; override when a model uses another format."""
        from ..protocol import parse_status

        return parse_status(values)
