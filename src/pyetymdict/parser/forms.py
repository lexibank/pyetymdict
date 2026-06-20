"""
Low-level parsing functionality for the pre-processed OCR text of the TloPO volumes.

What about the ca. 50 food plants reconstructions - without witnesses?
"""
import re
import dataclasses
from collections.abc import Generator
from typing import Optional, Literal

from clldutils.text import split_text_with_context

from .spec import FOOTNOTE_PATTERN
from . import kinship

__all__ = [
    'parse_protoform', 'strip_comment', 'strip_footnote_reference', 'iter_glosses'
]

StartEndType = Literal['start', 'end']

# [Panthera leo]
species_pattern = re.compile(r'\s*\[(?P<species>[A-Z]([a-z]+|\.)\s+[a-z]+\.?)]\s*$')
# (iv)
gloss_number_pattern = re.compile(
    r'\s*\(\s*(?P<qualifier>(i|1|present meaning|2|3|4|5|ii|iii|iv)(\.[0-9])?)\s*\)\s*')
# [Sg=1]
morpheme_gloss_pattern = re.compile(r'\[(?P<g>[A-Za-z:\-= 1-3/.()?,]+)]')


def strip_footnote_reference(
        rem: str,
        start_only: bool = False,
) -> tuple[str, Optional[str], Optional[StartEndType]]:
    """
    Detect and extract footnote reference from string.

    >>> strip_footnote_reference('text [2]')
    ('text', '2', 'end')
    """
    m = FOOTNOTE_PATTERN.match(rem)
    if m:
        return rem[m.end():].strip(), m.group('fn'), 'start'
    if not start_only:
        m = FOOTNOTE_PATTERN.search(rem)
        if m and m.end() == len(rem):  # strip footnote from end.
            return rem[:m.start()].strip(), m.group('fn'), 'end'
    return rem, None, None


def strip_comment(s: str, position: StartEndType = 'end') -> tuple[Optional[str], str]:
    """
    >>> strip_comment('text (comment)')
    ('comment', 'text')
    """
    def _match_brace(text, brace, other):
        cmt, level = [], 1
        for i, c in enumerate(text):
            if c == brace:
                level += 1
            elif c == other:
                level -= 1
                if level == 0:
                    break
            cmt.append(c)
        else:
            raise ValueError(s)  # pragma: no cover
        return cmt, i

    if position == 'end':
        # Find ( on matching level:
        if s.endswith(')'):
            assert '(' in s, s
            cmt, i = _match_brace(reversed(s[:-1]), ')', '(')
            return ''.join(reversed(cmt)).strip(), s[:-i-2].strip()  # noqa: E226
    else:
        assert position == 'start'
        if s.startswith('('):
            cmt, i = _match_brace(s[1:], '(', ')')
            return ''.join(cmt).strip(), s[i+2:].strip()  # noqa: E226
    return None, s


def _parse_form(f: str, phonemes):  # pylint: disable=R0912
    in_bracket, in_sbracket, in_abracket = False, False, False
    form, length = '', 0
    tilde = False
    for c in f:  # FIXME: don't try to pseudo-segment here.
        if c == '(':
            in_bracket = True
        elif c == ')':
            in_bracket = False
        elif c == '[':
            in_sbracket = True
        elif c == ']':
            in_sbracket = False
        elif c == '⟨':
            in_abracket = True
        elif c == '⟩':
            assert in_abracket, f
            in_abracket = False
        elif c == '~':
            tilde = True
        elif c == '*':  # Another protoform must be introduced as variant, with a ~.
            assert tilde, (f, phonemes)
            tilde = False
            length += len(c)
            continue
        elif c == ',':
            if not (in_bracket or in_sbracket):
                length += 1
                break
        elif c == ' ':
            break
        elif c in phonemes:
            pass
        else:
            raise ValueError(c, f, phonemes)  # pragma: no cover
        length += len(c)
        form += c
    return form, length


def parse_protoform(
        f: str,
        phonemes,
        allow_rem: bool=True,
) -> tuple[list[str], str]:
    """
    Assumes a string `f` immediately following a protoform marker `*`. Then consumes graphemes as
    long as they match the grapheme inventory for the proto-language.

    (x)       it cannot be determined whether x was present
    (x,y)     either x or y was present
    [x]       the item is reconstructable in two forms, one with and one without x
    [x,y]     the item is reconstructable in two forms, one with x and one with y
    x-y       x and y are separate morphemes
    x-        x takes an enclitic or a suffix
    ⟨x⟩       x is an infix

    Multi-word forms must be enclosed in pipes, e.g. |multi word|.

    >>> parse_protoform('bubun', 'bun')
    (['bubun'], '')
    >>> parse_protoform('bubun, *bun', 'bun')
    (['bubun', 'bun'], '')
    >>> parse_protoform('|bu bun|', 'bun')
    (['bu bun'], '')
    """
    if f.startswith('|'):  # multi-word protoform
        # Make sure there's a matching "closing" pipe:
        assert '|' in f[1:], f
        f, _, rem = f[1:].partition('|')
        forms = [' '.join(
            parse_protoform(word, phonemes, allow_rem=False)[0][0]
            for word in f.strip().split())]
        rem = rem.strip()
        if rem.startswith(',') and rem[1:].strip().startswith('*'):
            # rem may start with ", *" meaning there's another protoform!
            words = rem[1:].strip()[1:].split()
            forms.append(parse_protoform(words[0], phonemes, allow_rem=False)[0][0])
            rem = ' '.join(words[1:])
        if rem.startswith('*'):
            words = rem[1:].split()
            forms.append(parse_protoform(words[0], phonemes, allow_rem=False)[0][0])
            rem = ' '.join(words[1:])
        return (forms, rem.strip())

    form, length = _parse_form(f, phonemes)
    forms = [form]
    rem = f[length:].strip()
    if rem:
        assert allow_rem, f
        if rem.startswith('or '):
            assert rem[2:].strip().startswith('*')
            rem = rem[2:].strip()

        if rem.startswith('*'):
            # FIXME: add pos spec to forms!
            # PWOc (N LOC) *pa, (ADV) *qa-pa ‘to one’s left when facing the sea’
            f2, rem = parse_protoform(rem[1:].strip(), phonemes)
            forms.extend(f2)
        if rem:
            # The next token is a comment or source or a gloss or a doubt marker or a footnote.
            # This must be handled by the caller.
            assert rem[0] in "('‘?[", f
    return forms, rem


def get_quotes(s: str) -> str:
    """Detect and return the type of quotes used in s."""
    #
    # FIXME: Should be handled more predictably!
    #
    return "‘’" if "‘" in s and "'" not in s else "''"


@dataclasses.dataclass
class RawGloss:  # pylint: disable=R0902
    """
    ''
    """
    gloss: Optional[str] = None
    morpheme_gloss: Optional[str] = None
    kinship_gloss: Optional[str] = None
    pos: Optional[str] = None
    species: Optional[str] = None
    fn: Optional[str] = None
    comments: list[str] = dataclasses.field(default_factory=list)
    qualifier: Optional[str] = None
    uncertain: bool = False
    sources: Optional[list] = dataclasses.field(default_factory=list)

    @staticmethod
    def replace_apostrophe(s: str, quotes):
        """Replace quotes used as apostrophe to not confuse the gloss parsing."""
        return re.sub(
            r"(?P<c>[a-z.]){}s".format(quotes[1]),  # pylint: disable=C0209
            lambda m: m.group('c') + "__s", s)

    def check(self):
        """Make sure none of the apostrophe-replacement markers made it into data."""
        assert not any(isinstance(v, str) and '__s' in v for v in dataclasses.astuple(self)), self

    def parse_pos(self, rem: str, pos_pattern: re.Pattern[str]) -> str:
        """Parse a part-of-speech tag."""
        m = pos_pattern.match(rem)
        if m:
            self.pos = m.group('pos')
            rem = rem[m.end():].strip()
        return rem

    def parse_qualifier(self, rem: str) -> str:
        """Parse a qualifier. Typically something like a gloss number."""
        m = gloss_number_pattern.match(rem)
        if m:
            self.qualifier = m.group('qualifier')
            rem = rem[m.end():].strip()
        return rem

    def parse_uncertain(self, rem: str) -> str:
        """Parse an uncerrtainty marker."""
        if rem.startswith('?'):
            assert self.uncertain is False
            self.uncertain = True
            rem = rem[1:].strip()
        elif rem.startswith('(?)'):
            assert self.uncertain is False
            self.uncertain = True
            rem = rem[3:].strip()
        return rem

    def parse_species(self, rem):
        """Parse a species name in binomial nomenclature."""
        m = species_pattern.search(rem)
        if m:
            self.species = m.group('species')
            rem = rem[:m.start()].strip()
        return rem

    def parse_comments(self, rem: str) -> str:
        """consume up to two comments from the end."""
        comment, rem = strip_comment(rem.strip())
        if comment:
            self.comments.append(comment)
        comment, rem = strip_comment(rem.strip())
        if comment:
            self.comments.append(comment)
            self.comments = list(reversed(self.comments))
        return rem

    def parse_morpheme_gloss(self, rem: str) -> str:
        """Morpheme glosses or kinship tags."""
        m = morpheme_gloss_pattern.match(rem)
        if m:
            self.morpheme_gloss = m.group('g')
            try:
                self.fn = str(int(self.morpheme_gloss))
                self.morpheme_gloss = None
            except ValueError:
                pass
            return rem[m.end():].strip()

        m = kinship.search(rem)
        if m:
            self.kinship_gloss = ' '.join(
                s.strip() for s in m.string[m.start() + 1:m.end()].split(',') if s.strip())
            rem = rem[:m.start() + 1] + rem[m.end():]
        return rem


def iter_glosses(
        s: str,
        pos_pattern: re.Pattern[str],
) -> Generator[RawGloss, None, None]:
    """Detect and yield gloss instances from s."""
    quotes = get_quotes(s)

    # Replace quotes used as apostrophe to not confuse the gloss parsing.
    rem = RawGloss.replace_apostrophe(s, quotes)

    chunks = split_text_with_context(rem, ";", brackets={"(": ")", "'": "'", "‘": "’"})
    if len(chunks) > 1:
        # make sure not to match "';" in brackets!
        for chunk in chunks:
            yield from iter_glosses(chunk, pos_pattern)
        return

    gloss = RawGloss()
    rem = gloss.parse_uncertain(rem)
    rem = gloss.parse_morpheme_gloss(rem)
    rem = gloss.parse_pos(rem, pos_pattern)
    rem = gloss.parse_qualifier(rem)

    m = re.fullmatch(r"\[([^]]+)]", rem)
    if m:  # A catch-all for stuff that's enclosed in square brackets.
        gloss.morpheme_gloss = m.group(1)
        rem = ''

    if not gloss.fn:
        rem, gloss.fn, _ = strip_footnote_reference(rem)

    rem = gloss.parse_uncertain(rem)
    rem = gloss.parse_comments(rem)
    rem = gloss.parse_species(rem)

    if rem:
        # We parsed all the special stuff. So the remainder should be just a string enclosed in the
        # expected quotes with no other start quotes appearing inside.
        assert rem.startswith(quotes[0]) and rem.endswith(quotes[1]), (s, gloss.pos, rem)
        assert quotes[0] not in rem[1:-1], rem
        text = rem[1:-1].strip()
        gloss.gloss = text.replace("__s", quotes[1] + 's') if text else text

    if any(bool(a) for a in dataclasses.astuple(gloss)):
        gloss.check()
        yield gloss
