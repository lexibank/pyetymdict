import re

import pytest

from pyetymdict.parser.kinship import PATTERN, TERM


@pytest.mark.parametrize(
    'text',
    [
        'M',
        'oM',
        'ysM',
        '{ysM}B',
        '{{ysM}B}F',
        '(♂?)B'
    ]
)
def test_TERM(text):
    assert re.compile(TERM).fullmatch(text)


@pytest.mark.parametrize(
    'text',
    [
        'A',
        'Mo',
    ]
)
def test_not_TERM(text):
    assert not re.compile(TERM).fullmatch(text)


@pytest.mark.parametrize(
    'text',
    [
        '’, (ADDR)',
        '’, etc',
        '’, M etc',
        '’, F, M etc',
    ]
)
def test_PATTERN(text):
    assert PATTERN.fullmatch(text)
