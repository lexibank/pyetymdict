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
from clldutils import jsonlib

from .util import re_choice

ParagraphType = Sequence[str]  # A list of non-empty lines.
FigureRefType = Literal['Map', 'Table', 'Figure']
FigureTypeType = Literal['map', 'fig']
LanguageIdType = str
ChapterNumberType = str

FOOTNOTE_PATTERN = re.compile(r'\[(?P<fn>[0-9]+)]')  # [2]
CF_LINE_PREFIX = 'cf. also'  # Identifies the start of form group, appended to an etymon.

#
# FIXME: Should these patterns be configurable?
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

# A line starting with \x0c (form-feed) ...
# ... and ending with a number or ...
PAGENUMBER_RIGHT_PATTERN = re.compile(r'(\x0c|###newpage###)\s+\D+(?P<no>\d+)')
# ... immediately followed by a number.
PAGENUMBER_LEFT_PATTERN = re.compile(r'(\x0c|###newpage###)(?P<no>\d+)\s+\D+')

# Reference patterns: Map 1.2
FIGURE_REF_PATTERN = re.compile(
    r'(?P<type>{})\s+(?P<num>[0-9]+(\.[0-9]+)?)'.format(re_choice(get_args(FigureRefType))))
# Cross references:
# § 3.1
CROSS_REF_PATTERN = re.compile(  # #s-<section>-<subsection>-<subsubsection>
    r'(vol(\.|ume)\s*(?P<volume>[1-9])\s*(?P<sep>,|\()\s*)?'
    r'((C|c)h(apter|\.)?\s*(?P<chapter>[0-9]+),\s*)?'
    r'(§\s*(?P<section>[0-9]+))'
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

# Paragraph-level markup:
# :Table 2
TABLE_CAPTION_PATTERN = re.compile(r':\s+_*Table\s+(?P<num>[0-9.]+)_*')
BLOCKQUOTE_KEYWORD = '__blockquote__'
FORMGROUP_KEYWORD = '__formgroup__'
UL_KEYWORD = '__ul__'
BLOCK_KEYWORD = '__block__'
PREFORMATTED_KEYWORD = '__pre__'
TABLE_KEYWORD = '__table__'
TABLE_NOHEAD_KEYWORD = '__tablenh__'
# Identifies maps or figures:
MAP_OR_FIGURE_PATTERN = re.compile(r'(?P<type>Map|Figure)\s+(?P<num>[0-9]+[a-z]*(\.[0-9]+)?):')


@dataclasses.dataclass(frozen=True)
class BlockParseSpec:
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


def is_table_caption(para: ParagraphType) -> Optional[str]:
    m = TABLE_CAPTION_PATTERN.match(para[0])
    if m:
        return m.group('num')
    return None


def is_map_or_figure(para: ParagraphType) -> Optional[tuple[FigureTypeType, str]]:
    m = MAP_OR_FIGURE_PATTERN.match(para[0])
    if m:  # Turn figures and maps into CLDF Markdown links referencing MediaTable items.
        return 'map' if m.group('type').lower() == 'map' else 'fig', m.group('num')
    return None


def is_forms_line(
        line: str,
        reconstruction_pattern: re.Pattern[str],
        reflex_pattern: re.Pattern[str],
) -> bool:
    """
    Any of the following will match:

    PMP *balay 'open-sided building'
    -Tongic
      ADM: ...
    cf. also
    """
    return (bool(re.match('-[A-Z]', line)) or  # noqa: W504
            (bool(reconstruction_pattern.match(line)) or  # noqa: W504
             bool(reflex_pattern.match(line)) or  # noqa: W504
             line.strip().startswith(CF_LINE_PREFIX)))


#
# For improved accuracy, some patterns require information about controlled vocabularies for parts.
#
def reflex_pattern(reflex_groups: Iterable[str]) -> re.Pattern[str]:
    """A reflex line starts with an indented group label followed by a colon."""
    return re.compile(r'\s+({})(\s*:\s+)'.format(re_choice(reflex_groups)))


def pos_pattern(pos_map: Iterable[str]) -> re.Pattern[str]:
    """Matches a part-of-speech tag, optionally in brackets."""
    return re.compile(r'\s*\((?P<pos>{})\s?\)\s*'.format(re_choice(pos_map)))


def kinship_pattern(kinship_tags: Iterable[str]) -> re.Pattern[str]:
    """Matches a kinship tag, optionally prefixed with a female/male specifier."""
    return re.compile(r"’\s*(,\s+([♀♂]|\([♀♂]\?\))?({})( etc)?)+".format(re_choice(kinship_tags)))


def reconstruction_pattern(proto_langs: Iterable[str], pos_map: Iterable[str]) -> re.Pattern[str]:
    return re.compile(
        r'(\((?P<relno>[0-9])\)\s*)?'
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
    def pagerange(self) -> tuple[int, int]:
        s, _, e = self.pages.partition('-')
        return int(s), int(e)

    @property
    def pagelist(self) -> list[int]:
        s, e = self.pagerange
        return list(range(int(s), int(e) + 1))

    def bib(self, volume_bib: Source) -> Source:
        bib = Source(
            'incollection',
            f'{volume_bib.id}-{self.number}',
            **{k: v for k, v in volume_bib.items()})
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
    def from_json(cls, obj: dict[str, Any]):
        return cls(title=obj['title'], chapters=[ChapterMetadata(**ch) for ch in obj['chapters']])


@dataclasses.dataclass
class VolumeDir:
    """
    - abbreviations.txt
    - appendix.txt
    - cover.png
    - frontmatter.txt
    - index.csv
    - languages.csv
    - maps/
    - md.json
    - references.bib
    - text.txt
    - toc.txt
    """
    path: pathlib.Path
    bib: Source = None

    @classmethod
    def from_data(cls, d: pathlib.Path, citation_template: Source, project_id: str):
        assert re.fullmatch(r'vol[0-9]', d.name), \
            "Volume dirs are expected to be named vol[0-9]"
        res = cls(d)
        bib = Source('book', f'{project_id}{res.number}', **citation_template)
        bib['title'] += f' {res.number}: {res.metadata.title}'
        res.bib = bib
        return res

    @property
    def number(self):
        return self.path.name[-1]

    def id_for_figure(self, type_: Literal['map', 'fig'], number: str) -> Optional[str]:
        p = self.path / 'maps' / f'{type_}_{number}.png'
        if p.exists():
            return f"{type_}-{self.number}-{number.replace('.', '_')}"
        return None

    @functools.cached_property
    def metadata(self):
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
        return self.path.joinpath('text.txt').read_text(encoding='utf8').split('\n')


class Parser:  # pylint: disable=R0903
    """
    Parser implements the parsing of the plaintext representation of the EtymDict.

    This parsing is informed by controlled data, listing core entities of the dictionary, such as
    - the languages
    - etc.
    """
    def __init__(
            self,
            project_id: str,
            volumes: list[pathlib.Path],
            languoids: dict[LanguageIdType, collections.OrderedDict[str, Any]],
            # Graphemes used for proto-forms (per proto-language):
            proto_graphemes: dict[LanguageIdType, Container[str]],
            # Graphemes used for reflexes. Since these must be homogenized to enable reconstruction,
            # we assume just one set to be used for all languages.
            reflex_graphemes: Container[str],
            # List of groups of descendant languages. Typically nodes in the reconstruction tree.
            reflex_groups: list[str],
            # Mapping of part-of-speech tags.
            pos_map: dict[str, str],
            kinship_tags: list[str],
            citation_template: Source,
    ):
        self.project_id = project_id
        self.proto_graphemes: dict[str, Container[str]] = proto_graphemes
        self.reflex_graphemes: Container[str] = reflex_graphemes
        self.languoids: dict[LanguageIdType, collections.OrderedDict[str, Any]] = languoids
        self.reflex_pattern: re.Pattern[str] = reflex_pattern(reflex_groups)
        self.pos_pattern: re.Pattern[str] = pos_pattern(pos_map)
        self.pos_map = pos_map
        self.kinship_pattern: re.Pattern[str] = kinship_pattern(kinship_tags)
        self.reconstruction_pattern: re.Pattern[str] = reconstruction_pattern(
            proto_graphemes, pos_map)
        self.bib = citation_template
        self.volumes: list[VolumeDir] = [
            VolumeDir.from_data(d, citation_template, project_id) for d in volumes]

    def is_forms_line(self, line) -> bool:
        """
        Identifies a line in a form group or a reflex listed for an etymon.
        """
        return is_forms_line(line, self.reconstruction_pattern, self.reflex_pattern)
