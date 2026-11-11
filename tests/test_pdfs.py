from pipeline.pdfs import extract_pdf_text
from tests.helpers import make_pdf

BODY = [
    "Bank A Credit Strategy, 4 March 2026",
    "We remain overweight European investment grade credit versus US.",
    "Spreads have tightened 12bp since January on lower supply and strong inflows.",
    "Our year-end target for the iTraxx Main index is 55bp, from 61bp today.",
]


def write(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_text_extracted_from_every_page(tmp_path):
    p = write(tmp_path, "note.pdf", make_pdf([BODY, ["Page two: risks include a US slowdown"] + BODY]))
    text, warning = extract_pdf_text(p)
    assert warning is None
    assert "Bank A Credit Strategy, 4 March 2026" in text
    assert "Page two: risks include a US slowdown" in text
    assert text.index("Bank A") < text.index("Page two")


def test_near_empty_pdf_returns_warning(tmp_path):
    p = write(tmp_path, "scan.pdf", make_pdf([["Fig 1"], []]))
    text, warning = extract_pdf_text(p)
    assert text == "Fig 1"
    assert warning is not None and "scan.pdf" in warning and "little or no text" in warning


def test_broken_pdf_returns_warning_not_crash(tmp_path):
    p = write(tmp_path, "broken.pdf", b"%PDF-1.4\nthis is not really a pdf")
    text, warning = extract_pdf_text(p)
    assert text == ""
    assert warning is not None and "broken.pdf" in warning and "could not read" in warning


def test_non_pdf_bytes_return_warning(tmp_path):
    p = write(tmp_path, "fake.pdf", b"PK\x03\x04 zip bytes")
    _, warning = extract_pdf_text(p)
    assert warning is not None


def test_truncated_pdf_returns_warning_or_partial_text(tmp_path):
    data = make_pdf([BODY])
    p = write(tmp_path, "cut.pdf", data[: len(data) // 2])
    text, warning = extract_pdf_text(p)
    assert warning is not None or "Bank A" in text
