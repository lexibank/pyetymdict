"""
Low-level parsing functionality for the pre-processed OCR text of the TloPO volumes.

What about the ca. 50 food plants reconstructions - without witnesses?

comparing with data from Mae:

>>> s1 = "ūŋ-wūŋ"
>>> s2 = "ūŋ-wūŋ"
>>> len(s1)
8
>>> len(s2)
6
>>> import unicodedata
>>> unicodedata.normalize('NFC', s1) == s2
True
>>> unicodedata.normalize('NFD', s2) == s1
True
"""
import re
import typing
import unicodedata

from clldutils.text import split_text_with_context

from .util import fn_pattern

__all__ = [
    'iter_graphemes', 'parse_protoform', 'strip_comment', 'strip_footnote_reference',
    'iter_glosses'
]

species_pattern = re.compile(r'\s*\[(?P<species>[A-Z]([a-z]+|\.)\s+[a-z]+\.?)]\s*$')
gloss_number_pattern = re.compile(
    r'\s*\(\s*(?P<qualifier>(i|1|present meaning|2|3|4|5|ii|iii|iv)(\.[0-9])?)\s*\)\s*')
morpheme_gloss_pattern = re.compile(r'\[(?P<g>[A-Za-z:\-= 1-3/.()?,]+)]')


def strip_footnote_reference(rem, start_only=False):
    fn, position = None, None
    m = fn_pattern.match(rem)
    if m:
        fn = m.group('fn')
        rem = rem[m.end():].strip()
        position = 'start'
    elif not start_only:
        m = fn_pattern.search(rem)
        if m and m.end() == len(rem):  # strip footnote from end.
            fn = m.group('fn')
            rem = rem[:m.start()].strip()
            position = 'end'
    return rem, fn, position


def strip_comment(s, position='end'):
    if position == 'end':
        # Find ( on matching level:
        if s.endswith(')'):
            cmt, level = [], 1
            assert '(' in s, s
            for i, c in enumerate(reversed(s[:-1])):
                if c == ')':
                    level += 1
                elif c == '(':
                    level -= 1
                    if level == 0:
                        break
                cmt.append(c)
            else:
                raise ValueError(s)  # pragma: no cover
            return ''.join(reversed(cmt)).strip(), s[:-i-2].strip()  # noqa: E226
    else:
        assert position == 'start'
        if s.startswith('('):
            cmt, level = [], 1
            for i, c in enumerate(s[1:]):
                if c == '(':
                    level += 1
                elif c == ')':
                    level -= 1
                    if level == 0:
                        break
                cmt.append(c)
            else:
                raise ValueError(s)  # pragma: no cover
            return ''.join(cmt).strip(), s[i+2:].strip()  # noqa: E226
    return None, s


def iter_graphemes(s):
    g, left = '', ''
    for c in s:
        cat = unicodedata.name(c).split()[0]
        if cat not in {'MODIFIER', 'COMBINING'}:  # a letter.
            if g:
                yield g
            if left:  # concatenate whatever modifiers are left.
                g = left + c
                left = ''
            else:
                g = c
        else:
            if cat == 'MODIFIER' and g and g in 'iau':  # Modifiers apply from the left.
                left += c
            elif g and any(unicodedata.category(cc) == 'Ll' for cc in g):  # We have a letter.
                g += c
            else:
                left += c
    if g:
        yield g


def parse_protoform(f, phonemes, allow_rem=True) -> typing.Tuple[typing.List[str], str]:
    """
    Assumes a string `f` immediately following a protoform marker `*`. Then consumes graphemes as
    long as they match the grapheme inventory for the proto-language.

    (x)       it cannot be determined whether x was present
    (x,y)     either x or y was present
    [x]       the item is reconstructable in two forms, one with and one without x
    [x,y]     the item is reconstructable in two forms, one with x and one with y
    x-y       x and y are separate morphemes
    x-        x takes an enclitic or a suffix
    <x>       x is an infix
    """
    if f.startswith('|'):  # multi-word protoform
        assert '|' in f[1:], f
        f, _, rem = f[1:].partition('|')
        forms = [' '.join(
            parse_protoform(word, phonemes, allow_rem=False)[0][0]
            for word in f.strip().split())]
        # FIXME: rem may start with ", *" meaning there's another protoform!
        rem = rem.strip()
        if rem.startswith(',') and rem[1:].strip().startswith('*'):
            words = rem[1:].strip()[1:].split()
            forms.append(parse_protoform(words[0], phonemes, allow_rem=False)[0][0])
            rem = ' '.join(words[1:])
        if rem.startswith('*'):
            words = rem[1:].split()
            forms.append(parse_protoform(words[0], phonemes, allow_rem=False)[0][0])
            rem = ' '.join(words[1:])
        return (forms, rem.strip())

    in_bracket, in_sbracket, in_abracket = False, False, False
    form, length = '', 0
    tilde = False
    for c in iter_graphemes(f):
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
        elif c == '*':
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
            # FIXME: handle the remainder!
            # next token is a comment or source or a gloss or a doubt marker or a footnote.
            assert rem[0] in "('‘?[", f
    return forms, rem


def get_quotes(s):
    return "‘’" if "‘" in s else "''"


class GlossDict(typing.TypedDict):
    gloss: typing.Optional[str]
    morpheme_gloss: typing.Optional[str]
    pos: typing.Optional[str]
    species: typing.Optional[str]
    fn: typing.Optional[str]
    comments: list
    qualifier: typing.Optional[str]
    uncertain: typing.Optional[bool]
    sources: typing.Optional[list]


def iter_glosses(s, pos_pattern, kinship_pattern=None) -> typing.Generator[GlossDict, None, None]:
    quotes = get_quotes(s)

    gloss, pos, qualifier, fn, uncertain, comments = None, None, None, None, False, []
    species, morpheme_gloss = None, None
    rem = s
    rem = re.sub(r"(?P<c>[a-z.]){}s".format(quotes[1]), lambda m: m.group('c') + "__s", rem)

    chunks = split_text_with_context(rem, ";", brackets={"(": ")", "'": "'", "‘": "’"})
    if len(chunks) > 1:
        # make sure not to match "';" in brackets!
        for chunk in chunks:
            yield from iter_glosses(chunk, pos_pattern, kinship_pattern)
        return

    if rem.startswith('(?)'):
        uncertain = True
        rem = rem[3:].strip()

    m = morpheme_gloss_pattern.match(rem)
    if m:
        morpheme_gloss = m.group('g')
        try:
            fn = str(int(morpheme_gloss))
            morpheme_gloss = None
        except ValueError:
            pass
        rem = rem[m.end():].strip()
    else:
        if kinship_pattern:
            m = kinship_pattern.search(rem)
            if m:
                morpheme_gloss = ' '.join(
                    [s.strip() for s in m.string[m.start() + 1:m.end()].split(',') if s.strip()])
                rem = rem[:m.start() + 1] + rem[m.end():]

    m = pos_pattern.match(rem)
    if m:
        pos = m.group('pos')
        rem = rem[m.end():].strip()

    m = gloss_number_pattern.match(rem)
    if m:
        qualifier = m.group('qualifier')
        rem = rem[m.end():].strip()

    m = re.fullmatch(r"\[([^]]+)]", rem)
    if m:  # A catch-all for stuff that's enclosed in square brackets.
        morpheme_gloss = m.group(1)
        rem = ''

    if not fn:
        rem, fn, fnpos = strip_footnote_reference(rem)

    if rem.startswith('?'):
        uncertain = True
        rem = rem[1:].strip()

    # consume up to two comments from the end.
    comment, rem = strip_comment(rem.strip())
    if comment:
        comments.append(comment)
    comment, rem = strip_comment(rem.strip())
    if comment:
        comments.append(comment)
        comments = reversed(comments)

    m = species_pattern.search(rem)
    if m:
        species = m.group('species')
        rem = rem[:m.start()].strip()

    if rem:
        assert rem.startswith(quotes[0]) and rem.endswith(quotes[1]), (s, pos, rem)
        assert quotes[0] not in rem[1:-1], rem
        gloss = rem[1:-1].strip()

    res = GlossDict(
        pos=pos,
        species=species,
        gloss=gloss.replace("__s", quotes[1] + 's') if gloss else gloss,
        morpheme_gloss=morpheme_gloss,
        fn=fn,
        comments=comments or [],
        qualifier=qualifier,
        uncertain=bool(uncertain))
    if any(res[k] for k in res.keys()):
        yield res
