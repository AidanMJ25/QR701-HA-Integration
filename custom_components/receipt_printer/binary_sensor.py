"""Hardware fault sensors, only exposed when RX queries are enabled."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import CONF_STATUS
from .entity import ReceiptPrinterEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.data[CONF_STATUS]:
        async_add_entities(
            [
                ReceiptPrinterFault(
                    entry.runtime_data,
                    entry,
                    "paper_out",
                    "Paper out",
                    BinarySensorDeviceClass.PROBLEM,
                ),
                ReceiptPrinterFault(
                    entry.runtime_data,
                    entry,
                    "cover_open",
                    "Cover",
                    BinarySensorDeviceClass.OPENING,
                ),
                ReceiptPrinterFault(
                    entry.runtime_data, entry, "error", "Error", BinarySensorDeviceClass.PROBLEM
                ),
            ]
        )


class ReceiptPrinterFault(ReceiptPrinterEntity, BinarySensorEntity):
    def __init__(self, coordinator, entry, key, name, device_class):
        super().__init__(coordinator, entry, key, name)
        self.key = key
        self._attr_device_class = device_class

    @property
    def is_on(self):
        return (
            getattr(self.coordinator.data, self.key) if self.coordinator.data is not None else None
        )
