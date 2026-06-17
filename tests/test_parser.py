import re

import pytest

from pyetymdict.parser.forms import *
from pyetymdict.parser.spec import BLOCKS
from pyetymdict.parser.lines import extract_blocks, formblock


@pytest.mark.parametrize(
    'i,o',
    [
        ('[3] stuff', ('stuff', '3', 'start')),
        ('[a] stuff', ('[a] stuff', None, None)),
    ]
)
def test_strip_footnote_reference(i, o):
    assert strip_footnote_reference(i) == o


@pytest.mark.parametrize(
    's,r',
    [
        ("[1] 'gloss'", lambda g: g.fn == '1'),
        ("[A.B] 'gloss'", lambda g: g.morpheme_gloss == 'A.B'),
        ("'gloss' [7]", lambda g: g.fn == '7'),
        ("(V) 'gloss'", lambda g: g.pos == 'V'),
        ("(?) 'gloss'", lambda g: g.uncertain is True),
    ]
)
def test_iter_glosses(s, r):
    g = next(iter_glosses(s, re.compile(r'\((?P<pos>V)\)')))
    assert r(g)


def test_iter_glosses_multiple():
    assert len(list(iter_glosses("'a'; 'b'; 'c' ('x'; y)", re.compile(r'\(?P<pos>V\)')))) == 3


def test_iter_etyma(parser):
    lines = """
1 H1
1.1 H2
1.1.1 H3

\x0c                                        Architecturalforms and settlement patterns              49

<
PMP (N) *balay 'open-sided building'
POc *pale 'open-sided building'
 Adm: Mussau             ale               'house'
 cf. also: loans
 NNG: Bebeli             bele              'house'
>

"""
    etymon = list(extract_blocks(BLOCKS['etymon'], lines.split('\n')))[0]
    assert etymon.pagenumber == 49
    assert etymon.chapter == ('1', 'H1')
    assert etymon.section == ('1', 'H2')
    assert etymon.subsection == ('1', 'H3')

    forms, cfs = formblock(parser, etymon.lines)
    assert len(forms) == 3
    assert cfs and cfs[0][0] == 'loans' and len(cfs[0][1]) == 1

    gen = extract_blocks(BLOCKS['etymon'], lines.split('\n'))
    next(gen)
    while True:
        try:  # Send the proto-language of the first reconstruction into the generator.
            gen.send('xyz')
        except StopIteration as e:
            text = e.value
            break
    assert 'xyz' in text[4:]
