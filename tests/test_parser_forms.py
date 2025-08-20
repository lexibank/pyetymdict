import pytest


from pyetymdict.parser.forms import *


@pytest.mark.parametrize(
    'form,graphemes',
    [
        ('a', ['a']),
        ('ā', ['ā']),
        ('ʱa', ['ʱa']),
        ('aʱa', ['a', 'ʱa']),
    ]
)
def test_iter_graphemes(form, graphemes):
    assert list(iter_graphemes(form)) == graphemes
