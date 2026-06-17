import pytest


from pyetymdict.parser.forms import *


@pytest.mark.parametrize(
    'text,position,expected',
    [
        ('stuff (comment)', 'end', ('comment', 'stuff')),
        ('(comment) stuff', 'start', ('comment', 'stuff')),
        ('stuff', 'end', (None, 'stuff')),
        ('(abc)cde', 'start', ('abc', 'cde')),
        ('( abc ) cde', 'start', ('abc', 'cde')),
        ('( (a) bc ) cde', 'start', ('(a) bc', 'cde')),
        ('cde(abc)', 'end', ('abc', 'cde')),
        ('cde((a)bc)', 'end', ('(a)bc', 'cde')),
    ]
)
def test_strip_comment(text, position, expected):
    assert expected == strip_comment(text, position)


@pytest.mark.parametrize(
    'i,o',
    [
        ("bubuŋ (Dempwolff 1938) 'ridgepole'", (["bubuŋ"], "(Dempwolff 1938) 'ridgepole'")),
        ("bubuŋ, *second 'ridgepole'", (["bubuŋ", "second"], "'ridgepole'")),
        ("bu(b,g)uŋ 'ridgepole'", (["bu(b,g)uŋ"], "'ridgepole'")),
        ("bu[b,g]uŋ 'ridgepole'", (["bu[b,g]uŋ"], "'ridgepole'")),
        ("bu⟨b⟩uŋ 'ridgepole'", (["bu⟨b⟩uŋ"], "'ridgepole'")),
        ("|bubuŋ  second| 'ridgepole'", (["bubuŋ second"], "'ridgepole'")),
        ("|pa pa|, *qa-pa ‘t’", (["pa pa", "qa-pa"], "‘t’")),
        ("|pa pa| *qa-pa ‘t’", (["pa pa", "qa-pa"], "‘t’")),
        ("p~*q ‘t’", (["p~q"], "‘t’")),
        ("pa or *qa ‘t’", (["pa", "qa"], "‘t’")),
    ]
)
def test_parse_protoform(i, o):
    assert parse_protoform(i, list('-gbubuŋpaqsecond()[]⟨⟩')) == o
