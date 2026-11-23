"""Render a verified case review report as a minimal, stdlib-only PDF.

The PDF is a view of the case file, not the source of truth. The structured
case file and its seal remain the record; this only renders review_case's
plain-text report into a paginated, fixed-width PDF for human reading
outside a terminal. No PDF library is used or required.
"""

import argparse
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_case import report  # noqa: E402

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN = 50
FONT_SIZE = 10
LEADING = 12
CHAR_WIDTH = FONT_SIZE * 0.6  # Courier is a fixed-width 600/1000-em font.
MAX_CHARS_PER_LINE = int((PAGE_WIDTH - 2 * MARGIN) / CHAR_WIDTH)
LINES_PER_PAGE = int((PAGE_HEIGHT - 2 * MARGIN) / LEADING) - 1
FOOTER = "This PDF is a view of the sealed case file, not the source of truth."


def _wrap(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        indent = raw_line[: len(raw_line) - len(raw_line.lstrip(" "))]
        wrapped = textwrap.wrap(
            raw_line, width=MAX_CHARS_PER_LINE,
            subsequent_indent=indent, initial_indent="",
            break_long_words=True, break_on_hyphens=False,
        )
        lines.extend(wrapped or [""])
    return lines


def _paginate(lines: list[str]) -> list[list[str]]:
    body_lines_per_page = LINES_PER_PAGE - 2  # reserve space for the footer
    pages = [lines[i:i + body_lines_per_page] for i in range(0, len(lines), body_lines_per_page)]
    return pages or [[]]


def _escape(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    try:
        return escaped.encode("cp1252")
    except UnicodeEncodeError as error:
        raise ValueError(f"report text is not representable in the PDF font encoding: {error}") from error


def _content_stream(lines: list[str]) -> bytes:
    top = PAGE_HEIGHT - MARGIN
    stream = bytearray(f"BT\n/F1 {FONT_SIZE} Tf\n{LEADING} TL\n{MARGIN} {top} Td\n".encode("ascii"))
    for line in lines:
        stream += b"(" + _escape(line) + b") Tj\nT*\n"
    stream += b"(" + _escape(FOOTER) + b") Tj\nET"
    return bytes(stream)


def build_pdf(text: str) -> bytes:
    """Render plain text as a minimal, paginated, Courier-font PDF."""

    pages = _paginate(_wrap(text))
    objects: list[bytes] = []

    font_obj_num = 3
    page_obj_nums = [font_obj_num + 1 + 2 * i for i in range(len(pages))]
    content_obj_nums = [n + 1 for n in page_obj_nums]

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{n} 0 R" for n in page_obj_nums)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"))
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>"
    )

    for page_num, content_num, lines in zip(page_obj_nums, content_obj_nums, pages):
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {font_obj_num} 0 R >> >> "
                f"/Contents {content_num} 0 R >>"
            ).encode("ascii")
        )
        stream = _content_stream(lines)
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream"
        )

    buffer = bytearray(b"%PDF-1.4\n")
    offsets = [0]  # object 0 is the free-list head, never written as a real object
    for index, body in enumerate(objects, start=1):
        offsets.append(len(buffer))
        buffer += f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n"

    xref_offset = len(buffer)
    buffer += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    buffer += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        buffer += f"{offset:010d} 00000 n \n".encode("ascii")
    buffer += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode("ascii")
    return bytes(buffer)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv[1:])
    try:
        text = report(args.case.read_bytes())
        pdf = build_pdf(text)
    except (ValueError, OSError, TypeError, KeyError, AttributeError) as error:
        parser.exit(1, f"Cannot render case: {ascii(str(error))}\n")
        return 1
    args.output.write_bytes(pdf)
    print(f"Wrote a view of the case (not the source of truth) to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
