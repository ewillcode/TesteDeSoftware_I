"""Small dependency-free PDF writer for printable TestingStudio reports."""

from __future__ import annotations

import re
import textwrap


PAGE_WIDTH = 842  # Landscape A4 in PDF points.
PAGE_HEIGHT = 595
LEFT = 42
TOP = 555
BOTTOM = 46
LINE_HEIGHT = 13


def _printable(value: object) -> str:
    text = str(value)
    for original, replacement in {
        "→": "->", "−": "-", "ε": "epsilon", "×": "x", "÷": "/",
        "≥": ">=", "≤": "<=", "≠": "!=", "•": "-", "—": "-", "–": "-",
        "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...",
    }.items():
        text = text.replace(original, replacement)
    return text.encode("cp1252", errors="replace").decode("cp1252")


def _pdf_string(value: str) -> bytes:
    return _printable(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("cp1252")


def _make_lines(title: str, sections: list[tuple[str, list[dict[str, object]]]], report: str) -> list[tuple[str, bool]]:
    lines: list[tuple[str, bool]] = [(title, True), ("CAD0001 | TestingStudio Web", False), ("", False)]
    for section_title, rows in sections:
        lines.extend([("", False), (section_title, True)])
        if not rows:
            lines.append(("Nenhum resultado.", False))
            continue
        for number, row in enumerate(rows, 1):
            value = "  |  ".join(f"{key}: {value}" for key, value in row.items())
            for part in textwrap.wrap(_printable(f"{number}. {value}"), width=105, break_long_words=True, break_on_hyphens=False):
                lines.append((part, False))
    lines.extend([("", False), ("Interpretação do Gemini", True)])
    for raw in report.splitlines():
        line = raw.strip()
        if re.fullmatch(r"\|?[\s:|-]+\|?", line):
            continue
        heading = line.startswith("#")
        line = line.lstrip("# ") if heading else line
        line = line.replace("**", "").replace("`", "")
        if line.startswith("|"):
            line = " | ".join(part.strip() for part in line.strip("|").split("|"))
        if not line:
            lines.append(("", False))
        else:
            lines.extend((part, heading) for part in textwrap.wrap(_printable(line), width=105, break_long_words=True, break_on_hyphens=False))
    return lines


def create_pdf(title: str, sections: list[tuple[str, list[dict[str, object]]]], report: str) -> bytes:
    """Create landscape A4 pages with all tabulated data and Gemini text."""
    lines = _make_lines(title, sections, report)
    page_streams: list[bytes] = []
    commands: list[bytes] = []
    y = TOP

    def finish_page() -> None:
        page_number = len(page_streams) + 1
        footer = f"TestingStudio Web | CAD0001                                      Página {page_number}"
        commands.append(b"BT /F1 8 Tf 0.40 0.46 0.54 rg 42 24 Td (" + _pdf_string(footer) + b") Tj ET")
        page_streams.append(b"\n".join(commands) + b"\n")

    for value, heading in lines:
        if y < BOTTOM:
            finish_page()
            commands = []
            y = TOP
        if not value:
            y -= LINE_HEIGHT // 2
            continue
        font = b"F2" if heading else b"F1"
        size = 11 if heading else 9
        color = b"0.09 0.20 0.34" if heading else b"0.15 0.18 0.23"
        commands.append(
            b"BT /" + font + b" " + str(size).encode() + b" Tf " + color + b" rg "
            + str(LEFT).encode() + b" " + str(y).encode() + b" Td ("
            + _pdf_string(value) + b") Tj ET"
        )
        y -= LINE_HEIGHT + (3 if heading else 0)
    finish_page()

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",  # Pages object is filled after content/page object numbers are known.
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    page_refs = []
    for stream in page_streams:
        page_id = len(objects) + 1
        content_id = page_id + 1
        page_refs.append(f"{page_id} 0 R".encode())
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] "
            b"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
            + b"/Contents " + str(content_id).encode() + b" 0 R >>"
        )
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream")
    objects[1] = b"<< /Type /Pages /Kids [" + b" ".join(page_refs) + b"] /Count " + str(len(page_refs)).encode() + b" >>"

    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(document))
        document.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(document)
    document.extend(f"xref\n0 {len(offsets)}\n".encode())
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode())
    document.extend(b"trailer\n<< /Size " + str(len(offsets)).encode() + b" /Root 1 0 R >>\n")
    document.extend(b"startxref\n" + str(xref).encode() + b"\n%%EOF\n")
    return bytes(document)
