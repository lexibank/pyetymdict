"""

"""
import re
import typing
import pathlib
import functools
import collections
import dataclasses

from pycldf.sources import Source, Sources
from clldutils.misc import slug
from clldutils import jsonlib
from pyigt import IGT, LGRConformance

from .forms import (
    parse_protoform, iter_graphemes, iter_glosses, GlossDict, get_quotes,
    strip_footnote_reference, strip_comment
)
from .lines import CF_LINE_PREFIX, extract_etyma, iter_chapters, extract_igts, extract_formgroups
from .util import re_choice
from . import refs


@dataclasses.dataclass
class Reference:
    id: str
    label: str
    pages: str = None

    def __str__(self):
        return '[{}]({})'.format(self.label, self.id)

    @property
    def cldf_id(self):
        res = self.id
        if self.pages:
            res += '[{}]'.format(
                self.pages.replace('[', '［').replace(']', '］'))
        return res


@dataclasses.dataclass(eq=False)
class DataReference:
    """
    An object in the CLDF dataset, extracted from the raw data and re-inserted when rendering.
    """
    volume: str = None
    chapter: tuple = None
    section: tuple = None
    subsection: tuple = None
    page: int = 0

    __table__ = None

    def subkey(self):
        return []  # pragma: no cover

    def key(self):
        if not self.section:
            raise ValueError(str(self))  # pragma: no cover
        return tuple([
            self.volume,
            self.chapter[0],
            self.section[0] if self.section else None,
            self.subsection[0] if self.subsection else None,
            self.page,
        ] + list(self.subkey()))

    @property
    def id(self):
        return '-'.join(str(s) for s in self.key())

    def __hash__(self):
        return hash(self.key())

    def __eq__(self, other):  # pragma: no cover
        return self.key() == other.key()

    def cldf_markdown_link_label(self):
        return self.id

    def cldf_markdown_link(self):
        return '[{}]({}#cldf:{})\n'.format(
            self.cldf_markdown_link_label(), self.__table__, self.id)


@dataclasses.dataclass(eq=False)
class FormGroup(DataReference):
    forms: list = None
    __table__ = 'cf.csv'

    def subkey(self):
        f = self.forms[0]
        return (slug(f.group), slug(f.lang), slug(f.forms[0]))

    @classmethod
    def from_data(cls, vol, h1, h2, h3, page, lines):
        assert all(vol.parser.is_forms_line(line) for line in lines), lines
        forms = [
            Reflex.from_line(vol, line)
            for line in lines if vol.parser.witness_pattern.match(line)]
        assert forms, (vol.num, lines)
        return cls(
            volume=str(vol.num),
            chapter=h1,
            section=h2,
            subsection=h3,
            page=page,
            forms=forms,
        )


@dataclasses.dataclass
class Example:
    id: str = None
    analyzed: str = None
    gloss: str = None
    add_gloss: str = None
    translation: str = None
    comment: str = None
    reference: Reference = None
    language: str = None
    label: str = None

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
            m = re.fullmatch(r'\s*\((?P<group>[A-Za-z]+)(,[^)]+)?\)\s*', header)
            assert m and m.group('group') == ldata['Group'], lines

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
    number: str = None
    context: str = None
    examples: list = None
    __table__ = 'examplegroups.csv'

    def subkey(self):
        return [self.index]

    @classmethod
    def from_data(cls, index, vol, h1, h2, h3, page, lines):
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
                m = re.match(r'\s*\((?P<group>[A-Za-z]+)\)', header)
                assert m, (vol.num, lang, ldata, lines[0])
                assert m.group('group') == ldata['Group']
                header = header[m.end():].strip()

            header = header.lstrip(': ')
            if header:
                try:
                    srcid, pages = vol.match_ref(header)
                    ref = Reference(srcid, header.lstrip('(').rstrip(')'), pages)
                except TypeError:
                    context = header

            assert len(examples) % 3 == 0 or len(examples) == 4, (vol.num, lines)
            examples = [line.strip() for line in examples]
            examples = [Example.from_lines(vol, examples, lang, ref)] if len(examples) == 4 \
                else [Example.from_lines(vol, examples[i:i + 3], lang, ref)
                      for i in range(0, len(examples), 3)]

        res = cls(
            volume=str(vol.num),
            chapter=h1,
            section=h2,
            subsection=h3,
            page=page,
            index=index,
            number=num,
            context=context,
            examples=examples,
        )
        for i, e in enumerate(res.examples, start=1):
            e.id = '{}-{}'.format(res.id, i)
        return res


def comment_or_sources(vol, cmt) \
        -> typing.Tuple[typing.Union[None, str], typing.Union[None, typing.List[Reference]]]:
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
    gloss: str
    morpheme_gloss: str = None
    comment: str = None
    sources: typing.List[Reference] = None
    number: str = None
    pos: str = None
    fn: str = None
    qualifier: str = None  # Typically a gloss number.
    species: str = None
    doubt: bool = None

    def key(self):
        return (self.gloss, self.pos, self.comment)

    def __hash__(self):
        return hash(self.key())

    def __eq__(self, other):
        return self.key() == other.key()

    @classmethod
    def from_dict(cls, vol, d: GlossDict):
        d['sources'] = []
        if d['comments']:
            cmts = []
            for cmt in d['comments']:
                cmt, srcs = comment_or_sources(vol, cmt)
                if cmt:
                    cmts.append(cmt)
                elif srcs:
                    d['sources'] = srcs
            d['comments'] = cmts

        return cls(
            fn=d['fn'],
            pos=d['pos'],
            gloss=d['gloss'],
            comment="; ".join(d['comments'] or []),
            morpheme_gloss=d['morpheme_gloss'],
            species=d['species'],
            qualifier=d['qualifier'],
            doubt=d['uncertain'],
            sources=d['sources'])


@dataclasses.dataclass
class Form:
    lang: str
    forms: typing.List[str]
    glosses: typing.List[Gloss] = None
    subgroup: str = None
    footnote_number: str = None
    morpheme_gloss: str = None


@dataclasses.dataclass
class Protoform(Form):
    """
    PEOc (POC?)[6] *kori(s), *koris-i- 'scrape (esp. coconuts), grate (esp. coconuts)
    """
    comment: str = None
    pfdoubt: bool = False
    pldoubt: bool = False
    sources: typing.List[Reference] = None

    @property
    def form(self):
        return ', '.join(self.forms)

    def __str__(self):  # pragma: no cover
        return "{}\t{}\t{}{}\t{}".format(
            self.lang,
            ', '.join('*' + f for f in self.forms),
            '({})'.format(self.comment) if self.comment else '',
            '({})'.format(', '.join(str(s) for s in self.sources)) if self.sources else '',
            "; ".join(str(g) for g in self.glosses),
        )

    @classmethod
    def from_line(cls, vol, line, subgroup=None):
        kw = {'glosses': []}
        m = vol.parser.proto_pattern.match(line)
        assert m

        kw['lang'] = m.group('pl')
        kw['pfdoubt'] = bool(m.group('pfdoubt'))
        kw['pldoubt'] = bool(m.group('pldoubt'))
        pos = m.group('pos') or None
        # FIXME: root!
        fn = (m.group('fn') or '').replace('[', '').replace(']', '').strip() or None
        rem = line[m.end(0):].strip()

        forms, rem = parse_protoform(rem, vol.parser.proto_graphemes[kw['lang']])
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
            rem = '({}) {}'.format(cmt, rem)
        elif cmt == '?':
            assert rem[0] in "'‘", line
            kw['pfdoubt'] = True
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
            for i, g in enumerate(
                    iter_glosses(rem, vol.parser.pos_pattern, vol.parser.kinship_pattern)):
                if i == 0 and pos:
                    assert not g['pos'], line
                    g['pos'] = pos
                kw['glosses'].append(Gloss.from_dict(vol, g))

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
    def from_line(cls, vol, line, subgroup=None):
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
            for c in iter_graphemes(w):
                if c != ',':
                    if c not in vol.parser.reflex_graphemes:
                        raise ValueError(c, w, rem, line)  # pragma: no cover

        rem, ffn, pos = strip_footnote_reference(rem, start_only=True)
        assert not (lfn and ffn)
        fn = lfn or ffn
        assert lang, line
        glosses = [
            Gloss.from_dict(vol, g)
            for g in iter_glosses(rem, vol.parser.pos_pattern, vol.parser.kinship_pattern)]
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
            subgroup=subgroup,
        )


def markdown_escape(s):
    for k, v in {
        "*": "&ast;",
        "[": "&#91;",
        "]": "&#93;",
    }.items():
        s = s.replace(k, v)
    return s


@dataclasses.dataclass
class Reconstruction(DataReference):
    reflexes: list = None
    cfs: list = None
    disambiguation: str = 'a'

    @functools.cached_property
    def oceanic_protoforms(self):
        return [
            pf for pf in self.reflexes
            if isinstance(pf, Protoform) and pf.lang != 'PAn' and not pf.lang.endswith('MP')]

    @functools.cached_property
    def first_oceanic_protoform(self):
        if self.oceanic_protoforms:
            return self.oceanic_protoforms[0]
        return self.reflexes[0]

    @property
    def poc_gloss(self):
        for pf in self.oceanic_protoforms:
            if pf.glosses:
                return pf.glosses[0].gloss
            if pf.comment:
                return pf.comment
            if pf.morpheme_gloss:
                return pf.morpheme_gloss
        return self.reflexes[0].morpheme_gloss or self.reflexes[0].glosses[0].gloss

    def key(self):
        if not self.section:  # pragma: no cover
            print(self)
            raise ValueError(self)
        pf = self.first_oceanic_protoform
        return (
            self.volume,
            self.chapter[0],
            self.section[0] if self.section else None,
            self.subsection[0] if self.subsection else None,
            self.page,
            slug(pf.lang, lowercase=False),
            slug(pf.forms[0]),
            self.disambiguation,
        )

    @property
    def id(self):
        return '-'.join(str(s) for s in self.key())

    def __hash__(self):
        return hash(self.key())

    def cldf_markdown_link(self):
        return '[{} &ast;_{}_](cognatesetreferences.csv#cldf:{})\n'.format(
            self.reflexes[0].lang,
            markdown_escape(self.reflexes[0].forms[0]),
            self.id)

    @classmethod
    def from_data(cls, vol, h1, h2, h3, pageno, forms):
        forms, cfs = forms

        def iter_objs(lines):
            subgroup = None
            for line in lines:
                if vol.parser.proto_pattern.match(line):
                    yield Protoform.from_line(vol, line, subgroup=subgroup)
                    continue
                if vol.parser.witness_pattern.match(line):
                    yield Reflex.from_line(vol, line, subgroup=subgroup)
                    continue
                if line.startswith('-'):
                    subgroup = line[1:].strip()
                    continue
                raise ValueError(line)  # pragma: no cover

        reflexes = list(iter_objs(forms))
        assert any(isinstance(ref, Protoform) for ref in reflexes)

        return cls(
            volume=vol.num,
            chapter=h1,
            section=h2,
            subsection=h3,
            page=pageno,
            reflexes=reflexes,
            cfs=[(cfspec, list(iter_objs(cf))) for cfspec, cf in cfs or []]
        )


def polish_text(text):
    text = re.sub(r'\s*\.\s*\.\s*\.\s*', ' … ', text)
    return text.replace('*', '&ast;')


@dataclasses.dataclass
class Chapter:
    text: str
    toc: list
    bib: Source
    pages: list

    @classmethod
    def from_text(cls, vol, num, text, toc):
        for md in vol.metadata['chapters']:
            if md['number'] == num:
                break
        else:  # pragma: no cover
            raise ValueError('Chapter number {} not found'.format(num))

        pages = set()
        for m in re.finditer(r'<a id="p-(?P<num>[0-9]+)">', text):
            pages.add(int(m.group('num')))
        spage, _, epage = md['pages'].partition('-')
        pages = list(range(int(spage), int(epage) + 1))

        bib = Source(
            'incollection',
            vol.bib.id + '-' + md['number'],
            **{k: v for k, v in vol.bib.items()})
        bib['booktitle'] = bib.pop('title')
        bib['title'] = md['title']
        bib['author'] = md['author']
        bib['pages'] = md['pages']
        header = "\n[{}]{{.smallcaps}}\n\n<!--start-->\n".format(md['author'])
        text = vol.replace_cross_refs(text, num)
        return cls(polish_text(header + vol.replace_refs(text)), toc, bib, pages=pages)

    def iter_sections(self):
        anchor = re.compile(r'<a id=\"(?P<sec>s-[0-9\-]+)\">')
        sec, lines = None, []

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
    def __init__(self, parser, d, langs, bib, sources):
        self.parser = parser
        self.dir = d
        self.num = d.name[-1]
        self.langs = langs
        self.metadata = jsonlib.load(self.dir / 'md.json')
        self._lines = None
        bib.id = 'tlopo{}'.format(self.num)
        bib['title'] += ' {}: {}'.format(self.num, self.metadata['title'])
        self.bib = bib
        self.sources = sources
        self.chapter_pages = {}

        for md in self.dir.parent.glob('vol*/md.json'):
            for chap in jsonlib.load(md)['chapters']:
                s, _, e = chap['pages'].partition('-')
                self.chapter_pages[
                    '{}-{}'.format(md.parent.name.replace('vol', ''), chap['number'])] = \
                    (int(s), int(e))

    def __str__(self):  # pragma: no cover
        return self.bib['title']

    def match_language(self, s, group=None):
        for lg in sorted(self.langs, key=lambda ll: -len(ll)):
            if s.startswith(lg):
                assert group is None or (self.langs[lg]['Group'] == group), (group, lg, s)
                return lg, self.langs[lg], s[len(lg):]
        for k in self.parser.proto_graphemes.keys():
            if s.startswith(k):
                return k, None, s[len(k):]

    @functools.cached_property
    def chapters(self):
        if not self._lines:
            assert self.reconstructions
        return collections.OrderedDict(
            (num, Chapter.from_text(self, num, text, toc))
            for num, text, toc in iter_chapters(self._lines, self.dir))

    @functools.cached_property
    def source_in_brackets_pattern_dict(self):
        return {src.id: refs.key_to_regex(src['key'], in_text=False) for src in self.sources}

    @functools.cached_property
    def source_pattern_dict(self):
        res = collections.OrderedDict()
        for src in sorted(self.sources, key=lambda src: -len(src['key'])):
            res[src.id] = refs.key_to_regex(src['key'])
        return res

    def match_ref(self, s):
        if not s.startswith('('):
            s = '({})'.format(s)
        pages = None
        if s.endswith(')'):
            pages_pattern = re.compile(r'\:\s*(?P<pages>[0-9]+([,;-]\s*[0-9]+)*)\)')
            m = pages_pattern.search(s)
            if m:
                pages = m.group('pages')
                s = s[:m.start()] + ')'
        for srcid, pattern in self.source_in_brackets_pattern_dict.items():
            m = pattern.fullmatch(s)
            if m:
                return srcid, pages or m.groupdict().get('pages')

    def replace_cross_refs(self, s, chapter):
        def repl(m):
            # FIXME: account for (§§10.8–9), where only "§10.8" is matched!
            if m.string[:m.start()].endswith('['):
                # We are already in a link!
                return m.string[m.start():m.end()]
            path, anchor = '', ''
            if m.group('volume'):
                if m.group('chapter'):
                    path = '{}-{}'.format(m.group('volume'), m.group('chapter'))
                else:
                    return m.string[m.start():m.end()]
            else:
                if m.group('chapter'):
                    path = '{}-{}'.format(self.num, m.group('chapter'))
                else:
                    path = '{}-{}'.format(self.num, chapter)
            if 'section' in m.groupdict():
                if m.group('section'):
                    anchor = 's-{}'.format(m.group('section'))
                    if m.group('subsection'):
                        anchor += '-{}'.format(m.group('subsection'))
                        if m.group('subsubsection'):
                            anchor += '-{}'.format(m.group('subsubsection'))

            res = '[{}](ContributionTable{}#cldf:{})'.format(
                m.string[m.start():m.end()], '?anchor=' + anchor if anchor else '', path)
            return res

        res = refs.CROSS_REF_PATTERN.sub(repl, s)
        res = refs.CROSS_REF_PATTERN_NO_SECTION.sub(repl, res)

        def prepl(m):
            page = int(m.group('page'))
            for cid, (s, e) in self.chapter_pages.items():
                v, _, c = cid.partition('-')
                if v == m.group('volume') and page >= s and page <= e:
                    break
            else:
                return m.string[m.start():m.end()]
            return '[vol.{}{}{}](ContributionTable?anchor=p-{}#cldf:{})'.format(
                m.group('volume'),
                m.group('sep'),
                m.group('page'),
                m.group('page'),
                cid)

        res = refs.CROSS_REF_PATTERN_PAGES.sub(prepl, res)

        def figref(m):
            label = m.string[m.start():m.end()]
            if m.string[:m.start()].strip()[-1] in {':', '_'}:
                return label
            if m.string[m.end():].strip().startswith(':'):
                return label
            if m.group('type') in {'Figure', 'Map'}:
                a = '{}-{}-{}'.format(
                    m.group('type').lower()[:3], self.num, m.group('num').replace('.', '_'))
                return '[{}](#{})'.format(label, a)
            if m.group('type') == 'Table':
                return '[{}](#table-{})'.format(label, m.group('num'))
            return label

        res = refs.FIGURE_REF_PATTERN.sub(figref, res)
        return res

    def replace_refs(self, s):
        for srcid, pattern in self.source_pattern_dict.items():
            s = pattern.sub(functools.partial(refs.repl_ref, srcid), s)

        sep = r',\s*|\s+and\s+'  # We look for comma or " and " separated years.
        m = re.compile(r"\(Source#cldf:([^\)]+)\)(({})[0-9]+(\-[0-9]+)?[a-z]?)+".format(sep))

        def repl(m):
            link, *years = [s.strip() for s in re.split(sep, m.string[m.start():m.end()])]
            author, year, inyear = '', '', False
            for c in link.partition(':')[2]:
                if not inyear and c.isdigit():
                    inyear = True
                if inyear:
                    year += c
                else:
                    author += c
            res = link
            for year in years:
                cyear = year.replace('-', '')
                if author + cyear in self.source_pattern_dict:
                    res += ', [{}](Source#cldf:{})'.format(year, author + cyear)
                else:
                    res += ', {}'.format(year)
            return res

        return m.sub(repl, s)

    @functools.cached_property
    def reconstructions(self):
        return list(self._iter_reconstructions(
            self.dir.joinpath('text.txt').read_text(encoding='utf8').split('\n')))

    @functools.cached_property
    def formgroups(self):
        return list(self._iter_formgroups())

    @functools.cached_property
    def igts(self):
        return list(self._iter_igts())

    def _iter_reconstructions(self, lines):
        rids = set()
        etyma = extract_etyma(self.parser, lines)
        h1, h2, h3, pageno, paras = next(etyma)
        rec = Reconstruction.from_data(self, h1, h2, h3, pageno, paras)
        rids.add(rec.id)
        yield rec
        try:
            while True:
                h1, h2, h3, pageno, paras = etyma.send(rec.cldf_markdown_link())
                rec = Reconstruction.from_data(self, h1, h2, h3, pageno, paras)
                if rec.id in rids:
                    rec.disambiguation = 'b'
                rids.add(rec.id)
                yield rec
        except StopIteration as e:
            self._lines = e.value

    def _iter_formgroups(self):
        assert self.reconstructions
        forms = extract_formgroups(self.parser, self._lines)
        try:
            h1, h2, h3, pageno, block = next(forms)
        except StopIteration:  # pragma: no cover
            return
        fg = FormGroup.from_data(self, h1, h2, h3, pageno, block)
        yield fg
        try:
            while True:
                h1, h2, h3, pageno, block = forms.send(fg.cldf_markdown_link())
                fg = FormGroup.from_data(self, h1, h2, h3, pageno, block)
                yield fg
        except StopIteration as e:
            self._lines = e.value

    def _iter_igts(self):
        n = 0
        assert self.reconstructions
        igts = extract_igts(self.parser, self._lines)
        try:
            h1, h2, h3, pageno, block = next(igts)
            n += 1
        except StopIteration:  # pragma: no cover
            return
        eg = ExampleGroup.from_data(n, self, h1, h2, h3, pageno, block)
        yield eg
        try:
            while True:
                h1, h2, h3, pageno, block = igts.send(eg.cldf_markdown_link())
                n += 1
                eg = ExampleGroup.from_data(n, self, h1, h2, h3, pageno, block)
                yield eg
        except StopIteration as e:
            self._lines = e.value


class Parser:
    def __init__(self,
                 volumes: typing.List[pathlib.Path],
                 languoids: typing.Dict[str, typing.Dict],
                 citation: Source,
                 sources: Sources,
                 proto_graphemes: typing.Dict[str, typing.Container[str]],
                 reflex_graphemes: typing.Container[str],
                 reflex_groups: typing.List[str],
                 pos_map: typing.Dict[str, str],
                 kinship_tags: typing.List[str]):
        self.proto_graphemes = proto_graphemes
        self.reflex_graphemes = reflex_graphemes
        self.languoids = languoids
        self.witness_pattern = re.compile(r'\s+({})(\s*:\s+)'.format(re_choice(reflex_groups)))
        self.pos_pattern = re.compile(r'\s*\((?P<pos>{})\s?\)\s*'.format(re_choice(pos_map)))
        self.pos_map = pos_map
        self.kinship_pattern = re.compile(r"’\s*(,\s+([♀♂]|\([♀♂]\?\))?({})( etc)?)+".format(
            re_choice(kinship_tags)))
        self.proto_pattern = re.compile(
            r'(\((?P<relno>[0-9])\)\s*)?'
            r'(?P<pl>({}))\s+'
            r'(?P<root>root\s+)?'
            r'(?P<pldoubt>\((POC)?\?\)\s*)?'
            r'(?P<pos>\(({})\)\s*)?'
            r'(?P<fn>\[[0-9]+]\s+)?'
            r'(?P<pfdoubt>\?)?†?\*'.format(
                re_choice(proto_graphemes.keys()),
                re_choice(pos_map.keys())))  # FIXME: record dagger!
        self.volumes = [Volume(self, d, languoids, citation, sources) for d in volumes]

    def is_forms_line(self, line):
        return (re.match('-[A-Z]', line) or  # noqa: W504
                (self.proto_pattern.match(line) or  # noqa: W504
                 self.witness_pattern.match(line) or  # noqa: W504
                 line.strip().startswith(CF_LINE_PREFIX)))
