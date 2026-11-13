"""Protocol and real serialx tests without importing Home Assistant."""

import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Load only the HA-independent modules under an isolated package name.
ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "receipt_printer"
package = types.ModuleType("receipt_printer_standalone")
package.__path__ = [str(ROOT)]
sys.modules[package.__name__] = package
for name in ("const", "protocol", "printer"):
    spec = importlib.util.spec_from_file_location(
        f"receipt_printer_standalone.{name}", ROOT / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

from receipt_printer_standalone import protocol as p  # noqa: E402
from receipt_printer_standalone.models import PRINTER_MODELS, SUPPORTED_BAUDRATES, get_model  # noqa: E402
from receipt_printer_standalone.printer import PrinterTransport  # noqa: E402


class ProtocolTests(unittest.TestCase):
    def test_model_capabilities_are_centralized(self):
        self.assertEqual(get_model(None), PRINTER_MODELS["qr701"])
        self.assertEqual(get_model("rp326").text_columns, 48)
        self.assertTrue(get_model("rp326").supports_cut)
        self.assertFalse(get_model("qr701").supports_cut)
        self.assertNotIn(57600, get_model("rp326").baudrates)
        self.assertIn(57600, get_model("qr701").baudrates)
        self.assertEqual(SUPPORTED_BAUDRATES, (9600, 19200, 38400, 57600, 115200))
        self.assertEqual(len(get_model("qr701").status_queries), 4)
        self.assertIn(
            b"X" * 48 + b"\nX\n",
            get_model("rp326").encode("print_text", "X" * 49),
        )

    def test_model_width_and_cutter(self):
        self.assertIn(b"X" * 48 + b"\nX\n", p.text_receipt("X" * 49, columns=48))
        self.assertIn(b"-" * 48 + b"\n", p.markdown_receipt("---", columns=48))
        data = p.markdown_receipt("# " + "X" * 25, columns=48)
        self.assertEqual(data.count(b"\x1ba\x01\x1b!\x30"), 2)
        self.assertEqual(p.cut(2), b"\x1bd\x02\x1dV\x01")
        with self.assertRaises(ValueError):
            p.cut(256)

    def test_literal_wrap_and_controls(self):
        self.assertEqual(p.text_receipt("Hello"), b"\x1b@Hello\n\n\n\n")
        self.assertIn(b"X" * 32 + b"\nX\n", p.text_receipt("X" * 33))
        self.assertIn(b"A @ ?\n", p.text_receipt("A\x1b@ é"))

    def test_markdown_heading_and_rule(self):
        data = p.markdown_receipt("# Heading\n---\n- Item\n> Quote")
        self.assertIn(b"\x1ba\x01\x1b!\x30", data)
        self.assertIn(b"-" * 32 + b"\n", data)
        self.assertIn(b"- ", data)
        self.assertIn(b"| ", data)

    def test_inline_style_continues_after_wrap(self):
        data = p.markdown_receipt("**" + "word " * 12 + "**")
        self.assertGreaterEqual(data.count(b"\x1bE\x01"), 2)
        self.assertTrue(data.endswith(p.NORMAL + b"\n" + p.FEED))

    def test_italic_commands_have_no_parameter(self):
        data = p.markdown_receipt("*Italic*")
        self.assertIn(b"\x1b4", data)
        self.assertNotIn(b"\x1b4\x01", data)

    def test_qr_byte_length_not_character_length(self):
        data = p.qr_receipt("é", 4, "H")
        self.assertIn(b"\x1d(k\x05\x001P0\xc3\xa9", data)
        self.assertIn(b"1E3", data)
        for args in (("", 5, "M"), ("x", 17, "M"), ("x", 5, ""), ("x", 5, "LM")):
            with self.assertRaises(ValueError):
                p.qr_receipt(*args)

    def test_barcode_length_and_literal_braces(self):
        data = p.barcode_receipt("a{B")
        self.assertIn(b"\x1dkI\x06{Ba{{B", data)
        with self.assertRaises(ValueError):
            p.barcode_receipt("{" * 252)

    def test_barcode_validation(self):
        for text, fmt in (
            ("bad", "EAN13"),
            ("123", "ITF"),
            ("lower", "CODE39"),
            ("123", "CODABAR"),
            ("a\x00b", "CODE128"),
        ):
            with self.assertRaises(ValueError):
                p.barcode_receipt(text, fmt)
        self.assertIn(b"\x1dkC\x0c123456789012", p.barcode_receipt("123456789012", "EAN13"))

    def test_feed_limits(self):
        self.assertEqual(p.feed(3), b"\x1bd\x03")
        with self.assertRaises(ValueError):
            p.feed(256)

    def test_status_bits_and_priority(self):
        self.assertEqual(p.parse_status(bytes([0x12] * 4)).state, "idle")
        self.assertEqual(p.parse_status(bytes([0x1A, 0x36, 0x12, 0x72])).state, "paper_out")
        self.assertEqual(p.parse_status(bytes([0x12, 0x16, 0x12, 0x12])).state, "cover_open")
        self.assertEqual(p.parse_status(bytes([0x12, 0x12, 0x16, 0x12])).state, "error")
        for bad in (b"", b"\x00" * 4, b"\xff" * 4):
            with self.assertRaises(ValueError):
                p.parse_status(bad)


class MemoryTransportTests(unittest.IsolatedAsyncioTestCase):
    """Exercise async stream behaviour even in network-restricted sandboxes."""

    async def asyncSetUp(self):
        self.received = bytearray()
        self.queries = []
        self.clients = []
        self.reply = True
        owner = self

        class Writer:
            def __init__(self, reader):
                self.reader = reader
                self.closing = False

            def write(self, data):
                if data.startswith(b"\x10\x04"):
                    owner.queries.append(data)
                    if owner.reply:
                        self.reader.feed_data(b"\x12")
                else:
                    owner.received.extend(data)

            async def drain(self):
                await asyncio.sleep(0)

            def is_closing(self):
                return self.closing

            def close(self):
                self.closing = True
                self.reader.feed_eof()

            async def wait_closed(self):
                pass

        async def connect(url, **kwargs):
            self.assertEqual(url, "esphome-hass://test/?port_name=QR701")
            self.assertEqual(kwargs, {"baudrate": 19200})
            reader = asyncio.StreamReader()
            writer = Writer(reader)
            self.clients.append(writer)
            return reader, writer

        self.open_patch = patch(
            "receipt_printer_standalone.printer.serialx.open_serial_connection", connect
        )
        self.open_patch.start()
        self.printer = PrinterTransport(
            "esphome-hass://test/?port_name=QR701", 19200, True, get_model("qr701")
        )

    async def asyncTearDown(self):
        await self.printer.close()
        self.open_patch.stop()

    async def test_status_queries(self):
        self.assertEqual((await self.printer.check()).state, "idle")
        self.assertEqual(self.queries, [bytes([16, 4, i]) for i in range(1, 5)])

    async def test_tx_only_does_not_query_hardware(self):
        self.printer.status_enabled = False
        self.assertIsNone(await self.printer.check())
        self.assertEqual(self.queries, [])

    async def test_concurrent_jobs_are_not_interleaved(self):
        await asyncio.gather(
            self.printer.send(b"A" * 80, lambda: None), self.printer.send(b"B" * 80, lambda: None)
        )
        self.assertEqual(self.received, b"A" * 80 + b"B" * 80)
        self.assertEqual(len(self.queries), 8)

    async def test_timeout_discards_connection_and_recovers(self):
        self.reply = False
        with self.assertRaises(TimeoutError):
            await self.printer.check()
        self.assertIsNone(self.printer.writer)
        self.reply = True
        self.assertEqual((await self.printer.check()).state, "idle")
        self.assertEqual(len(self.clients), 2)

    async def test_partial_write_is_not_replayed(self):
        self.printer.status_enabled = False
        await self.printer.check()
        original = self.printer.writer.drain
        calls = 0

        async def fail_after_chunk():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("connection dropped")
            await original()

        with patch.object(self.printer.writer, "drain", fail_after_chunk):
            with self.assertRaises(OSError):
                await self.printer.send(b"X" * 96, lambda: None)
        self.assertEqual(self.received, b"X" * 64)
        self.assertEqual(len(self.clients), 1)
        self.assertIsNone(self.printer.writer)

    async def test_cancel_releases_port(self):
        self.reply = False
        task = asyncio.create_task(self.printer.check())
        await asyncio.sleep(0.1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertIsNone(self.printer.writer)
        self.assertFalse(self.printer.lock.locked())


class SocketTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.received = bytearray()
        self.queries = []
        self.clients = []
        self.tasks = set()
        self.reply = True

        async def client(reader, writer):
            self.clients.append(writer)
            task = asyncio.current_task()
            self.tasks.add(task)
            try:
                while data := await reader.read(1):
                    if data == b"\x10":
                        suffix = await reader.readexactly(2)
                        self.queries.append(data + suffix)
                        if self.reply:
                            writer.write(b"\x12")
                            await writer.drain()
                    else:
                        self.received.extend(data)
            except asyncio.IncompleteReadError, ConnectionError:
                pass
            finally:
                writer.close()
                await writer.wait_closed()
                self.tasks.discard(task)

        try:
            self.server = await asyncio.start_server(client, "127.0.0.1", 0)
        except PermissionError:
            self.skipTest(
                "Sandbox does not allow local TCP listeners; memory transport tests still run"
            )
        port = self.server.sockets[0].getsockname()[1]
        self.printer = PrinterTransport(
            f"socket://127.0.0.1:{port}", 19200, True, get_model("qr701")
        )

    async def asyncTearDown(self):
        await self.printer.close()
        for writer in self.clients:
            writer.close()
        self.server.close()
        await self.server.wait_closed()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

    async def test_real_serialx_status_queries(self):
        self.assertEqual((await self.printer.check()).state, "idle")
        self.assertEqual(self.queries, [bytes([16, 4, i]) for i in range(1, 5)])

    async def test_tx_only_does_not_query_hardware(self):
        self.printer.status_enabled = False
        self.assertIsNone(await self.printer.check())
        self.assertEqual(self.queries, [])

    async def test_concurrent_jobs_are_not_interleaved(self):
        await asyncio.gather(
            self.printer.send(b"A" * 80, lambda: None), self.printer.send(b"B" * 80, lambda: None)
        )
        self.assertEqual(self.received, b"A" * 80 + b"B" * 80)
        self.assertEqual(len(self.queries), 8)

    async def test_timeout_discards_connection_and_recovers(self):
        self.reply = False
        with self.assertRaises(TimeoutError):
            await self.printer.check()
        self.assertIsNone(self.printer.writer)
        self.reply = True
        self.assertEqual((await self.printer.check()).state, "idle")
        self.assertEqual(len(self.clients), 2)

    async def test_failed_write_not_replayed(self):
        await self.printer.check()
        with patch.object(
            self.printer.writer, "drain", new=AsyncMock(side_effect=OSError("disconnected"))
        ):
            with self.assertRaises(OSError):
                await self.printer.send(b"receipt", lambda: None)
        self.assertIsNone(self.printer.writer)
        self.assertNotIn(b"receipt", self.received)

    async def test_cancel_releases_port(self):
        self.reply = False
        task = asyncio.create_task(self.printer.check())
        await asyncio.sleep(0.1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertIsNone(self.printer.writer)
        self.assertFalse(self.printer.lock.locked())


if __name__ == "__main__":
    unittest.main()
