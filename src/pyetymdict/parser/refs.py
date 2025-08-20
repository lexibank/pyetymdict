"""
Parsing bibliographic and cross references.
"""
import re


CROSS_REF_PATTERN = re.compile(  # #s-<section>-<subsection>-<subsubsection>
    r'(vol(\.|ume)\s*(?P<volume>[1-5])\s*(?P<sep>,|\()\s*)?'
    r'((C|c)h(apter|\.)?\s*(?P<chapter>[0-9]+),\s*)?'
    r'(§\s*(?P<section>[0-9]+))'
    r'(\s*\.\s*(?P<subsection>[0-9]+))?'
    r'(\s*\.\s*(?P<subsubsection>[0-9]+))?')
CROSS_REF_PATTERN_NO_SECTION = re.compile(
    r'(vol(\.|ume)\s*(?P<volume>[1-5])\s*(?P<sep>,|\()\s*)'
    r'((C|c)h(apter|\.)?\s*(?P<chapter>[0-9]+)\s*)'
)
CROSS_REF_PATTERN_PAGES = re.compile(  # -> 1 #p-<page>  or  (vol.4:278)
    r'(vol(\.|ume)\s*(?P<volume>[1-5])\s*(?P<sep>,|\(|\:))\s*(pp?\.?)?\s*(?P<page>[0-9][0-9]+)')

FIGURE_REF_PATTERN = re.compile(r'(?P<type>Table|Figure|Map)\s+(?P<num>[0-9]+(\.[0-9]+)?)')


def key_to_regex(key, in_text=True):
    """
    :param in_text: If `True`, we assume the author name(s) to be part of regular text and only the\
    year (possibly) in brackets.
    """
    #
    # FIXME: match "(after Blust ...)", "(from French-Wright ...)"!
    # (Milke 1968: *paRaRa)
    #
    comps = key.split()
    if len(comps) > 1:
        authors = r'\s+'.join(
            [re.escape(c) if c not in {'&', 'and'} else r'(and|&)' for c in comps[:-1]])
        year = comps[-1]
        if in_text:
            return re.compile(r"{}(['’]s?)?(,\s*eds?,\s*)?\s*\(?{}".format(authors, year))
        return re.compile(
            r"\(((?P<qualifier>after|from)\s+)?{}(['’]s)?(,\s*eds?,\s*)?"
            r"\s*{}(\s*:\s*(?P<pages>[^,;)]+))?\)".format(authors, year))
    if in_text:
        return re.compile(r"(?<=\s){}(?=\s|\.|,)".format(comps[0]))
    return re.compile(r"\({}\)".format(comps[0]))


def search(s, *keys, **kw):
    for key in keys:
        for m in key_to_regex(key, **kw).finditer(s):
            yield key, m.string[m.start():m.end()], m.groupdict()


def repl_ref(srcid, m):
    matched_string = m.string[m.start():m.end()]

    # Figure out if we are already within a link label!
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
        return "[{1}](Source#cldf:{0}) ([{2}](Source#cldf:{0})".format(srcid, a.strip(), y)
    if ' ' in matched_string or all(c.isupper() for c in matched_string):
        return "[{1}](Source#cldf:{0})".format(srcid, matched_string)
    return matched_string  # pragma: no cover
