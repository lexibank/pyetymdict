"""

"""
import re
import functools
import collections
from collections.abc import Generator, Iterable
import dataclasses
from typing import Any, Optional, Union, Protocol

from pycldf.sources import Source, Sources
from clldutils.misc import slug
from pyigt import IGT, LGRConformance

from .spec import (Parser, VolumeDir, LanguageIdType, ChapterNumberType, BLOCKS, BlockParseSpec)
from .forms import (
    parse_protoform, iter_glosses, RawGloss, get_quotes,
    strip_footnote_reference, strip_comment
)
from .lines import Block, formblock, extract_blocks, iter_chapters, HeaderType, TocItemType
from .util import markdown_escape, polish_text, cldf_markdown_link
from . import refs


class BlockObject(Protocol):
    """An object class that can be used with `extract_blocks`"""
    id: str

    @classmethod
    def from_block(cls, index: int, volume: 'Volume', block: Block) -> 'BlockObject':
        ...  # pragma: no cover

    def cldf_markdown_link(self) -> str:
        ...  # pragma: no cover


@dataclasses.dataclass
class Reference:
    """A reference to a bibliographical source."""
    id: str
    label: str
    pages: str = None

    def __str__(self):
        return f'[{self.label}]({self.id})'

    @property
    def cldf_id(self) -> str:
        """The reference formatted for a CLDF Source field."""
        res = self.id
        if self.pages:
            res += f"[{self.pages.replace('[', '［').replace(']', '］')}]"
        return res


@dataclasses.dataclass(eq=False)
class DataReference:
    """
    An reference to an object in the CLDF dataset, extracted from the raw data and re-inserted
    when rendering.

    Instances of this class are responsible for storing enough identifying information to make this
    process work.

    The location information gleaned from the containing text which is stored with this base class
    will be filled in when using `extract_blocks` to parse the text.
    """
    volume: Optional[str] = None
    chapter: Optional[HeaderType] = None
    section: Optional[HeaderType] = None
    subsection: Optional[HeaderType] = None
    page: Optional[Union[str, int]] = None

    __table__ = None

    def subkey(self) -> list[str]:
        """
        Subclasses can use this method to add more identifying information, possibly derived from
        the extracted data.
        """
        return []  # pragma: no cover

    def key(self) -> tuple:
        """The constituents of the referenced object's identifier."""
        if not self.section:
            raise ValueError(str(self))  # pragma: no cover
        return tuple([
            self.volume,
            self.chapter[0] if self.chapter else None,
            self.section[0] if self.section else None,
            self.subsection[0] if self.subsection else None,
            self.page,
        ] + list(self.subkey()))

    @property
    def id(self) -> str:
        """The identifier."""
        return '-'.join(str(s) for s in self.key())

    def __hash__(self):
        return hash(self.key())

    def __eq__(self, other):  # pragma: no cover
        return self.key() == other.key()

    def cldf_markdown_link_label(self) -> str:
        """The label to use for a CLDF Markdown link constructed for the reference."""
        return self.id

    def cldf_markdown_link(self) -> str:
        """The reference formatted as CLDF Markdown link."""
        return cldf_markdown_link(self.__table__, self.id, label=self.cldf_markdown_link_label())


def _group_regex(vol):
    return r'(?P<group>' + vol.parser.languoids.reflex_group_regex + r')'


@dataclasses.dataclass
class Example:
    id: str = None
    analyzed: str = None
    gloss: str = None
    add_gloss: Optional[str] = None
    translation: str = None
    comment: Optional[str] = None
    reference: Reference = None
    language: str = None
    label: Optional[str] = None

    @functools.cached_property
    def igt(self):
        return IGT(phrase=self.analyzed, gloss=self.gloss)

    def __str__(self):
        return """{}{}{}
{}
""".format(self.label + ' ' if self.label else '',
           self.language + ':',
           ' ({})'.format(self.reference.label) if self.reference else '',
           '\n'.join(str(self.igt).split('\n')[1:]))

    @classmethod
    def from_lines(cls, vol, lines, lang=None, ref=None):
        #
        # FIXME: Make example spec explicit!
        #
        add_gloss, header = None, None
        if len(lines) == 3:
            analyzed, gloss, translation = lines
        elif len(lines) == 4:
            if lang is None:
                header, analyzed, gloss, translation = lines
            else:
                # Additional gloss line.
                analyzed, gloss, add_gloss, translation = lines
        else:
            raise ValueError(lines)  # pragma: no cover
        s, e = get_quotes(translation)

        assert lang or header, lines

        translation = re.sub(
            "(?P<pre>[A-Za-z]){}(?P<post>[a-z])".format(e),
            lambda m: "{}__e__{}".format(m.group('pre'), m.group('post')),
            translation)

        assert translation.startswith(s), (s, translation, lines)
        translation, _, comment = translation[1:].partition(e)
        translation = translation.replace('__e__', e)
        comment = comment.strip()
        real_comment = None
        if comment:
            assert comment.startswith('(') and comment.endswith(')'), (comment, lines)
            for cmt in re.split(r'\)\s*\(', comment):
                cmt = cmt.lstrip('(').rstrip(')')
                r = vol.match_ref(cmt)
                if r:
                    ref = Reference(r[0], cmt, r[1])
                else:
                    assert not real_comment, (real_comment, cmt, lines[-1])
                    real_comment = cmt

        label = None
        m = re.match(r'(?P<label>[a-g][.)])\s+', header or analyzed)
        if m:
            label = m.group('label')
            if header:
                header = header[m.end():]
            else:
                analyzed = analyzed[m.end():]

        if lang is None:
            try:
                lang, ldata, header = vol.match_language(header)
            except:  # pragma: no cover  # noqa E722
                raise ValueError(header)
            m = re.fullmatch(r'\s*\(' + _group_regex (vol) + r'(,[^)]+)?\)\s*', header)
            assert m and m.group('group') == ldata['Group'], (header, ldata['Group'])

        igt = IGT(phrase=analyzed, gloss=gloss)
        if igt.conformance != LGRConformance.MORPHEME_ALIGNED:
            cmt, analyzed = strip_comment(analyzed)
            if cmt:
                assert not real_comment, '\n'.join(lines)
                real_comment = cmt
            igt = IGT(phrase=analyzed, gloss=gloss)
            assert igt.conformance == LGRConformance.MORPHEME_ALIGNED, lines

        if add_gloss:
            assert len(add_gloss.split()) == len(igt.glossed_words), \
                (add_gloss, len(igt.glossed_words))

        return cls(
            analyzed=analyzed.split(),
            gloss=gloss.split(),
            add_gloss=add_gloss.split() if add_gloss else None,
            translation=translation,
            comment=real_comment,
            reference=ref,
            language=lang,
            label=label,
        )


@dataclasses.dataclass
class ExampleGroup(DataReference):
    """
    (1) Boumaa (Fij): (Dixon 1988:204, 231)
    a. Au   rabe.
       s:1s kick
       'I'm kicking.'
    b. Au    rabe-t-a     a   polo.
       s:1s  kick-TR-O:3s ART ball
       'I'm kicking the ball.'

    Longgu (SES)
      e     la vu komu (local noun)
      S:3SG go R  village
      ‘s/he went towards her/his (home) village’
       e     la vu   ta-na      iola  ŋaia (common noun)
       S:3SG go R    PREP-P:3SG canoe D:3SG
       ‘s/he went to her/his (canoe)’

    Seimat (Adm)
    Tok      mom          hahitak-e         tehu     iŋ.
    CLF      chicken      under-CSTR        CLF      house
    ‘The chicken [is] under the house.’ (Wozna & Wilson 2005:66)

    Additional gloss line:

    Hoava (MM)
    Hagala       vura        mae         sa          manue.
    run          go. out     come        ART:S       possum
    MANNER       PATH        DEIXIS
    ‘The possum came running out.’ (Davis 2003:155)

    12)   a. Mussau (Adm)
         ko-tolu olimo namū
         ATTRIB-3 canoe big
         ‘three big canoes’ (Brownie & Brownie 2007:51)
      b. Ughele (MM, New Georgia group)
         ka      made vineki meke ka         rua koreo
         ATTRIB 4       girls and ATTRIB 2 men
         ‘four girls and two men’ (Frostad 2012:59)
      c. Kwamera (SV, Tanna)
         nimʷa kəru
         house 2          ‘two houses’ (Lindstrom & Lynch 1994:16)
    """
    index: int = None
    number: Optional[str] = None
    context: Optional[str] = None
    examples: list = dataclasses.field(default_factory=list)
    __table__ = 'examplegroups.csv'

    def subkey(self):
        return [self.index]

    @classmethod
    def from_block(cls, index: int, vol: 'Volume', block: Block) -> 'ExampleGroup':
        lines = block.lines
        num, ref, context = None, None, None
        header, examples = lines[0], lines[1:]
        header = header.strip()
        # Extract optional example number:
        m = re.match(r'\(?(?P<num>[0-9]+|[a-z])\)', header)
        if m:
            num = m.group('num')
            header = header[m.end():].strip()

        # First look for  "12)   a. Mussau (Adm)"
        if re.match(r'[a-g]\.\s+', header):
            lines[0] = header
            assert len(lines) % 4 == 0, lines
            examples = [
                Example.from_lines(vol, [ln.strip() for ln in lines[i:i + 4]])
                for i in range(0, len(lines), 4)]
        else:
            try:
                lang, ldata, header = vol.match_language(header)
            except:  # pragma: no cover  # noqa E722
                raise ValueError(header)
            if not ldata:
                # A proto language!
                assert (not header.strip()) or header.strip().startswith(':')
            if ldata and ldata['Group']:
                m = re.match(r'\s*\(' + _group_regex (vol) + r'\)', header)
                assert m, (vol.dir.number, lang, ldata, lines[0])
                assert m.group('group') == ldata['Group']
                header = header[m.end():].strip()

            header = header.lstrip(': ')
            if header:
                res = vol.match_ref(header)
                if res:
                    srcid, pages = res
                    ref = Reference(srcid, header.lstrip('(').rstrip(')'), pages)
                else:
                    context = header

            assert len(examples) % 3 == 0 or len(examples) == 4, (vol.dir.number, lines)
            examples = [line.strip() for line in examples]
            examples = [Example.from_lines(vol, examples, lang, ref)] if len(examples) == 4 \
                else [Example.from_lines(vol, examples[i:i + 3], lang, ref)
                      for i in range(0, len(examples), 3)]

        res = cls(
            volume=str(vol.dir.number),
            chapter=block.chapter,
            section=block.section,
            subsection=block.subsection,
            page=block.pagenumber,
            index=index,
            number=num,
            context=context,
            examples=examples,
        )
        for i, e in enumerate(res.examples, start=1):
            e.id = f'{res.id}-{i}'
        return res


def comment_or_sources(vol: 'Volume', cmt: str) -> tuple[Optional[str], Optional[list[Reference]]]:
    """
    If `cmt` can be parsed as comma-separated list of references, these are returned.
    """
    srcs = []
    for chunk in re.split(r'[,;]', cmt):
        chunk = chunk.strip()
        res = vol.match_ref(chunk)
        if res:
            srcs.append(Reference(res[0], chunk, res[1]))
        else:  # We connot match the chunk.
            return cmt, None
    return None, srcs


@dataclasses.dataclass(eq=False)
class Gloss:
    gloss: Optional[str]
    morpheme_gloss: Optional[str] = None
    kinship_gloss: Optional[str] = None
    comment: Optional[str] = None
    sources: list[Reference] = dataclasses.field(default_factory=list)
    number: Optional[str] = None
    pos: Optional[str] = None
    fn: Optional[str] = None
    qualifier: Optional[str] = None  # Typically a gloss number.
    species: Optional[str] = None
    doubt: Optional[bool] = None

    def key(self):
        return (self.gloss, self.pos, self.comment)

    def __hash__(self):
        return hash(self.key())

    def __eq__(self, other):
        return self.key() == other.key()

    @classmethod
    def from_rawgloss(cls, vol, d: RawGloss):
        if d.comments:
            cmts = []
            for cmt in d.comments:
                cmt, srcs = comment_or_sources(vol, cmt)
                if cmt:
                    cmts.append(cmt)
                elif srcs:
                    d.sources = srcs
            d.comments = cmts

        return cls(
            fn=d.fn,
            pos=d.pos,
            gloss=d.gloss,
            comment="; ".join(d.comments or []),
            morpheme_gloss=d.morpheme_gloss,
            kinship_gloss=d.kinship_gloss,
            species=d.species,
            qualifier=d.qualifier,
            doubt=d.uncertain,
            sources=d.sources or [])


@dataclasses.dataclass
class Form:
    lang: str
    forms: list[str]
    glosses: list[Gloss] = None
    subgroup: str = None
    footnote_number: str = None
    morpheme_gloss: str = None
    kinship_gloss: str = None


@dataclasses.dataclass
class Protoform(Form):
    """
    PEOc (POC?)[6] *kori(s), *koris-i- 'scrape (esp. coconuts), grate (esp. coconuts)
    """
    comment: str = None
    pfdoubt: bool = False
    pldoubt: bool = False
    sources: list[Reference] = None

    @property
    def form(self):
        return ', '.join(self.forms)

    def __str__(self):  # pragma: no cover
        return "{}\t{}\t{}{}\t{}".format(
            self.lang,
            ', '.join('*' + f for f in self.forms),
            f'({self.comment})' if self.comment else '',
            '({})'.format(', '.join(str(s) for s in self.sources)) if self.sources else '',
            "; ".join(str(g) for g in self.glosses),
        )

    @classmethod
    def from_line(cls, vol, line, subgroup=None):
        kw = {'glosses': []}
        m = vol.parser.reconstruction_pattern.match(line)
        assert m

        kw['lang'] = m.group('pl')
        kw['pfdoubt'] = bool(m.group('pfdoubt'))
        kw['pldoubt'] = bool(m.group('pldoubt'))
        pos = m.group('pos') or None
        # FIXME: root!
        fn = (m.group('fn') or '').replace('[', '').replace(']', '').strip() or None
        rem = line[m.end(0):].strip()

        forms, rem = parse_protoform(rem, vol.parser.graphemes[kw['lang']])
        "('‘?["
        if rem.startswith('?'):
            kw['pfdoubt'] = True
            rem = rem[1:].strip()
            if rem:
                assert rem[0] in "('‘[", line

        if not fn:
            rem, fn, fnpos = strip_footnote_reference(rem, start_only=True)
        if rem:
            assert rem[0] in "('‘[", rem

        cmt, rem = strip_comment(rem, 'start')
        if cmt == '1' or vol.parser.pos_pattern.fullmatch("({})".format(cmt)):
            # It's part of the glosses.
            if rem.startswith('(?)'):
                # POc *qatu(R) (N) (?) ‘number of things in a line, row’
                kw['pfdoubt'] = True  # ?
                rem = rem[3:].strip()
            assert rem[0] in "'‘", line
            pass
            rem = f'({cmt}) {rem}'
        elif cmt:
            # Check whether it's a source or comma-separated list of sources!
            # PMP *bubuŋ (Dempwolff 1938, Zorc 1994) 'ridgepole, ridge of the roof'
            cmt, srcs = comment_or_sources(vol, cmt)
            if cmt:
                kw['comment'] = cmt
            elif srcs:
                kw['sources'] = srcs
        elif rem:
            assert rem[0] in "'‘[", line

        if rem.startswith('[') and rem.endswith(']'):
            kw['morpheme_gloss'] = rem[1:-1].strip()
            rem = ''

        if rem:
            # Now consume the gloss.
            kw['glosses'] = []
            for i, g in enumerate(iter_glosses(rem, vol.parser.pos_pattern)):
                if i == 0 and pos:
                    assert not g.pos, line
                    g.pos = pos
                kw['glosses'].append(Gloss.from_rawgloss(vol, g))

        for g in kw['glosses']:
            if g.fn:
                assert not fn
                fn = g.fn

        kw['forms'] = forms
        return cls(subgroup=subgroup, footnote_number=fn, **kw)


@dataclasses.dataclass
class Reflex(Form):
    group: str = None
    lfn: str = None  # Footnote with comment about the language.
    ffn: str = None  # Footnote with comment about the form.

    @property
    def form(self):
        return self.forms[0]

    @classmethod
    def from_line(cls, vol: 'Volume', line: str, subgroup: Optional[str] = None):
        group, _, rem = line.partition(':')
        group = group.strip()
        lang = vol.match_language(rem.strip(), group=group)
        assert lang, line
        lang = lang[0]
        for word in lang.split():
            rem = rem.lstrip(' ')
            assert rem.startswith(word), rem
            rem = rem[len(word):].strip()

        # get the next word:
        rem, lfn, _ = strip_footnote_reference(rem, start_only=True)
        if rem.startswith('|'):  # multi word marker
            assert rem.count('|') == 2, rem
            word, _, rem = rem[1:].strip().partition('|')
            rem = rem.strip()
            words = word.split()
        else:
            rem_comps = rem.split()
            try:
                word, comma = rem_comps.pop(0), None
            except:  # pragma: no cover # noqa E722
                raise ValueError(line)
            if word.endswith(','):
                word = word[:-1]
                comma = True
            words = [word]
            if comma:
                w2 = rem_comps.pop(0)
                words.append(w2)
                word += ', {}'.format(w2)
            rem = ' '.join(rem_comps)

        for w in words:
            #
            # check if there's a profile, look up from parser?, then segment.
            #
            for c in w:  # FIXME: properly segment using a profile later!
                if c not in ',[]':
                    if c not in vol.parser.graphemes[lang]:  # vol.parser.reflex_graphemes(lang)
                        raise ValueError(
                            c, w, rem, line, vol.parser.graphemes[lang])  # pragma: no cover

        rem, ffn, pos = strip_footnote_reference(rem, start_only=True)
        assert not (lfn and ffn)
        fn = lfn or ffn
        assert lang, line
        glosses = [
            Gloss.from_rawgloss(vol, g)
            for g in iter_glosses(rem, vol.parser.pos_pattern)]
        for g in glosses:
            if g.fn:
                assert not fn
                fn = g.fn
        assert len([g for g in glosses if g.morpheme_gloss]) < 2
        return cls(
            group=group.strip(),
            lang=lang,
            forms=[word],
            glosses=glosses,
            footnote_number=fn,
            morpheme_gloss=glosses[0].morpheme_gloss if glosses else None,
            kinship_gloss=glosses[0].kinship_gloss if glosses else None,
            subgroup=subgroup,
        )


def iter_objs(
        vol: 'Volume',
        lines: Iterable[str],
) -> Generator[Union[Protoform, Reflex], None, None]:
    subgroup = None
    for line in lines:
        if vol.parser.reconstruction_pattern.match(line):
            yield Protoform.from_line(vol, line, subgroup=subgroup)
            continue
        if vol.parser.reflex_pattern.match(line):
            yield Reflex.from_line(vol, line, subgroup=subgroup)
            continue
        if line.startswith('-'):
            subgroup = line[1:].strip()
            continue
        raise ValueError(line)  # pragma: no cover


@dataclasses.dataclass(eq=False)
class FormGroup(DataReference):
    """
    Groups of (not necessarily cognate) forms. E.g. forms appended to an etymon as "cf." forms,
    often loanwords, which are not to be confused with proper cognates.
    """
    forms: list = None
    __table__ = 'cf.csv'

    def subkey(self):
        """
        We assume that there are no two form groups starting with the same form in the same section.
        SO adding information about the first form to the key should make it unique.
        """
        f = self.forms[0]
        return (slug(getattr(f, 'group', '')), slug(f.lang), slug(f.forms[0]))

    @classmethod
    def from_block(cls, _: int, vol: 'Volume', block: Block) -> 'FormGroup':
        """Instantiate an object from the lines of a block."""
        forms = list(iter_objs(vol, block.lines))
        assert forms, (vol.dir.number, block.lines)
        return cls(
            volume=str(vol.dir.number),
            chapter=block.chapter,
            section=block.section,
            subsection=block.subsection,
            page=block.pagenumber,
            forms=forms,
        )


@dataclasses.dataclass
class Reconstruction(DataReference):
    reflexes: list = None
    cfs: list = None
    disambiguation: str = 'a'

    def key(self):
        return (
            self.volume,
            self.chapter[0] if self.chapter else None,
            self.section[0] if self.section else None,
            self.subsection[0] if self.subsection else None,
            self.page,
            slug(self.reflexes[0].lang),
            slug(self.reflexes[0].forms[0]),
            self.disambiguation,
        )

    @property
    def id(self):
        return '-'.join(str(s) for s in self.key())

    @property
    def computed_gloss(self) -> Optional[str]:
        return None

    def __hash__(self):
        return hash(self.key())

    def cldf_markdown_link(self):
        return cldf_markdown_link(
            'cognatesetreferences.csv',
            self.id,
            f'{self.reflexes[0].lang} &ast;_{markdown_escape(self.reflexes[0].forms[0])}_')

    @classmethod
    def from_block(cls, _: int, vol: 'Volume', block: Block):
        forms, cfs = formblock(vol.parser, block.lines)
        reflexes = list(iter_objs(vol, forms))
        assert any(isinstance(ref, Protoform) for ref in reflexes)

        return cls(
            volume=vol.dir.number,
            chapter=block.chapter,
            section=block.section,
            subsection=block.subsection,
            page=block.pagenumber,
            reflexes=reflexes,
            cfs=[(cfspec, list(iter_objs(vol, cf))) for cfspec, cf in cfs or []]
        )


@dataclasses.dataclass
class Chapter:
    text: str
    toc: list[TocItemType]
    bib: Source
    pages: list[int]

    @classmethod
    def from_text(cls, vol: 'Volume', num: str, text: str, toc: list[TocItemType]) -> 'Chapter':
        """Initializze from volume and text."""
        md = vol.dir.metadata[num]
        header = f"\n[{md.author}]{{.smallcaps}}\n\n<!--start-->\n"
        text = vol.replace_cross_refs(text, num)
        return cls(
            polish_text(header + vol.replace_source_refs(text)),
            toc,
            md.bib(vol.dir.bib),
            pages=md.pagelist)

    def iter_sections(self) -> Generator[tuple[str, str], None, None]:
        """Split chapter text into sections - using the inserted HTML anchors."""
        anchor = re.compile(r'<a id=\"(?P<sec>s-[0-9\-]+)\">')
        sec = ''
        lines: list[str] = []

        for line in self.text.split('\n'):
            m = anchor.match(line)
            if m:
                if sec:
                    yield sec, '\n'.join(lines)
                sec, lines = m.group('sec'), []
            else:
                lines.append(line)
        if sec:
            yield sec, '\n'.join(lines)


class Volume:
    """
    A Volume is the central, citeable unit of data, or a Contribution in CLDF terms.

    The data of a volume is expected to be found in a directory, structured as described for
    `VolumeDir`.
    """
    def __init__(  # pylint: disable=R0913,R0917
            self,
            parser: 'Parser',
            d: VolumeDir,
            sources: Sources,
            reconstruction_cls: Optional[type] = None,
    ):
        self.parser: 'Parser' = parser
        self.dir: VolumeDir = d
        self.sources = sources
        self._reconstruction_cls = reconstruction_cls or Reconstruction
        self._lines = None

    @functools.cached_property
    def chapter_pages(self) -> dict[str, tuple[int, int]]:
        """Page ranges per chapter."""
        return dict(self.dir.iter_chapter_pages())

    def __str__(self):  # pragma: no cover
        return self.dir.bib['title']

    def match_language(
            self,
            s: str,
            group: Optional[str] = None,
    ) -> Optional[tuple[LanguageIdType, Optional[collections.OrderedDict[str, Any]], str]]:
        """Check if the start of `s` matches a known language in the Volume."""
        for lg in sorted(self.parser.languoids.by_name, key=lambda ll: -len(ll)):
            if s.startswith(lg):
                assert group is None or (self.parser.languoids.by_name[lg]['Group'] == group), \
                    (group, lg, s)
                return lg, self.parser.languoids.by_name[lg], s[len(lg):]
        return None

    @functools.cached_property
    def chapters(self) -> collections.OrderedDict[Union[None, ChapterNumberType], Chapter]:
        """Chapters of the volume keyed by number."""
        if not self._lines:
            assert self.reconstructions
        return collections.OrderedDict(
            (num, Chapter.from_text(self, num, text, toc))
            for num, text, toc in iter_chapters(self._lines, self.dir))

    @functools.cached_property
    def source_in_brackets_pattern_dict(self) -> dict[str, re.Pattern[str]]:
        """Patterns to match references to sources."""
        return {src.id: refs.key_to_regex(src['key'], in_text=False) for src in self.sources}

    @functools.cached_property
    def source_pattern_dict(self) -> collections.OrderedDict[str, re.Pattern[str]]:
        """Patterns to match references to sources."""
        res = collections.OrderedDict()
        for src in sorted(self.sources, key=lambda src: -len(src['key'])):
            res[src.id] = refs.key_to_regex(src['key'])
        return res

    def match_ref(self, s) -> Optional[tuple[str, Optional[str]]]:
        """Try to match a single source reference, possibly including page numbers."""
        if not s.startswith('('):
            s = f'({s})'
        pages = None
        if s.endswith(')'):
            m = re.search(r':\s*(?P<pages>[0-9]+([,;-]\s*[0-9]+)*)\)', s)
            if m:
                pages = m.group('pages')
                s = s[:m.start()] + ')'
        for srcid, pattern in self.source_in_brackets_pattern_dict.items():
            m = pattern.fullmatch(s)
            if m:
                return srcid, pages or m.groupdict().get('pages')
        return None

    def replace_cross_refs(self, s, chapter):
        """Replace references to sections, etc. with markdown links."""
        res = refs.replace_cross_refs(s, self.dir.number, chapter, self.chapter_pages)
        return refs.replace_figure_refs(res, self.dir.number)

    def replace_source_refs(self, s: str) -> str:
        """Replace references to sources with CLDF Markdown links."""
        return refs.replace_source_refs(s, self.source_pattern_dict)

    @functools.cached_property
    def reconstructions(self) -> list[Reconstruction]:
        """Extracted reconstructions."""
        # This must be called as first object extractor!
        self._lines = self.dir.text_lines
        return list(self._iter_blocks(BLOCKS['etymon'], self._reconstruction_cls))

    @functools.cached_property
    def formgroups(self) -> list[FormGroup]:
        """Extracted formgroups."""
        assert self.reconstructions, 'self._lines not initialized!'
        return list(self._iter_blocks(BLOCKS['formgroup'], FormGroup))

    @functools.cached_property
    def igts(self) -> list[ExampleGroup]:
        """Extracted examples."""
        assert self.reconstructions, 'self._lines not initialized!'
        return list(self._iter_blocks(BLOCKS['igt'], ExampleGroup))

    def _iter_blocks(
            self,
            block_spec: BlockParseSpec,
            cls: type[BlockObject],
    ) -> Generator[BlockObject, None, None]:
        objids = set()
        n = 0
        generator = extract_blocks(block_spec, self._lines)
        try:
            block = next(generator)
            n += 1
        except StopIteration:  # pragma: no cover
            return
        obj = cls.from_block(n, self, block)
        objids.add(obj.id)
        yield obj
        try:
            while True:
                block = generator.send(obj.cldf_markdown_link())
                n += 1
                obj = cls.from_block(n, self, block)
                if obj.id in objids:
                    assert hasattr(obj, 'disambiguation'), cls
                    setattr(obj, 'disambiguation', 'b')
                objids.add(obj.id)
                yield obj
        except StopIteration as e:
            self._lines = e.value
