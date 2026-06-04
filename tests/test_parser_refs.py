import pytest

from pyetymdict.parser.refs import *


@pytest.fixture
def source_pattern_dict():
    return {
        'meier2011': key_to_regex('Meier 2011'),
        'meier2013': key_to_regex('Meier 2013'),
        'meier201214': key_to_regex('Meier 2012–14'),
    }


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


def test_replace_source_refs(source_pattern_dict):
    res = replace_source_refs('Meier 2011, 2012–14, 2013', source_pattern_dict)
    assert 'cldf:meier201214' in res
    assert 'cldf:meier2013' in res


def test_replace_figure_refs():
    assert replace_figure_refs(':Map 1', '1') == ':Map 1', 'not a reference.'
    assert 'map-1' in replace_figure_refs('see Map 1', '1')
