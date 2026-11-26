"""Telegram preview size and document error behavior."""

from io import BytesIO

import pymupdf
import pytest
from PIL import Image

from app.services.pdf_service import PDFError, preview, render_preview


@pytest.mark.parametrize("pages", [1, 2, 3])
def test_pdf(tmp_path, pages):
    path = tmp_path / "sample.pdf"
    with pymupdf.open() as doc:
        for _ in range(pages):
            doc.new_page().insert_text((40, 40), "Sample test")
        doc.save(path)
    result = render_preview(path)
    image = Image.open(BytesIO(result))
    assert image.format == "JPEG"
    assert image.width <= 1600 and sum(image.size) <= 10000
    assert max(image.size) / min(image.size) <= 20
    assert len(result) <= 10_000_000


def test_invalid(tmp_path):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"not pdf")
    with pytest.raises(PDFError):
        render_preview(path)
    with pytest.raises(PDFError):
        render_preview(tmp_path / "missing.pdf")


def test_password(tmp_path):
    path = tmp_path / "protected.pdf"
    with pymupdf.open() as doc:
        doc.new_page()
        doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
    with pytest.raises(PDFError):
        render_preview(path)


async def test_async(tmp_path):
    path = tmp_path / "one.pdf"
    with pymupdf.open() as doc:
        doc.new_page()
        doc.save(path)
    assert await preview(path)
