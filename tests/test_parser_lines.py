import pytest

from pyetymdict.parser.lines import *


@pytest.fixture
def volume_dir(tmp_path):
    d = tmp_path / 'vol1'
    d.mkdir()
    return VolumeDir(d)


def test_extract_blocks():
    spec = BlockParseSpec('b', '<--', '-->')

    generator = extract_blocks(spec, """
1. Chap
1.1 Sec
1.1.1 Subsec

<--
stuff
-->

1.2 Sec
<--
stuff
-->
""".split('\n'))
    b = next(generator)
    assert 'stuff' in b.lines
    assert b.subsection
    n = 1
    try:
        while True:
            b = generator.send(f'obj{n}')
            assert not b.subsection
            n += 1
    except StopIteration as e:
        lines = e.value
    assert 'obj2' in lines


def test_extract_blocks_no_end():
    spec = BlockParseSpec('b', '--')

    generator = extract_blocks(spec, """
text
--
stuff

more text
--
stuff

""".split('\n'))
    next(generator)
    n = 1
    try:
        while True:
            generator.send(f'obj{n}')
            n += 1
    except StopIteration as e:
        pass
    assert n == 2


@pytest.mark.parametrize(
    'i,o',
    [
        (['First  ', '  Second'], lambda s: s == 'First Second'),
        ([':Figure 1: Cap'], lambda s: 'fig-1-1' in s and 'Cap]' in s),
    ]
)
def test_make_paragraph(i, o, volume_dir):
    volume_dir.path.joinpath('media').mkdir(parents=True)
    volume_dir.path.joinpath('media', 'fig_1.png').write_text('t')
    assert o(make_paragraph(i, volume_dir))


def test_iter_chapters_no_chapter(volume_dir):
    res = list(iter_chapters("Just text".split() + ['', 'text'], volume_dir))
    assert len(res) == 1
    assert res[0] == (None, 'Just text\n\ntext', [])


def test_iter_chapters(volume_dir):
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


""".split('\n'), volume_dir))
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
    assert 'tab-1' in text, 'Table caption not recognized'
