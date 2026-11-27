"""Parser acceptance and invalid input cases."""

import pytest

from app.services.answer_parser import AnswerError, parse_answers, parse_key


@pytest.mark.parametrize("separator", [",", ", ", " , ", ",\n"])
def test_thirty_question_key(separator):
    """All thirty keys normalize identically with optional whitespace."""
    expected = {str(i): "abcd"[(i - 1) % 4] for i in range(1, 31)}
    text = separator.join(f"{number}{answer.upper()}" for number, answer in expected.items())
    assert parse_key(text, 30).answers == expected


@pytest.mark.parametrize("text", ["ab", "1a 2b", "1a2b", "1a;2b", "1a,,2b", "1a,2b,", ",1a,2b"])
def test_key_shares_formats(text):
    assert parse_key(text, 2) == parse_answers(text, 2)


@pytest.mark.parametrize("text", ["1a,1b", "1a,3b", "1a,2e", "0a,2b"])
def test_key_validation(text):
    with pytest.raises(AnswerError):
        parse_key(text, 2)


@pytest.mark.parametrize(
    "text",
    [
        "4829 1a,2b,3d,4a",
        "4829\n1a 2b 3d 4a",
        "4829 1-a, 2-b, 3-d, 4-a",
        "4829 abda",
        "1a,2b,3d,4a 4829",
        "4829 ABDA",
        "abda",
        "1a2b3d4a",
    ],
)
def test_formats(text):
    parsed = parse_answers(text, 4)
    assert parsed.answers == {"1": "a", "2": "b", "3": "d", "4": "a"}
    assert parsed.code in ("4829", None)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "4829",
        "4829 1a 1b",
        "4829 1f",
        "4829 1a trash 2b",
        "4829 a!b",
        "4829 0a 1b",
        "1a,2b 4829 garbage",
    ],
)
def test_invalid(text):
    with pytest.raises(AnswerError):
        parse_answers(text, 2)


def test_missing_and_extra():
    with pytest.raises(AnswerError) as error:
        parse_answers("1a 3b", 2)
    assert "2" in str(error.value) and "3" in str(error.value)


def test_e_variant():
    with pytest.raises(AnswerError, match="a, b, c, d"):
        parse_answers("3e", 3)


@pytest.mark.parametrize("text", ["4829 1a 2b 3d", "1a,2b,3d 4829", "4829\n1a\n2b\n3d"])
def test_numeric_code(text):
    assert parse_answers(text, 3).code == "4829"


@pytest.mark.parametrize(
    "text", ["A123 ab", "0999 ab", "4829 1234 ab", "4829", " ", "1a 1b", "1a 4d"]
)
def test_numeric_edges(text):
    with pytest.raises(AnswerError):
        parse_answers(text, 2)


def test_question_twelve_is_not_code():
    assert parse_answers("1234 12a").answers == {"12": "a"}
    assert parse_answers("12a").code is None


def test_missing_numbers():
    with pytest.raises(AnswerError, match="5"):
        parse_answers("4829 abcd", 5)
