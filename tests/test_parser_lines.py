import pytest

from pyetymdict.parser.lines import *


@pytest.mark.parametrize(
    'i,o',
    [
        (['First  ', '  Second'], lambda s: s == 'First Second'),
        (['Figure 1: Cap'], lambda s: 'fig-1-1' in s and 'Cap]' in s),
    ]
)
def test_make_paragraph(i, o, tmp_path):
    tmp_path.joinpath('vol1', 'maps').mkdir(parents=True)
    tmp_path.joinpath('vol1', 'maps', 'fig_1.png').write_text('t')
    assert o(make_paragraph(i, tmp_path / 'vol1'))


def test_iter_chapters(tmp_path):
    chapters = list(iter_chapters("""\

1 Chapter

merge
lines

__blockquote__
First quote

|  Second quote

__ul__
x
y

__block__
- a
- b

1.1 Section

__tablenh__
a | b | c

1.1.1 Subsection[1]

[1] A footnote

1.1.1.1 Subsubsection

__pre__
stuff

1.1.1.1.1 Subsubsubsection

: Table 1 below

__table__
 1 | 2 | 3

item
: definition

2 Next chapter


""".split('\n'), tmp_path))
    inchapter, text, toc = chapters[0]
    assert inchapter
    assert 'merge lines' in text, 'Lines in regular parapgraph not concatenated'
    assert '## 1. Section' in text
    assert '### 1.1. Subsection' in text
    assert '## Notes' in text
    assert "|:----|:----|:----|" in text
    assert "```" in text
    assert 'item\n: definition' in text
    assert '- a\n- b' in text
    assert '- x\n- y' in text, '__ul__ not handled properly'
    assert '> First quote' in text
    assert '> Second quote' in text
    assert 'table-1' in text, 'Table caption not recognized'
