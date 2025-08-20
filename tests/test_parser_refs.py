import pytest

from pyetymdict.parser.refs import *


@pytest.mark.parametrize(
    'text,num_matches',
    [
        ('Meier and Müller, eds, 1911-12', 1),
        ('Meier and Müller 1911-12', 1),
        ("Meier and Müller's 1911-12'", 1),
        ('Meier and Müller (1911-12', 1),
    ]
)
def test_search(text, num_matches):
    matches = list(search(text, 'Meier and Müller 1911-12'))
    assert len(matches) == num_matches


def test_search_single_token():
    matches = list(search('see ACD.', 'ACD'))
    assert len(matches) == 1
    assert not list(search('see ACD', 'ACD'))
    assert not list(search('seeACD.', 'ACD'))
    assert list(search('(ACD)', 'ACD', in_text=False))


def test_search_with_pages():
    matches = list(search('(after Meier 2011: 7-10)', 'Meier 2011', in_text=False))
    _, _, groups = matches[0]
    assert groups['pages'] == '7-10'


@pytest.mark.parametrize(
    'text,replacement',
    [
        (' Meier 2011 ', '[Meier 2011](Source#cldf:srcid)'),
        (' Meier (2011) ', '[Meier](Source#cldf:srcid) ([2011](Source#cldf:srcid)'),
        ('] Meier 2011 ', '[Meier 2011](Source#cldf:srcid)'),
        ('[Meier 2011 ', 'Meier 2011'),
    ]
)
def test_repl_ref(text, replacement):
    p = key_to_regex('Meier 2011')
    assert repl_ref('srcid', p.search(text)) == replacement
