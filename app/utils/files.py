"""Controlled storage file names."""

from pathlib import Path
from uuid import uuid4


def pdf_destination() -> Path:
    """Generate a server-owned PDF name without trusting uploaded names."""
    directory = Path("storage/pdf")
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{uuid4().hex}.pdf"
