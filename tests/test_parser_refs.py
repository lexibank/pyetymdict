import pytest

from pyetymdict.parser.refs import *


def search(s, *keys, **kw):
    for key in keys:
        for m in key_to_regex(key, **kw).finditer(s):
            yield key, m.string[m.start():m.end()], m.groupdict()


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
    assert groups['qualifier'] == 'after'
    assert groups['pages'] == '7-10'

    matches = list(search('(Milke 1968: *paRaRa)', 'Milke 1968', in_text=False))
    _, _, groups = matches[0]
    assert groups['pages'] == '*paRaRa'


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


@pytest.mark.parametrize(
    'text,expected',
    [
        (
        "See Chapter 9, §§7-8.",
    'See [Ch. 9](#cldf:1-9) §§[7](?anchor=s-7#cldf:1-9)-[8](?anchor=s-8#cldf:1-9).',
        ),
        (
        "in §§3.3.1–3.3.2. As",
    "in §§[3.3.1](?anchor=s-3-3-1#cldf:1-1)-[3.3.2](?anchor=s-3-3-2#cldf:1-1). As",
        ),
        (
        " vol.1, ch.2, §§3 .1.2-3) but",
    " [Vol. 1, ch. 2](#cldf:1-2) §§[3.1.2](?anchor=s-3-1-2#cldf:1-2)-[3.1.3](?anchor=s-3-1-3#cldf:1-2)) but",
        ),
   ]
)
def test_replace_cross_refs(text, expected):
    assert expected == replace_cross_refs(text, '1', '1', {}).replace('ContributionTable', '')
