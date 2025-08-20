import re
import collections

fn_pattern = re.compile(r'\[(?P<fn>[0-9]+)]')  # [2]


def re_choice(items):
    return r'|'.join(re.escape(i) for i in sorted(items, key=lambda ii: (-len(ii), ii)))


def strip_morphemeseparator(f):
    if f.startswith('-'):
        return '-' + strip_morphemeseparator(f[1:])
    if f.endswith('-'):
        return strip_morphemeseparator(f[:-1]) + '-'
    return f.replace('-', '')


def variants(f):
    # a(x)b -> axb, ab
    # a(x,y)b -> axb, ayb
    # a((x,y))b -> axb, ayb, ab
    v = []
    level = 0
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
        elif c in ')]':
            level -= 1
            if level == 0:
                break  # The remainder has to be dealt with recursively!
            bracketed += c
        else:
            bracketed += c

    if bracketed:
        if any(cc in bracketed for cc in '(['):  # Need to recurse.
            assert '),' not in bracketed
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


def nested_toc(items):
    def d2l(sid, title, children):
        return [
            sid,
            title,
            [d2l('-'.join([sid, ssid]) if sid else ssid, i[0], i[1])
             for ssid, i in children.items()] if children else []]

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
