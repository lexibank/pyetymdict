"""
Parse line-level markup.
"""
import re
import functools

from tabulate import tabulate

from .util import fn_pattern

CF_LINE_PREFIX = 'cf. also'

h1_pattern = re.compile(
    r'(?P<a>\d+)\.?\s+(?P<title>([_‘♂])?[A-Z].+)')
h2_pattern = re.compile(
    r'(?P<a>\d+)(\.|\s)\s*(?P<b>\d+)\.?\s+(?P<title>([_‘♂])?[A-Z].+)')
h3_pattern = re.compile(
    r'(?P<a>\d+)(\.|\s)\s*(?P<b>\d+)(\.|\s)\s*(?P<c>\d+)\.?\s+(?P<title>([_‘♂])?[*mA-Z].+)')
h4_pattern = re.compile(
    r'(?P<a>\d+)(\.|\s)\s*(?P<b>\d+)(\.|\s)\s*(?P<c>\d+)(\.|\s)\s*(?P<d>\d+)\.?\s+'
    r'(?P<title>([_‘♂])?[*A-Z].+)')
h5_pattern = re.compile(
    r'(?P<a>\d+)(\.|\s)\s*(?P<b>\d+)(\.|\s)\s*(?P<c>\d+)(\.|\s)\s*(?P<d>\d+)(\.|\s)\s*'
    r'(?P<e>\d+)\.?\s+(?P<title>([_‘♂])?[*A-Z].+)')
_pageno_right_pattern = re.compile(r'(\x0c|###newpage###)\s+\D+(?P<no>\d+)')
_pageno_left_pattern = re.compile(r'(\x0c|###newpage###)(?P<no>\d+)\s+\D+')

map_pattern = re.compile(r'(?P<type>Map|Figure)\s+(?P<num>[0-9]+[a-z]*(\.[0-9]+)?):')


def match_pageno(line):
    m = _pageno_left_pattern.fullmatch(line) or _pageno_right_pattern.fullmatch(line)
    if m:
        return m.group('no')


def formblock(parser, lines):
    reg, cfs = [], []
    in_cf, cf, cfspec = False, [], None

    for line in lines:
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


def igt_group(parser, lines):
    return lines


def make_paragraph(lines, voldir) -> str:
    """
    Lines starting with "|" are a quote.
    If first line is __ul__ ...
    If firts line is __pre__ ...
    Figure ...
    Map ...
    """
    m = re.match(r'\:\s+\_*Table\s+(?P<num>[0-9\.]+)\_*', lines[0])
    if m:
        return '<a id="table-{}"> </a>\n\n{}'.format(m.group('num'), '\n'.join(lines))
    if lines[0].startswith('|'):
        return '> {}'.format(' '.join(line.lstrip('|').strip() for line in lines))
    if lines[0] == '__blockquote__':
        return '> {}'.format(' '.join(line.strip() for line in lines[1:]))
    if lines[0] == '__formgroup__':
        return '\n'.join('' if line.strip() == '#' else line for line in lines[1:])
    if lines[0] == '__ul__':
        return '\n'.join('- {}'.format(line.strip()) for line in lines[1:])
    if lines[0] == '__block__':
        return '\n'.join('' if line.strip() == '#' else line for line in lines[1:])
    if len(lines) > 1 and lines[1].strip().startswith(':'):
        # A definition list
        return '\n'.join(lines)
    if lines[0] == '__pre__':
        return "```\n{}\n```".format('\n'.join(lines[1:]))
    if lines[0] == '__table__':
        return tabulate(
            [[s.strip() or ' ' for s in ln.split('|')] for ln in lines[2:]],
            headers=[s.strip() or ' ' for s in lines[1].split('|')],
            tablefmt='pipe')
    if lines[0] == '__tablenh__':
        return tabulate(
            [[s.strip() or ' ' for s in ln.split('|')] for ln in lines[1:]],
            headers=[' '] * len(lines[1].split('|')),
            tablefmt='pipe')
    # __formset__, figure, map. __html__
    m = map_pattern.match(lines[0])
    if m:  # Turn figures and maps into CLDF Markdown links referencing MediaTable items.
        mtype = 'map' if m.group('type').lower() == 'map' else 'fig'
        fid = '{}-{}-{}'.format(
            mtype,
            voldir.name.replace('vol', ''),
            m.group('num').replace('.', '_'))
        p = voldir / 'maps' / '{}_{}.png'.format(mtype, m.group('num'))
        if p.exists():
            caption = ' '.join(ln.strip() for ln in lines)
            label, _, caption = caption.partition(':')
            return """\
<a id="{}"> </a>

[__{}:__ {}](MediaTable#cldf:{})

""".format(fid, label, caption.strip(), fid)
    return ' '.join(ln.strip() for ln in lines)


def make_chapter(paras):
    """
    If first line starts with footnote pattern, it's the footnote content.
    """
    regular, endnotes = [], []
    for para in paras:
        if fn_pattern.match(para):
            endnotes.append(fn_pattern.sub(lambda m: '[^{}]:'.format(m.group('fn')), para, count=1))
        else:
            regular.append(fn_pattern.sub(lambda m: '[^{}]'.format(m.group('fn')), para))
    return '\n\n'.join(regular + ['\n## Notes'] + endnotes)


def iter_chapters(lines, voldir):
    from .forms import strip_footnote_reference

    chapter, toc, para = [], [], []
    in_chapter = None
    for line in lines:
        m = h1_pattern.match(line)
        if m:
            if in_chapter:
                yield in_chapter, make_chapter(chapter), toc
            chapter, toc, in_chapter = [], [], m.group('a')
            continue

        if not in_chapter:
            continue

        pageno = match_pageno(line)
        if pageno:  # Page number line.
            chapter.append('\n<a id="p-{}"></a>'.format(pageno))
            continue

        header = False
        for level, pattern, link_format, number_format in [
            (1, h2_pattern, 's-{b}', '{b}.'),
            (2, h3_pattern, 's-{b}-{c}', '{b}.{c}.'),
            (3, h4_pattern, 's-{b}-{c}-{d}', '{b}.{c}.{d}.'),
            (4, h5_pattern, None, '{b}.{c}.{d}.{e}.'),
        ]:
            m = pattern.match(line)
            if m:
                number = number_format.format(**m.groupdict())
                title = '{title}'.format(**m.groupdict())
                if link_format:
                    link = link_format.format(**m.groupdict())
                    chapter.append('\n<a id="{}"></a>\n\n{} {} {}\n'.format(
                        link, (level + 1) * '#', number, title))
                    toc.append((level, link, strip_footnote_reference(title)[0]))
                else:
                    chapter.append('\n{} {} {}\n'.format((level + 1) * '#', number, title))
                header = True
                break
        if header:
            continue

        if not line.strip():
            if para:
                chapter.append(make_paragraph(para, voldir))
                para = []
        else:
            para.append(line)

    if para:
        chapter.append(make_paragraph(para, voldir))
    yield in_chapter, make_chapter(chapter), toc


def extract_blocks(parser, lines, factory=formblock, start='<', end='>'):
    pageno = -1
    block = []
    h1, h2, h3 = None, None, None
    in_block = False

    new_lines = []
    for i, line in enumerate(lines, start=1):
        m = match_pageno(line)
        if m:  # Page number line.
            pageno = int(m)
            assert not in_block, pageno
            new_lines.append(line)
            continue

        if not line:  # Empty line.
            if not end and in_block:  # implicit end of block
                assert block, i
                etymon_id = yield h1, h2, h3, pageno, factory(parser, block)
                in_block = False
                new_lines.append(etymon_id)
                new_lines.append('')
                continue

            if not in_block:
                new_lines.append(line)
            continue

        if line == start:  # Etymon start marker.
            assert not in_block, i
            in_block = True
            block = []
            continue
        if end and line == end:  # Etymon end marker.
            assert block, i
            etymon_id = yield h1, h2, h3, pageno, factory(parser, block)
            assert in_block, i
            in_block = False
            new_lines.append(etymon_id)
            continue

        if not in_block:
            m = h1_pattern.match(line)
            if m:
                h1 = (m.group('a'), m.group('title'))
                h2, h3 = None, None
            else:
                m = h2_pattern.match(line)
                if m:
                    assert h1, line
                    assert m.group('a') == h1[0], (line, h1)
                    h2 = (m.group('b'), m.group('title'))
                    h3 = None
                else:
                    m = h3_pattern.match(line)
                    if m:
                        assert h2 and m.group('b') == h2[0], line
                        h3 = (m.group('c'), m.group('title'))
            new_lines.append(line)
        else:
            block.append(line)
    return new_lines


extract_etyma = extract_blocks
extract_igts = functools.partial(extract_blocks, factory=igt_group, start='__igt__', end=None)
extract_formgroups = functools.partial(
    extract_blocks, factory=lambda parser, lines: lines, start='__formgroup__', end=None)
