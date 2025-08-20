import pytest

from pyetymdict.parser.util import variants, strip_morphemeseparator, nested_toc


@pytest.mark.parametrize(
    'form,res',
    [
        ('', ''),
        ('-', '-'),
        ('--', '--'),
        ('-a', '-a'),
        ('b-', 'b-'),
        ('-b-', '-b-'),
        ('a-b', 'ab'),
    ]
)
def test_strip_morphemeseparator(form, res):
    assert strip_morphemeseparator(form) == res


@pytest.mark.parametrize(
    'form,var',
    [
        ('', []),
        ('a', ['a']),
        ('(x)', ['', 'x']),
        ('a(x)', ['a', 'ax']),
        ('a(x,y)', ['ax', 'ay']),
        ('a((x,y))', ['a', 'ax', 'ay']),
        ('a[x,y]', ['ax', 'ay']),
        ('a(x)b(y)', ['ab', 'axb', 'aby', 'axby']),
        (
            '((r,l)(a,u))mo(g,k)o',
            ['ramogo', 'ramoko', 'rumogo', 'rumoko', 'lamogo', 'lamoko', 'lumogo', 'lumoko']),
    ]
)
def test_variants(form, var):
    assert set(variants(form)) == set(var)


@pytest.mark.parametrize(
    'items,nested',
    [
        ([], []),
        ([(1, 's-1', 'A')], [['s-1', 'A', []]]),
        ([(1, 's-1', 'A'), (1, 's-2', 'B')], [['s-1', 'A', []], ['s-2', 'B', []]]),
        ([(1, 's-1', 'A'), (2, 's-1-2', 'B')], [['s-1', 'A', [['s-1-2', 'B', []]]]]),
    ]
)
def test_nested_toc(items, nested):
    assert nested_toc(items) == nested