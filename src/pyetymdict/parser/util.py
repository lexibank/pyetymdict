"""
Utilities
"""
import re
import functools
import collections
from collections.abc import Iterable


def cldf_markdown_link(component: str, id_: str, label: str = None, anchor: str = None) -> str:
    """A CLDF Markdown link as string"""
    anchor = '?anchor=' + anchor if anchor else ''
    label = label or id_
    return f"[{label}]({component}{anchor}#cldf:{id_})"


cldf_source_link = functools.partial(cldf_markdown_link, 'Source')
cldf_contribution_link = functools.partial(cldf_markdown_link, 'ContributionTable')
cldf_media_link = functools.partial(cldf_markdown_link, 'MediaTable')


def polish_text(text):
    """Normalize ellipsis, make sure asterisks are escaped to make them work in Markdown."""
    text = re.sub(r'\s*\.\s*\.\s*\.\s*', ' … ', text)
    return text.replace('*', '&ast;')


def markdown_escape(s: str) -> str:
    """Escape characters that have a special meaning in Markdown."""
    for k, v in {
        "*": "&ast;",
        "[": "&#91;",
        "]": "&#93;",
    }.items():
        s = s.replace(k, v)
    return s


def re_choice(items: Iterable[str]) -> str:
    """Turn items into a list of alternatives suitable for a regex pattern."""
    return r'|'.join(re.escape(i) for i in sorted(items, key=lambda ii: (-len(ii), ii)))


def strip_morphemeseparator(f: str) -> str:
    """Remove morpheme separators from start or end of string."""
    if f.startswith('-'):
        return '-' + strip_morphemeseparator(f[1:])
    if f.endswith('-'):
        return strip_morphemeseparator(f[:-1]) + '-'
    return f.replace('-', '')


def variants(f: str) -> list[str]:  # pylint: disable=R0912
    """
    Enumerate the form variants implied by bracket-notation in a reconstructed form.

    a(x)b -> axb, ab
    a(x,y)b -> axb, ayb
    a((x,y))b -> axb, ayb, ab
    """
    v = []
    level = 0
    # Prefix is everything up to a bracket, bracketed is stuff in brackets (including the brackets):
    prefix, bracketed = '', ''
    i = -1
    for i, c in enumerate(f):
        if (level == 0) and (c not in '[('):
            prefix += c
            continue

        if c in '[(':
            level += 1
            if level > 1:
                bracketed += c
            continue

        if c in ')]':
            level -= 1
            if level == 0:
                break  # The remainder has to be dealt with recursively!
            bracketed += c
            continue

        bracketed += c

    if bracketed:
        if any(cc in bracketed for cc in '(['):  # Need to recurse.
            assert '),' not in bracketed, "Comma in nested brackets."
            v = [prefix + vv for vv in variants(bracketed)]
            if prefix:
                v.append(prefix)
        else:
            if ',' in bracketed:  # Variants.
                for s in bracketed.split(','):
                    v.append(prefix + s.strip())
            else:  # Optional part.
                v.append(prefix)
                v.append(prefix + bracketed)
    elif prefix:
        v.append(prefix)

    rem = f[i + 1:]
    if rem:
        v = [vv + yy for vv in v for yy in variants(rem)]

    assert len(set(v)) == len(v), v
    return [strip_morphemeseparator(vv) for vv in sorted(v)]


def nested_toc(items: Iterable[tuple[int, str, str]]) -> list[tuple[str, str, list]]:
    """
    Turn section titles with level into a nested structure.
    """
    def d2l(sid, title, children):
        return (
            sid,
            title,
            [d2l('-'.join([sid, ssid]) if sid else ssid, i[0], i[1])
             for ssid, i in children.items()] if children else [])

    sections = ('', collections.OrderedDict())
    for level, sid, title in items:
        keys = sid.split('-')
        tk, keys = '-'.join(keys[:2]), keys[2:]
        keys = [tk] + keys
        assert len(keys) == level

        node = sections
        try:
            for key in keys[:-1]:
                node = node[1][key]

            node[1][keys[-1]] = (title, collections.OrderedDict())
        except KeyError:  # pragma: no cover
            print(level, sid, title)
            raise

    return d2l('', sections[0], sections[1])[2]
