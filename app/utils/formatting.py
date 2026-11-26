"""Telegram-safe text sizing helpers."""
from collections.abc import Iterator


def chunks(value: str,limit: int=3500) -> Iterator[str]:
    """Split text into UTF-16 bounded messages without breaking Unicode."""
    buffer=[]
    size=0
    for char in value:
        width=2 if ord(char)>0xFFFF else 1
        if size+width>limit:
            yield "".join(buffer)
            buffer=[]
            size=0
        buffer.append(char)
        size+=width
    if buffer:
        yield "".join(buffer)
