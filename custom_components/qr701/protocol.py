"""Pure QR701 ESC/POS encoding, independent of Home Assistant.

Adapted from AidanMJ25/QR701-ESPHome-External-Component, revision
e09da678a603e2266d961da6965eabb7c35f1178. All text is printed using ASCII;
unsupported characters become ?. QR payloads use UTF-8.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass

from .const import BARCODES

RESET = b"\x1b@"
FEED = b"\n\n\n"
NORMAL = b"\x1bE\x00\x1b5\x1b-\x00\x1bM\x00\x1b!\x00\x1ba\x00"


def clean_text(text: str) -> str:
    """Prevent user text from injecting ESC/POS or real-time commands."""
    return (
        "".join(c if c >= " " and c != "\x7f" else " " for c in text)
        .encode("ascii", "replace")
        .decode("ascii")
    )


def _wrap(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width, break_long_words=True, break_on_hyphens=False) or [""]


def text_receipt(text: str, columns: int = 32) -> bytes:
    """Wrap literal text at the selected model width and feed to the tear edge."""
    lines = [
        part for line in text.splitlines() or [""] for part in _wrap(clean_text(line), columns)
    ]
    return RESET + ("\n".join(lines) + "\n").encode("ascii") + FEED


def _glyphs(text: str) -> list[tuple[str, int]]:
    """Parse inline styles before wrapping, preserving styles across lines."""
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    result: list[tuple[str, int]] = []
    style = 0
    index = 0
    markers = (("**", 1), ("__", 1), ("~~", 4), ("*", 2), ("_", 2), ("`", 8))
    while index < len(text):
        if text[index] == "\\" and index + 1 < len(text):
            result.append((text[index + 1], style))
            index += 2
            continue
        for marker, flag in markers:
            if text.startswith(marker, index):
                style ^= flag
                index += len(marker)
                break
        else:
            result.append((text[index], style))
            index += 1
    return result


def _styled_line(glyphs: list[tuple[str, int]], heading: bool) -> bytes:
    data = bytearray()
    previous = -1
    for char, style in glyphs:
        if style != previous:
            data.extend(b"\x1bE" + bytes([bool(style & 1) or heading]))
            data.extend(b"\x1b4" if style & 2 else b"\x1b5")
            data.extend(b"\x1b-" + bytes([bool(style & 4)]))
            data.extend(b"\x1bM" + bytes([bool(style & 8)]))
            previous = style
        data.extend(char.encode("ascii"))
    return bytes(data)


def markdown_receipt(text: str, columns: int = 32) -> bytes:
    """Render headings, lists, quotes, rules, links, and inline styles."""
    data = bytearray(RESET)
    fenced = False
    for source in text.splitlines() or [""]:
        source = clean_text(source)
        if source.startswith("```"):
            fenced = not fenced
            continue
        heading = re.match(r"^(#{1,3}) +(.+)$", source) if not fenced else None
        prefix = ""
        width = columns
        mode = 0
        if not fenced and re.fullmatch(r"([-*_])\1{2,}", source.strip()):
            data.extend(b"-" * columns + b"\n")
            continue
        if heading:
            source = heading[2]
            mode = 0x30 if len(heading[1]) == 1 else 0x10
            width = columns // 2 if mode == 0x30 else columns
        elif not fenced and source.startswith("> "):
            prefix, source = "| ", source[2:]
        elif not fenced and source.startswith(("- ", "* ", "+ ")):
            prefix, source = "- ", source[2:]
        glyphs = [(c, 8) for c in source] if fenced else _glyphs(source)
        plain = "".join(c for c, _ in glyphs)
        # textwrap supplies boundaries; consume the same glyphs to retain styles.
        cursor = 0
        for line in _wrap(plain, width - len(prefix)):
            cursor = plain.find(line, cursor)
            selected = glyphs[cursor : cursor + len(line)]
            cursor += len(line)
            data.extend(b"\x1ba" + bytes([bool(heading)]) + b"\x1b!" + bytes([mode]))
            data.extend(prefix.encode("ascii") + _styled_line(selected, bool(heading)))
            data.extend(NORMAL + b"\n")
    return bytes(data) + FEED


def feed(lines: int) -> bytes:
    if not 0 <= lines <= 255:
        raise ValueError("Feed must be between 0 and 255 lines")
    return b"\x1bd" + bytes([lines])


def qr_receipt(text: str, size: int = 5, error_correction: str = "M") -> bytes:
    payload = text.encode("utf-8")
    if (
        not 1 <= len(payload) <= 7092
        or not 1 <= size <= 16
        or error_correction not in "LMQH"
        or len(error_correction) != 1
    ):
        raise ValueError("Invalid QR data, module size, or error correction")

    def command(value: bytes) -> bytes:
        return b"\x1d(k" + len(value).to_bytes(2, "little") + value

    return (
        RESET
        + b"\x1ba\x01"
        + command(b"1A2\x00")
        + command(b"1C" + bytes([size]))
        + command(b"1E" + bytes([48 + "LMQH".index(error_correction)]))
        + command(b"1P0" + payload)
        + command(b"1Q0")
        + FEED
        + NORMAL
    )


def barcode_receipt(
    text: str, format: str = "CODE128", height: int = 80, width: int = 2, show_text: bool = True
) -> bytes:
    """Encode Function B barcodes, validating lengths and character sets."""
    if format not in BARCODES or not 1 <= height <= 255 or not 2 <= width <= 6:
        raise ValueError("Invalid barcode format, height, or width")
    try:
        payload = text.encode("ascii")
    except UnicodeEncodeError as err:
        raise ValueError("Barcode data must be ASCII") from err
    if not 1 <= len(payload) <= 252 or any(c < 32 or c > 126 for c in payload):
        raise ValueError("Barcode data must contain 1 to 252 printable ASCII bytes")
    lengths = {"UPC_A": (11, 12), "UPC_E": (6, 7, 8), "EAN13": (12, 13), "EAN8": (7, 8)}
    if format in lengths and (not text.isdigit() or len(text) not in lengths[format]):
        raise ValueError("Invalid UPC/EAN digit count")
    if format == "ITF" and (not text.isdigit() or len(text) % 2):
        raise ValueError("ITF requires an even number of digits")
    if format == "CODE39" and not re.fullmatch(r"[0-9A-Z .$/+%\-]+", text):
        raise ValueError("Invalid Code 39 characters")
    if format == "CODABAR" and not re.fullmatch(r"[A-D][0-9$:/+.\-]+[A-D]", text):
        raise ValueError("Codabar requires A-D start and stop characters")
    if format == "CODE128":
        # Always use Code B; escape literal braces rather than interpreting
        # untrusted text as code-set switches or function characters.
        payload = b"{B" + payload.replace(b"{", b"{{")
    if len(payload) > 255:
        raise ValueError("Encoded barcode exceeds the 255-byte command limit")
    return (
        RESET
        + b"\x1dH"
        + bytes([2 if show_text else 0])
        + b"\x1dh"
        + bytes([height])
        + b"\x1dw"
        + bytes([width])
        + b"\x1ba\x01\x1dk"
        + bytes([BARCODES[format], len(payload)])
        + payload
        + FEED
        + NORMAL
    )


@dataclass(frozen=True)
class PrinterStatus:
    offline: bool
    cover_open: bool
    paper_out: bool
    error: bool

    @property
    def state(self) -> str:
        for key in ("error", "paper_out", "cover_open", "offline"):
            if getattr(self, key):
                return key
        return "idle"


def parse_status(values: bytes) -> PrinterStatus:
    if len(values) != 4 or any(value & 0x93 != 0x12 for value in values):
        raise ValueError("Invalid ESC/POS real-time status response")
    return PrinterStatus(
        bool(values[0] & 8),
        bool(values[1] & 4),
        bool(values[1] & 32 or values[3] & 96),
        bool(values[1] & 64 or values[2] & 0x6C),
    )


def cut(lines: int = 3) -> bytes:
    """Feed clear of the print head, then request a partial cut (RP326 only)."""
    return feed(lines) + b"\x1dV\x01"
