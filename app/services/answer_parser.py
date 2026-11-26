"""Strict answer parsing with optional test codes."""

import re
from dataclasses import dataclass

from app.constants import MAX_ANSWER_CHARS
from app.services.errors import BusinessError
from app.texts import t


class AnswerError(BusinessError):
    """User-correctable input error."""


@dataclass(frozen=True)
class ParsedAnswers:
    """Normalized answer input."""

    code: str | None
    answers: dict[str, str]


def parse_key(text: str, expected: int) -> ParsedAnswers:
    """Require comma-separated numbered keys, ignoring surrounding whitespace."""
    if not text or len(text) > MAX_ANSWER_CHARS:
        raise AnswerError(t("parse_empty"))
    if not all(re.fullmatch(r"\s*[0-9]+\s*[a-zA-Z]\s*", item) for item in text.split(",")):
        raise AnswerError(t("key_format"))
    return parse_answers(text, expected)


def parse_answers(text: str, expected: int | None = None) -> ParsedAnswers:
    """Accept compact or numbered answers and optional leading/trailing code."""
    if not text or len(text) > MAX_ANSWER_CHARS:
        raise AnswerError(t("parse_empty"))
    raw = text.strip().lower()
    code = None
    tokens = raw.split()
    code_tokens = [token for token in tokens if re.fullmatch(r"[0-9]{4}", token)]
    if len(code_tokens) > 1:
        raise AnswerError(t("parse_invalid"))
    if code_tokens:
        code = code_tokens[0]
        if int(code) < 1000:
            raise AnswerError(t("invalid_code"))
        tokens.remove(code)
    raw = " ".join(tokens).strip()
    if not raw:
        raise AnswerError(t("parse_empty"))
    answers = {}
    compact = re.sub(r"[\s,;]+", "", raw)
    if re.fullmatch(r"[a-z]+", compact):
        answers = {str(i): value for i, value in enumerate(compact, 1)}
    else:
        pattern = re.compile(r"(\d+)\s*[-.:]?\s*([a-z])", re.I)
        cursor = 0
        for match in pattern.finditer(raw):
            if raw[cursor : match.start()].strip(" ,;\t\n\r"):
                raise AnswerError(t("parse_invalid"))
            number = str(int(match[1]))
            if number in answers:
                raise AnswerError(t("parse_duplicate", number=number))
            answers[number] = match[2]
            cursor = match.end()
        if not answers or raw[cursor:].strip(" ,;\t\n\r"):
            raise AnswerError(t("parse_invalid"))
    for number, value in answers.items():
        if value not in "abcd":
            raise AnswerError(t("parse_variant", number=number, variant=value))
    if expected is not None:
        wanted = {str(i) for i in range(1, expected + 1)}
        missing, extra = wanted - answers.keys(), answers.keys() - wanted
        if missing or extra:
            raise AnswerError(
                t(
                    "parse_count",
                    expected=expected,
                    missing=",".join(sorted(missing, key=int)) or "?",
                    extra=",".join(sorted(extra, key=int)) or "?",
                )
            )
    return ParsedAnswers(code, answers)
