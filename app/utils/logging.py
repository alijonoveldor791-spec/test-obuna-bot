"""Secret-safe application logging."""

import logging
import re


class Redact(logging.Filter):
    """Remove Telegram tokens from logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = re.sub(r"\d{5,}:[A-Za-z0-9_-]{20,}", "[REDACTED]", record.getMessage())
        record.args = ()
        if record.exc_info:
            exception = logging.Formatter().formatException(record.exc_info)
            record.exc_text = re.sub(r"\d{5,}:[A-Za-z0-9_-]{20,}", "[REDACTED]", exception)
        return True


def setup_logging() -> None:
    """Configure console logging with redaction."""
    handler = logging.StreamHandler()
    handler.addFilter(Redact())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
