"""
Parsing bibliographic references and cross references.
"""
import re
import functools

from .spec import (
    CROSS_REF_PATTERN, CROSS_REF_PATTERN_PAGES, CROSS_REF_PATTERN_NO_SECTION, FIGURE_REF_PATTERN,
    CROSS_REF_PATTERN_MULTI_SECTIONS, VolumeDir,
)
from .util import cldf_source_link, cldf_contribution_link


def key_to_regex(key: str, in_text: bool = True) -> re.Pattern[str]:
    """
    :param in_text: If `True`, we assume the author name(s) to be part of regular text and only the\
    year (possibly) in brackets.
    """
    comps = key.split()
    if len(comps) > 1:
        authors = r'\s+'.join(
            [re.escape(c) if c not in {'&', 'and'} else r'(and|&)' for c in comps[:-1]])
        year = comps[-1]
        if in_text:
            return re.compile(r"{}(['’]s?)?(,\s*eds?,\s*)?\s*\(?{}".format(  # pylint: disable=C0209
                authors, year))
        return re.compile(
            r"\(((?P<qualifier>after|from)\s+)?{}(['’]s)?(,\s*eds?,\s*)?"  # pylint: disable=C0209
            r"\s*{}(\s*:\s*(?P<pages>[^,;)]+))?\)".format(  # pylint: disable=C0209
                authors, year))
    if in_text:
        return re.compile(r"(?<=\s){}(?=\s|\.|,)".format(comps[0]))  # pylint: disable=C0209
    return re.compile(r"\({}\)".format(comps[0]))  # pylint: disable=C0209


def repl_ref(srcid: str, m: re.Match[str]) -> str:
    """Replace references matching `srcid` with a CLDF Markdown link."""
    matched_string: str = m.string[m.start():m.end()]

    # Figure out if we are already within a link label, by checking if there's an unmatched
    # opening square bracket within 30 characters.
    for i in range(30):
        c = None
        try:
            c = m.string[m.start() - i - 1]
        except IndexError:
            break
        if c == ']':
            break
        if c == '[':
            # We are in a link label! Don't replace anything!
            return matched_string

    if '(' in matched_string:
        a, _, y = matched_string.partition('(')
        # Note: The closing brace is not part if the match.
        return f"{cldf_source_link(srcid, a.strip())} ({cldf_source_link(srcid, y)}"
    if ' ' in matched_string or all(c.isupper() for c in matched_string):
        return f"{cldf_source_link(srcid, matched_string)}"
    return matched_string  # pragma: no cover


def replace_cross_refs(
        text: str,
        volume_number: str,
        chapter: str,
        chapter_pages: dict[str, tuple[int, int]],
) -> str:
    """
    Replace cross-references in text to other sections with Markdown links.

    vol3:ch.11 (§§2.1, 2.4 and 3.5 respectively).
    vol4:chapter 8, §§5 and 6). More restrictive expressions are often coined by adding a

    """
    def mrepl(m: re.Match[str]) -> str:
        matched = m.string[m.start():m.end()]
        chapterlabel = None
        if m.group('volume'):
            if not m.group('chapter'):  # A volume is referenced but no specific chapter.
                return matched
            cid = f"{m.group('volume')}-{m.group('chapter')}"
            chapterlabel = f"Vol. {m.group('volume')}, ch. {m.group('chapter')}"
        else:
            if m.group('chapter'):
                cid = f"{volume_number}-{m.group('chapter')}"
                chapterlabel = f"Ch. {m.group('chapter')}"
            else:
                cid = f'{volume_number}-{chapter}'

        f = [part.strip() for part in m.group('fromsection').split('.') if part.strip()]
        t = [part.strip() for part in m.group('tosection').split('.') if part.strip()]
        if len(t) < len(f):
            t = f[:len(f) - len(t)] + t

        if len(f) > 3:
            return matched

        res = ''
        if chapterlabel:
            res += cldf_contribution_link(cid, label=chapterlabel) + ' '

        res += '§§{}-{}'.format(  # pylint: disable=C0209
            cldf_contribution_link(cid, label='.'.join(f), anchor='-'.join(['s'] + f)),
            cldf_contribution_link(cid, label='.'.join(t), anchor='-'.join(['s'] + t)),
        )
        if m.group('tosection').endswith('.'):
            res += '.'
        return res

    res = CROSS_REF_PATTERN_MULTI_SECTIONS.sub(mrepl, text)

    def repl(m: re.Match[str]) -> str:
        matched = m.string[m.start():m.end()]
        if m.string[:m.start()].endswith('['):
            # We are already in a link!
            return matched
        cid, anchor = '', ''
        if m.group('volume'):
            if not m.group('chapter'):
                return matched
            cid = f"{m.group('volume')}-{m.group('chapter')}"
        else:
            if m.group('chapter'):
                cid = f"{volume_number}-{m.group('chapter')}"
            else:
                cid = f'{volume_number}-{chapter}'
        if 'section' in m.groupdict():
            if m.group('section'):
                anchor = f"s-{m.group('section')}"
                if m.group('subsection'):
                    anchor += f"-{m.group('subsection')}"
                    if m.group('subsubsection'):
                        anchor += f"-{m.group('subsubsection')}"

        return cldf_contribution_link(cid, label=matched, anchor=anchor)

    res = CROSS_REF_PATTERN.sub(repl, res)
    res = CROSS_REF_PATTERN_NO_SECTION.sub(repl, res)

    def prepl(m: re.Match[str]) -> str:
        page = int(m.group('page'))
        for cid, (s, e) in chapter_pages.items():
            v, _, _ = cid.partition('-')
            if v == m.group('volume') and s <= page <= e:
                break
        else:
            return m.string[m.start():m.end()]
        return cldf_contribution_link(
            cid,
            label=f"vol.{m.group('volume')}{m.group('sep')}{m.group('page')}",
            anchor=f"p-{m.group('page')}"
        )

    return CROSS_REF_PATTERN_PAGES.sub(prepl, res)


def replace_figure_refs(text: str, volume_number: str) -> str:
    """
    Replaces references to figures, maps or tables in text with proper Markdown links.
    """
    def repl(m: re.Match[str]) -> str:
        label = m.string[m.start():m.end()]
        if m.string[:m.start()].strip()[-1] in {':', '_'}:
            return label
        if m.string[m.end():].strip().startswith(':'):
            return label
        a = VolumeDir.figure_id(volume_number, m.group('type'), m.group('num'))
        return f'[{label}](#{a})'

    return FIGURE_REF_PATTERN.sub(repl, text)


def replace_source_refs(text: str, source_pattern_dict: dict[str, re.Pattern[str]]):
    """
    Replaces source references in text with proper CLDF Markdown links.
    """
    # First step: Replace proper author-year style refs.
    for srcid, pattern in source_pattern_dict.items():
        text = pattern.sub(functools.partial(repl_ref, srcid), text)

    # Second step: Look for trailing years after identified source refs to handle cases like
    # "Meier 1998, 2009".
    sep = r',\s*|\s+and\s+'  # We look for comma or " and " separated years.
    m = re.compile(r"\(Source#cldf:([^)]+)\)((" + sep + r")[0-9]+([\-–][0-9]+)?[a-z]?)+")

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
            cyear = year.replace('-', '').replace('–', '')
            if author + cyear in source_pattern_dict:
                res += f', {cldf_source_link(author + cyear, year)}'
            else:
                res += f', {year}'
        return res

    return m.sub(repl, text)
