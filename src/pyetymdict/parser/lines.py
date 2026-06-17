"""
Parse line- or paragraph-level markup.

Some of the functionlity in this module requires a Parser instance, which will typically be passed
as first argument. So, in a sense, this module provides methods for a Parser.
"""
import itertools
from collections.abc import Generator, Iterable, Sequence
import dataclasses
from typing import Union, Optional

from tabulate import tabulate

from .spec import (
    FOOTNOTE_PATTERN, CF_LINE_PREFIX, BlockParseSpec, VolumeDir, Parser,
    CHAPTER_HEADER_PATTERN, SECTION_HEADER_PATTERN, SUBSECTION_HEADER_PATTERN, H4_PATTERN,
    H5_PATTERN, TABLE_KEYWORD, TABLE_NOHEAD_KEYWORD,
    BLOCK_KEYWORD, BLOCKQUOTE_KEYWORD, PREFORMATTED_KEYWORD, UL_KEYWORD, FORMGROUP_KEYWORD,
    is_figure, is_pagenumber)
from .util import cldf_media_link

CfGroupType = tuple[str, list[str]]  # A group "name" (often just "cf. also") and the list of lines.
HeaderType = tuple[Union[int, str], str]
TocItemType = tuple[int, str, str]  # Level, id, text.


def formblock(parser: Parser, lines: Iterable[str]) -> tuple[list[str], list[CfGroupType]]:
    """Partitions lines into a list of regular form lines and an optional list of cf-groups."""
    reg, cfs = [], []
    in_cf, cf, cfspec = False, [], None

    for line in itertools.dropwhile(lambda l: not l, lines):
        assert parser.is_forms_line(line), line
        if line.strip().startswith(CF_LINE_PREFIX):
            in_cf = True
            if cf:  # There's already a previous cf block.
                cfs.append((cfspec, cf))
            cf = []
            cfspec = line.replace(CF_LINE_PREFIX, '').strip().lstrip(':').strip()
            continue
        if in_cf:
            cf.append(line)
        else:
            reg.append(line)
    if cf:
        cfs.append((cfspec, cf))
    return reg, cfs


def make_paragraph(lines: Sequence[str], voldir: VolumeDir) -> str:  # pylint: disable=R0911
    """
    Our parser understands some sort of paragraph markup.
    Paragraphs are contiguous, non-empty lines.

    In particular:
    - A paragraph of lines all starting with "|" is interpreted as blockquote and
    - so are lines following a line "__blockquote__".
    - A paragraph with first line "__formgroup__" is interpreted as form group.
    - A paragraph with first line "__ul__" is interpreted as unordered list where each line is one
      item.
    - A paragraph with first line "__block__" is interpreted as list of newline-separated lines.
    - A paragraph with first line "__pre__" is interpreted as preformatted text.
    - A paragraph with first line "__table__" is interpreted as list of header and table rows.
    - A paragraph with first line "__tablenh__" is interpreted as list of table rows.
    - A paragraph starting with "Map|Figure [0-9]+[a-z]:" is interpreted as figure and converted
      to CLDF Markdown link referencing the corresponding file in MediaTable.
    - A paragraph where the second line starts with ":" is interpreted as definition list.
    - Otherwise the lines are interpreted as contiguous text and returned concatenated.
    """
    if lines[0].startswith('|'):
        return f"> {' '.join(line.lstrip('|').strip() for line in lines)}"
    if lines[0] == BLOCKQUOTE_KEYWORD:
        return f"> {' '.join(line.strip() for line in lines[1:])}"
    if lines[0] == FORMGROUP_KEYWORD:
        return '\n'.join('' if line.strip() == '#' else line for line in lines[1:])
    if lines[0] == UL_KEYWORD:
        return '\n'.join(f'- {line.strip()}' for line in lines[1:])
    if lines[0] == BLOCK_KEYWORD:
        return '\n'.join('' if line.strip() == '#' else line for line in lines[1:])
    if len(lines) > 1 and lines[1].strip().startswith(':'):
        # A definition list
        return '\n'.join(lines)
    if lines[0] == PREFORMATTED_KEYWORD:
        return "```\n{}\n```".format('\n'.join(lines[1:]))
    if lines[0] == TABLE_KEYWORD:
        return tabulate(
            [[s.strip() or ' ' for s in ln.split('|')] for ln in lines[2:]],
            headers=[s.strip() or ' ' for s in lines[1].split('|')],
            tablefmt='pipe')
    if lines[0] == TABLE_NOHEAD_KEYWORD:
        return tabulate(
            [[s.strip() or ' ' for s in ln.split('|')] for ln in lines[1:]],
            headers=[' '] * len(lines[1].split('|')),
            tablefmt='pipe')
    res = is_figure(lines)
    if res:  # Turn figures and maps into CLDF Markdown links referencing MediaTable items.
        if res[0] == 'tab':
            return (f'<a id="{voldir.figure_id(voldir.number, res[0], res[1])}"> </a>\n\n'
                    + '\n'.join(lines))
        fid = voldir.id_for_figure(res[0], res[1])
        if fid:
            label, _, caption = ' '.join(ln.lstrip(':').strip() for ln in lines).partition(':')
            label = f'__{label}:__ {caption.strip()}'
            return f'<a id="{fid}"> </a>\n\n{cldf_media_link(fid, label=label)}\n\n'
    return ' '.join(ln.strip() for ln in lines)


def make_chapter(paras: Iterable[str]) -> str:
    """
    Turns a bunch of paragraph into a chapter, moving footnotes to endnotes.

    If the first line of a paragraph starts with footnote pattern, it's the footnote content.
    """
    def repl(m):
        return f"[^{m.group('fn')}]:"

    regular, endnotes = [], []
    for para in paras:
        if FOOTNOTE_PATTERN.match(para):
            endnotes.append(FOOTNOTE_PATTERN.sub(repl, para, count=1))
        else:
            regular.append(FOOTNOTE_PATTERN.sub(repl, para))
    if endnotes:
        return '\n\n'.join(regular + ['\n## Notes'] + endnotes)
    return '\n\n'.join(regular)


def match_header_or_pageno(line: str, chapter: list[str], toc: list[TocItemType]) -> bool:
    """
    Check whether line is a header line, and if so update the relevant items.
    """
    from .forms import strip_footnote_reference  # pylint: disable=C0415

    pageno = is_pagenumber(line)
    if pageno:  # Page number line.
        chapter.append(f'\n<a id="p-{pageno}"></a>')
        return True

    for level, pattern, link_format, number_format in [
        (1, SECTION_HEADER_PATTERN, 's-{b}', '{b}.'),
        (2, SUBSECTION_HEADER_PATTERN, 's-{b}-{c}', '{b}.{c}.'),
        (3, H4_PATTERN, 's-{b}-{c}-{d}', '{b}.{c}.{d}.'),
        (4, H5_PATTERN, None, '{b}.{c}.{d}.{e}.'),
    ]:
        m = pattern.match(line)
        if m:
            number = number_format.format(**m.groupdict())
            title = '{title}'.format(**m.groupdict())  # pylint: disable=C0209
            levelmark = (level + 1) * '#'
            if link_format:
                link = link_format.format(**m.groupdict())
                chapter.append(f'\n<a id="{link}"></a>\n\n{levelmark} {number} {title}\n')
                toc.append((level, link, strip_footnote_reference(title)[0]))
            else:
                chapter.append(f"\n{levelmark} {number} {title}\n")
            return True
    return False


def iter_chapters(
        lines: Iterable[str],
        voldir: VolumeDir,
) -> Generator[tuple[Union[str, None], str, list[TocItemType]], None, None]:
    """
    Partitions lines into chapters.

    Note: We discard every line before the first chapter - unless no chapters are found at all.
    """
    before_chapter, chapter, toc, para = [], [], [], []
    in_chapter: Union[str, None] = None
    for line in lines:
        m = CHAPTER_HEADER_PATTERN.match(line)
        if m:
            if in_chapter:  # Yield the previous chapter and initialize a new one.
                yield in_chapter, make_chapter(chapter), toc
            chapter, toc, in_chapter = [], [], m.group('a')
            continue

        if match_header_or_pageno(line, chapter if in_chapter else before_chapter, toc):
            continue

        if not line.strip():  # An empty line ends a paragraph.
            if para:
                (chapter if in_chapter else before_chapter).append(make_paragraph(para, voldir))
                para = []
        else:
            para.append(line)

    if para:
        (chapter if in_chapter else before_chapter).append(make_paragraph(para, voldir))
    yield in_chapter, make_chapter(chapter if in_chapter else before_chapter), toc


@dataclasses.dataclass
class CurrentHeader:
    """A small state machine to keep track of sections in a list of text lines."""
    h1: Optional[HeaderType] = None
    h2: Optional[HeaderType] = None
    h3: Optional[HeaderType] = None

    def match(self, line: str):
        """
        Looks for header patterns in line and updates the state accordingly.
        """
        m = CHAPTER_HEADER_PATTERN.match(line)
        if m:
            self.h1 = (m.group('a'), m.group('title'))
            self.h2, self.h3 = None, None
            return
        m = SECTION_HEADER_PATTERN.match(line)
        if m:
            assert self.h1, line
            assert m.group('a') == self.h1[0], (line, self.h1)
            self.h2 = (m.group('b'), m.group('title'))
            self.h3 = None
            return
        m = SUBSECTION_HEADER_PATTERN.match(line)
        if m:
            assert self.h2 and m.group('b') == self.h2[0], line
            self.h3 = (m.group('c'), m.group('title'))
        return


@dataclasses.dataclass(frozen=True)
class Block:
    """
    A block is a list of lines extracted from a section of a text.
    """
    type: str
    lines: list[str]
    chapter: Optional[HeaderType] = None
    section: Optional[HeaderType] = None
    subsection: Optional[HeaderType] = None
    pagenumber: Optional[Union[int, str]] = None


def extract_blocks(block_spec: BlockParseSpec, lines) -> Generator[Block, str, list[str]]:
    """
    Extract marked up blocks.

    When the function yields a block, it expects to be sent a unique block ID to insert as reference
    in the text.
    """
    pageno = -1
    block = []
    current = CurrentHeader()
    in_block = False

    new_lines = []
    for i, line in enumerate(lines, start=1):
        m = is_pagenumber(line)
        if m:  # Page number line.
            pageno = int(m)
            assert not in_block, pageno
            new_lines.append(line)
            continue

        if line == block_spec.start:
            assert not in_block, i
            in_block = True
            block = []
            continue

        # Implicit or explicit end of block:
        if (not line and (not block_spec.end) and in_block) \
                or (block_spec.end and line == block_spec.end):
            assert block, i
            block_id = yield Block(
                block_spec.name,
                block,
                current.h1,
                current.h2,
                current.h3,
                None if pageno == -1 else pageno)
            in_block = False
            new_lines.append(block_id)
            if not line:
                new_lines.append('')
            continue

        if not in_block:
            current.match(line)
            new_lines.append(line)
        else:
            block.append(line)
    return new_lines
