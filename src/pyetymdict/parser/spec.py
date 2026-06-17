"""
The specification of the plain text format understood by `pyetymdict`.
"""
import re
import pathlib
import functools
import collections
from collections.abc import Sequence, Generator, Container, Iterable
import dataclasses
from typing import Literal, Optional, Any, get_args

from pycldf import Source
from pycldf.ext.markdown import CLDFMarkdownLink
from clldutils import jsonlib

from . import kinship
from .util import re_choice
from ..languoids import Languoids

ParagraphType = Sequence[str]  # A list of non-empty lines.
FigureRefType = Literal['Map', 'Table', 'Figure']
FigureTypeType = Literal['map', 'fig', 'tab']
LanguageIdType = str
ChapterNumberType = str

FOOTNOTE_PATTERN = re.compile(r'\[(?P<fn>[0-9]+)]')  # [2]
CF_LINE_PREFIX = 'cf. also'  # Identifies the start of form group, appended to an etymon.

#
# Detecting headers
#
CHAPTER_HEADER_PATTERN = re.compile(  # Identifies chapter headers: 1. Title
    r'(?P<a>\d+)\.?\s+(?P<title>([_‘♂])?[A-Z].+)')
SECTION_HEADER_PATTERN = re.compile(  # Identifies section headers: 1.2. Title
    r'(?P<a>\d+)(\.|\s)\s*(?P<b>\d+)\.?\s+(?P<title>([_‘♂])?[A-Z].+)')
SUBSECTION_HEADER_PATTERN = re.compile(  # Identifies subsection headers: 1.2.3. Title
    r'(?P<a>\d+)(\.|\s)\s*(?P<b>\d+)(\.|\s)\s*(?P<c>\d+)\.?\s+(?P<title>([_‘♂])?[*mA-Z].+)')
H4_PATTERN = re.compile(
    r'(?P<a>\d+)(\.|\s)\s*(?P<b>\d+)(\.|\s)\s*(?P<c>\d+)(\.|\s)\s*(?P<d>\d+)\.?\s+'
    r'(?P<title>([_‘♂])?[*A-Z].+)')
H5_PATTERN = re.compile(
    r'(?P<a>\d+)(\.|\s)\s*(?P<b>\d+)(\.|\s)\s*(?P<c>\d+)(\.|\s)\s*(?P<d>\d+)(\.|\s)\s*'
    r'(?P<e>\d+)\.?\s+(?P<title>([_‘♂])?[*A-Z].+)')

#
# Page numbers
#
# A line starting with \x0c (form-feed) ...
# ... and ending with a number or ...
PAGENUMBER_RIGHT_PATTERN = re.compile(r'(\x0c|###newpage###)\s+\D+(?P<no>\d+)')
# ... immediately followed by a number.
PAGENUMBER_LEFT_PATTERN = re.compile(r'(\x0c|###newpage###)(?P<no>\d+)\s+\D+')

#
# Figures, Maps, Tables
#
_FIGURE_REGEX = r'(?P<type>{})\s+(?P<num>[0-9]+[a-z]?(\.[0-9]+)?)'.format(  # pylint: disable=C0209
    re_choice(get_args(FigureRefType)))
# Figures are marked up using the pandoc convention for captions, a leading ":".
# Type and number are used to look up the associated file in the volume's media directory.
# e.g.  Map 1:
# Number format: 1, 2a, 2.1
FIGURE_PATTERN = re.compile(r':\s*_*' + _FIGURE_REGEX + '_*:?')

# Reference patterns: Map 1.2
FIGURE_REF_PATTERN = re.compile(_FIGURE_REGEX)

# Cross references:
# § 3.1
CROSS_REF_PATTERN = re.compile(  # #s-<section>-<subsection>-<subsubsection>
    r'(vol(\.|ume)\s*(?P<volume>[1-9])\s*(?P<sep>,|\()\s*)?'
    r'((C|c)h(apter|\.)?\s*(?P<chapter>[0-9]+),\s*)?'
    r'((?<!§)§\s*(?P<section>[0-9]+))'
    r'(\s*\.\s*(?P<subsection>[0-9]+))?'
    r'(\s*\.\s*(?P<subsubsection>[0-9]+))?')
# vol 2, chapter 3
CROSS_REF_PATTERN_NO_SECTION = re.compile(
    r'(vol(\.|ume)\s*(?P<volume>[1-5])\s*(?P<sep>,|\()\s*)'
    r'((C|c)h(apter|\.)?\s*(?P<chapter>[0-9]+)\s*)'
)
# vol.4:278
CROSS_REF_PATTERN_PAGES = re.compile(
    r'(vol(\.|ume)\s*(?P<volume>[1-5])\s*(?P<sep>,|\(|\:))\s*(pp?\.?)?\s*(?P<page>[0-9][0-9]+)')
# §§ 7-8
CROSS_REF_PATTERN_MULTI_SECTIONS = re.compile(
    r'(vol(\.|ume)\s*(?P<volume>[1-9])\s*(?P<sep>,)\s*)?'
    r'((C|c)h(apter|\.)?\s*(?P<chapter>[0-9]+),\s*)?'
    r'(§§\s*(?P<fromsection>[0-9 .]+))[-–](?P<tosection>[0-9.]+)'
)

# Paragraph-level markup:

BLOCKQUOTE_KEYWORD = '__blockquote__'
FORMGROUP_KEYWORD = '__formgroup__'
UL_KEYWORD = '__ul__'
BLOCK_KEYWORD = '__block__'
PREFORMATTED_KEYWORD = '__pre__'
TABLE_KEYWORD = '__table__'
TABLE_NOHEAD_KEYWORD = '__tablenh__'


@dataclasses.dataclass(frozen=True)
class BlockParseSpec:
    """Blocks are structured data objects which are extracted from the text."""
    name: str
    start: str
    end: Optional[str] = None


BLOCKS = {
    b.name: b for b in [
        BlockParseSpec('etymon', '<', '>'),
        BlockParseSpec('igt', '__igt__'),
        BlockParseSpec('formgroup', '__formgroup__'),
    ]
}


def is_pagenumber(line: str) -> Optional[str]:
    """Checks whether a line starts a new page, indicated by a page number."""
    m = PAGENUMBER_LEFT_PATTERN.fullmatch(line) or PAGENUMBER_RIGHT_PATTERN.fullmatch(line)
    if m:
        return m.group('no')
    return None


def is_figure(para: ParagraphType) -> Optional[tuple[FigureTypeType, str]]:
    """
    : Figure 1: caption
    """
    m = FIGURE_PATTERN.match(para[0])
    if m:  # Turn figures and maps into CLDF Markdown links referencing MediaTable items.
        return m.group('type').lower()[:3], m.group('num')
    return None


def is_forms_line(
        line: str,
        reconstruction_pattern_: re.Pattern[str],
        reflex_pattern_: re.Pattern[str],
) -> bool:
    """
    Any of the following will match:

    PMP *balay 'open-sided building'
    -Tongic
      ADM: ...
    cf. also
    """
    return (bool(re.match('-[A-Z]', line)) or  # noqa: W504
            (bool(reconstruction_pattern_.match(line)) or  # noqa: W504
             bool(reflex_pattern_.match(line)) or  # noqa: W504
             line.strip().startswith(CF_LINE_PREFIX)))


#
# For improved accuracy, some patterns require information about controlled vocabularies for parts.
#
def reflex_pattern(reflex_groups: Iterable[str]) -> re.Pattern[str]:
    """A reflex line starts with an indented group label followed by a colon."""
    return re.compile(r'\s+({})(\s*:\s+)'.format(re_choice(reflex_groups)))  # pylint: disable=C0209


def pos_pattern(pos_map: Iterable[str]) -> re.Pattern[str]:
    """Matches a part-of-speech tag, optionally in brackets."""
    return re.compile(r'\s*\((?P<pos>{})\s?\)\s*'.format(  # pylint: disable=C0209
        re_choice(pos_map)))


def reconstruction_pattern(proto_langs: Iterable[str], pos_map: Iterable[str]) -> re.Pattern[str]:
    """
    Matches some metadata and then up to the asterisk marking the protoform.

    (1) PMP root (?) (ADV) [1] *...
    """
    return re.compile(
        r'(\((?P<relno>[0-9])\)\s*)?'  # pylint: disable=C0209
        r'(?P<pl>({}))\s+'
        r'(?P<root>root\s+)?'
        r'(?P<pldoubt>\((POC)?\?\)\s*)?'
        r'(?P<pos>\(({})\)\s*)?'
        r'(?P<fn>\[[0-9]+]\s+)?'
        r'(?P<pfdoubt>\?)?†?\*'.format(
            re_choice(proto_langs),
            re_choice(pos_map)))  # FIXME: record dagger!


@dataclasses.dataclass
class ChapterMetadata:
    """
    ```json
            {
                "number": "1",
                "title": "Introduction",
                "pages": "1-14",
                "author": "Malcolm Ross and Andrew Pawley and Meredith Osmond"
            },
    ```
    """
    number: str
    title: str
    pages: str
    author: str

    @property
    def pagerange(self) -> tuple[int, int]:  # pylint: disable=C0116
        s, _, e = self.pages.partition('-')
        return int(s), int(e)

    @property
    def pagelist(self) -> list[int]:
        """List of page numbers in the chapter."""
        s, e = self.pagerange
        return list(range(int(s), int(e) + 1))

    def bib(self, volume_bib: Source) -> Source:  # pylint: disable=C0116
        bib = Source('incollection', f'{volume_bib.id}-{self.number}', **dict(volume_bib.items()))
        bib['booktitle'] = bib.pop('title')
        bib['title'] = self.title
        bib['author'] = self.author
        bib['pages'] = self.pages
        return bib


@dataclasses.dataclass
class VolumeMetadata:
    """
    ```json
    {
        "title": "Material culture",
        "chapters": [
            ...
        ]
    }
    ```
    """
    title: str
    chapters: list[ChapterMetadata]

    def __getitem__(self, item: str) -> ChapterMetadata:
        for md in self.chapters:
            if md.number == item:
                return md
        raise KeyError(f'Chapter number {item} not found')  # pragma: no cover

    @classmethod
    def from_json(cls, obj: dict[str, Any]):  # pylint: disable=C0116
        return cls(title=obj['title'], chapters=[ChapterMetadata(**ch) for ch in obj['chapters']])


@dataclasses.dataclass
class VolumeDir:
    """
    - md.json
    - text.txt
    - media/
      - map_1.png
      - fig_1.png
    """
    path: pathlib.Path
    bib: Source = None

    @classmethod
    def from_path(  # pylint: disable=C0116
            cls, d: pathlib.Path,
            citation_template: Source,
            project_id: str,
    ) -> 'VolumeDir':
        assert re.fullmatch(r'vol[0-9]', d.name), \
            "Volume dirs are expected to be named vol[0-9]"
        res = cls(d)
        bib = Source('book', f'{project_id}{res.number}', **citation_template)
        bib['title'] += f' {res.number}: {res.metadata.title}'
        res.bib = bib
        return res

    @property
    def number(self) -> str:  # pylint: disable=C0116
        return self.path.name[-1]

    def media_path(self, type_, number) -> Optional[pathlib.Path]:
        """Path to a media file in the volume's media directory."""
        alt = list(self.path.joinpath('media').glob(f'{type_}_{number}.*'))
        if not alt:
            return None  # pragma: no cover
        assert len(alt) == 1, f'Ambiguous figure spec: {type_}_{number}'
        return alt[0]

    @staticmethod
    def figure_id(volnum: str, type_: str, number: str) -> str:
        """Recipe to construct figure IDs."""
        type_ = type_.lower()[:3]
        if type_ == 'tab':
            return f"tab-{number}"
        return f"{type_}-{volnum}-{number.replace('.', '_')}"

    def id_for_figure(self, type_: Literal['map', 'fig'], number: str) -> Optional[str]:
        """A project-wide unique identifier for a figure."""
        p = self.media_path(type_, number)
        if p:
            return self.figure_id(self.number, type_, number)
        return None  # pragma: no cover

    def iter_figures(self, text: str) -> Generator[tuple[str, str, pathlib.Path], None, None]:
        """Yield figures which have already been marked with CLDF Markdown links in text."""
        figs = []

        def repl(ml):
            if ml.table_or_fname == 'MediaTable':
                # We parse the identifier format as emitted by `id_for_figure`:
                mtype, _, fignum = ml.objid.split('-', maxsplit=2)
                p = self.media_path(mtype, fignum.replace('_', '.'))
                if p:
                    figs.append((ml.objid, ml.label, p))

        CLDFMarkdownLink.replace(text, repl)
        yield from figs

    @functools.cached_property
    def metadata(self) -> VolumeMetadata:  # pylint: disable=C0116
        return VolumeMetadata.from_json(jsonlib.load(self.path / 'md.json'))

    def iter_chapter_pages(self) -> Generator[tuple[str, tuple[int, int]], None, None]:
        """
        Note: This retrieves metadata for all volumes to make it possible to detect references.
        """
        for md in self.path.parent.glob('vol*/md.json'):
            for chap in VolumeMetadata.from_json(jsonlib.load(md)).chapters:
                yield (f"{md.parent.name.replace('vol', '')}-{chap.number}",
                       chap.pagerange)

    @functools.cached_property
    def text_lines(self) -> list[str]:
        """The volume's main text split in lines."""
        return self.path.joinpath('text.txt').read_text(encoding='utf8').split('\n')


class Parser:  # pylint: disable=R0903,R0902
    """
    Parser implements the parsing of the plaintext representation of the EtymDict.

    This parsing is informed by controlled data, listing core entities of the dictionary, such as
    - the languages
    - etc.
    """
    def __init__(  # pylint: disable=R0913,R0917
            self,
            project_id: str,
            volumes: list[pathlib.Path],
            languoids: Languoids,
            # Mapping of part-of-speech tags.
            pos_map: dict[str, str],
            citation_template: Source,
    ):
        self.project_id: str = project_id

        self.graphemes: dict[str, Container[str]] = {
            name: languoids.grapheme_tokens(name) for name in languoids.by_name}
        self.languoids: dict[LanguageIdType, dict[str, Any]] = languoids.by_name
        self.reflex_pattern: re.Pattern[str] = reflex_pattern(languoids.reflex_groups)
        self.pos_pattern: re.Pattern[str] = pos_pattern(pos_map)
        self.pos_map = pos_map
        self.kinship_pattern: re.Pattern[str] = kinship.PATTERN
        self.reconstruction_pattern: re.Pattern[str] = reconstruction_pattern(
            [v['Name'] for v in languoids.proto_languages], pos_map)
        self.bib = citation_template
        self.volumes: list[VolumeDir] = [
            VolumeDir.from_path(d, citation_template, project_id) for d in volumes]

    def is_forms_line(self, line) -> bool:
        """
        Identifies a line in a form group or a reflex listed for an etymon.
        """
        return is_forms_line(line, self.reconstruction_pattern, self.reflex_pattern)
