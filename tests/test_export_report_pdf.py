import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from export_report_pdf import build_pdf, LINES_PER_PAGE  # noqa: E402


def _xref_offsets(pdf: bytes) -> list[int]:
    startxref = pdf.rindex(b"startxref")
    xref_offset = int(pdf[startxref:].split(b"\n")[1])
    body = pdf[xref_offset:]
    lines = body.split(b"\n")
    assert lines[0] == b"xref"
    count = int(lines[1].split()[1])
    offsets = []
    for line in lines[2:2 + count]:
        offsets.append(int(line[:10]))
    return offsets


class PdfStructureTests(unittest.TestCase):
    def test_header_and_trailer(self):
        pdf = build_pdf("A short report.\n")

        self.assertTrue(pdf.startswith(b"%PDF-1.4\n"))
        self.assertTrue(pdf.rstrip(b"\n").endswith(b"%%EOF"))

    def test_xref_offsets_point_to_real_objects(self):
        pdf = build_pdf("Line one.\nLine two.\n")
        offsets = _xref_offsets(pdf)

        self.assertEqual(offsets[0], 0)  # free-list head, per spec
        for index, offset in enumerate(offsets[1:], start=1):
            marker = f"{index} 0 obj".encode("ascii")
            self.assertEqual(
                pdf[offset:offset + len(marker)], marker,
                f"object {index}'s xref offset does not point at its own header",
            )

    def test_single_short_page_produces_one_page_object(self):
        pdf = build_pdf("One line.\n")

        self.assertIn(b"/Count 1", pdf)

    def test_long_report_is_paginated(self):
        long_text = "\n".join(f"Line {i}" for i in range(LINES_PER_PAGE * 3))
        pdf = build_pdf(long_text)

        match = re.search(rb"/Count (\d+)", pdf)
        self.assertGreaterEqual(int(match.group(1)), 3)

    def test_rejects_characters_outside_the_font_encoding(self):
        with self.assertRaisesRegex(ValueError, "not representable"):
            build_pdf("Report with an unsupported glyph: \U0001F600")

    def test_em_dash_is_representable(self):
        # review_case.py's hypothesis lines use an em dash (U+2014).
        pdf = build_pdf("mechanism — prediction")
        self.assertIn(bytes([0x97]), pdf)  # em dash in WinAnsiEncoding/cp1252


@unittest.skipUnless(shutil.which("pdftotext"), "pdftotext not installed")
class PdfContentRoundTripTests(unittest.TestCase):
    def test_pdftotext_recovers_the_original_lines(self):
        text = "Case \"case-001\"\nSHA-256 deadbeef\nmechanism — prediction\n"
        pdf = build_pdf(text)

        with subprocess.Popen(
            ["pdftotext", "-", "-"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        ) as process:
            extracted, _ = process.communicate(pdf)

        decoded = extracted.decode("utf-8")
        self.assertIn('Case "case-001"', decoded)
        self.assertIn("SHA-256 deadbeef", decoded)
        self.assertIn("mechanism — prediction", decoded)


@unittest.skipUnless(shutil.which("gs"), "ghostscript not installed")
class PdfGhostscriptValidationTests(unittest.TestCase):
    def test_ghostscript_accepts_a_multi_page_report(self):
        long_text = "\n".join(f"Line {i}" for i in range(LINES_PER_PAGE * 2))
        pdf = build_pdf(long_text)

        result = subprocess.run(
            ["gs", "-dNOPAUSE", "-dBATCH", "-sDEVICE=nullpage", "-q", "-"],
            input=pdf, capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))


if __name__ == "__main__":
    unittest.main()
