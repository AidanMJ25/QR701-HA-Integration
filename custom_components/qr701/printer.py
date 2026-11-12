"""Asynchronous serialx transport with serialized, paced print jobs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress

import serialx

from .protocol import PrinterStatus, parse_status


class QR701Printer:
    """One owner for a UART; jobs and status queries never interleave."""

    def __init__(self, port: str, baudrate: int, status_enabled: bool) -> None:
        self.port = port
        self.baudrate = baudrate
        self.status_enabled = status_enabled
        self.reader: asyncio.StreamReader | None = None
        self.writer = None
        self.lock = asyncio.Lock()
        self.closed = False

    async def _connect(self) -> None:
        if self.closed:
            raise ConnectionError("Printer is unloading")
        if self.writer is not None and not self.writer.is_closing():
            return
        await self._disconnect()
        # Do not register our own ESPHome URL handler: Home Assistant's USB
        # and ESPHome integrations provide esphome-hass:// and reuse its API.
        async with asyncio.timeout(20):
            self.reader, self.writer = await serialx.open_serial_connection(
                self.port,
                baudrate=self.baudrate,
            )

    async def _disconnect(self) -> None:
        writer, self.writer = self.writer, None
        self.reader = None
        if writer is not None:
            writer.close()
            with suppress(Exception):
                async with asyncio.timeout(5):
                    await writer.wait_closed()

    async def close(self) -> None:
        self.closed = True
        async with self.lock:
            await self._disconnect()

    async def check(self) -> PrinterStatus | None:
        """Open the port; query hardware only when RX/status is enabled."""
        async with self.lock:
            try:
                await self._connect()
                if not self.status_enabled:
                    # Detect a disconnected proxy without inventing paper status.
                    if self.reader.at_eof() or self.reader.exception():
                        raise ConnectionError("Serial connection closed")
                    return None
                return await self._status()
            except BaseException:
                # Reconnect after timeouts so late untagged replies cannot be
                # mistaken for responses to a different status query.
                await self._disconnect()
                raise

    async def _status(self) -> PrinterStatus:
        values = bytearray()
        for query in range(1, 5):
            self.writer.write(bytes([0x10, 0x04, query]))
            async with asyncio.timeout(2):
                await self.writer.drain()
                values.extend(await self.reader.readexactly(1))
        return parse_status(bytes(values))

    async def send(self, payload: bytes, on_sending: Callable[[], None]) -> None:
        """Send exactly once; never retry a partially printed receipt."""
        async with self.lock:
            try:
                await self._connect()
                if self.status_enabled:
                    status = await self._status()
                    if status.state != "idle":
                        raise ConnectionError("Printer is not ready: " + status.state)
                on_sending()
                # Small chunks and wire-time pacing prevent overwhelming cheap
                # printer buffers. Extra time at line boundaries allows heating.
                async with asyncio.timeout(300):
                    for offset in range(0, len(payload), 32):
                        if self.closed:
                            raise ConnectionError("Printer is unloading")
                        chunk = payload[offset : offset + 32]
                        self.writer.write(chunk)
                        await self.writer.drain()
                        await asyncio.sleep(
                            len(chunk) * 10 / self.baudrate + chunk.count(b"\n") * 0.1
                        )
                    # QR/barcode commands have few LF bytes but need time to
                    # render. This is a pacing delay, not a completion signal.
                    await asyncio.sleep(1)
            except BaseException:
                await self._disconnect()
                raise
