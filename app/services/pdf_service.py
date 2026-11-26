"""Bounded PDF rendering for Telegram photos."""

import asyncio
from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image

from app.constants import MAX_PHOTO_BYTES
from app.services.errors import BusinessError
from app.texts import t


class PDFError(BusinessError):
    """Unusable PDF document."""


def render_preview(pdf_path: str | Path, pages: int = 2, zoom: float = 2.0) -> bytes:
    """Render up to two PDF pages into a bounded JPEG."""
    try:
        with pymupdf.open(pdf_path) as doc:
            if doc.needs_pass:
                raise PDFError(t("pdf_encrypted"))
            if not doc.page_count:
                raise PDFError(t("pdf_invalid"))
            images = []
            for page in list(doc)[: max(1, min(pages, 2))]:
                if page.rect.width <= 0 or page.rect.height <= 0:
                    raise PDFError(t("pdf_invalid"))
                factor = min(max(zoom, 0.1), 1600 / page.rect.width, 4000 / page.rect.height)
                pix = page.get_pixmap(matrix=pymupdf.Matrix(factor, factor), alpha=False)
                images.append(Image.open(BytesIO(pix.tobytes("png"))).convert("RGB"))
            width, height = max(im.width for im in images), sum(im.height for im in images)
            canvas = Image.new("RGB", (width, height), "white")
            y = 0
            for im in images:
                canvas.paste(im, (0, y))
                y += im.height
            canvas.thumbnail((1600, 8000))
            # Telegram also limits aspect ratio to 20.
            if max(canvas.size) / min(canvas.size) > 20:
                padded = Image.new(
                    "RGB",
                    (
                        max(canvas.width, (canvas.height + 19) // 20),
                        max(canvas.height, (canvas.width + 19) // 20),
                    ),
                    "white",
                )
                padded.paste(canvas, (0, 0))
                canvas = padded
            for quality in (85, 70, 50):
                output = BytesIO()
                canvas.save(output, "JPEG", quality=quality)
                if output.tell() <= MAX_PHOTO_BYTES:
                    return output.getvalue()
            raise PDFError(t("pdf_limit"))
    except PDFError:
        raise
    except (RuntimeError, ValueError, OSError) as exc:
        raise PDFError(t("pdf_invalid")) from exc


async def preview(pdf_path: str | Path) -> bytes:
    """Move CPU-bound rendering off the event loop."""
    return await asyncio.to_thread(render_preview, pdf_path)
