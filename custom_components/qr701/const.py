"""Shared thermal-printer integration constants."""

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
