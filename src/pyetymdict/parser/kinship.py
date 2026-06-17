"""
 M": "mother |        (NB not ‘Male’)
 F": "father | (NB not ‘Female’)
 P": "parent |

__tablenh__
 Z": "sister  |    (Z, as S is reserved for ‘son’)
 B": "brother  |
 G": "sibling | (Latin _germāna_, _germānus_)

__tablenh__
 W": "wife    |
 H": "husband | (French _épouse_, _époux_)
 E": "spouse  |

__tablenh__
 D": "daughter
 S": "son
 C": "child

    s | same sex as [EGO]{.smallcaps}
    o | opposite sex to [EGO]{.smallcaps}
    y | younger than [EGO]{.smallcaps} within [EGO]{.smallcaps}’s generation
    e | elder than [EGO]{.smallcaps} within [EGO]{.smallcaps}’s generation

Relative sex is reckoned relative to [EGO]{.smallcaps} in order to avoid ambiguity. Hence EGsC
‘spouse’s sibling’s child of [EGO]{.smallcaps}’s sex’, not ‘spouse’s siblings’s child of spouse’s
sibling’s sex’.
However, there are terms that encode sex relative to someone other than [EGO]{.smallcaps}, and in
these cases curly brackets are used, e.g. {PsG}C ‘child of parent’s same-sex sibling’,[8] i.e.
‘parallel cousin’, as opposed to PsGC ‘child of parent’s sibling of [EGO]{.smallcaps}’s sex’.
"""
import re


ATOMIC_TERMS = {
    "M": "mother",  # NB not ‘Male’
    "F": "father",  # NB not ‘Female’
    "P": "parent",  # M or F
    "Z": "sister",  # Z, as S is reserved for ‘son’
    "B": "brother",
    "G": "sibling",  # Latin _germāna_, _germānus_, Z or B
    "W": "wife",
    "H": "husband",  # French _épouse_, _époux_
    "E": "spouse",  # W or H
    "D": "daughter",
    "S": "son",
    "C": "child",  # D or S
}
MODIFIERS = {
    "s": "same sex as EGO",
    "o": "opposite sex to EGO",
    "y": "younger than EGO within EGO’s generation",
    "e": "elder than EGO within EGO’s generation",
}


ATOM = r'([{}]+)?[{}]'.format(''.join(MODIFIERS), ''.join(ATOMIC_TERMS))
ATOM_GROUP = r'\{?(' + ATOM + r')+\}?'
NESTED_GROUP = r'\{?(' + ATOM_GROUP + '|' + ATOM + r')+\}?'
TERM = r'([♀♂]|\([♀♂]\?\))?({})+|etc|\(ADDR\)'.format(NESTED_GROUP)

# Kinship tags are detected when they follow a quoted gloss, separated by a comma.
PATTERN: re.Pattern[str] = re.compile(r"[’']\s*(,\s+({})( etc)?)+".format(  # pylint: disable=C0209
    TERM))


def search(text):
    m = PATTERN.search(text)
    if m:
        s = m.string[m.start():m.end()]
        if s.count('{') == s.count('}'):
            # We don't force matching braces with the regexes above!
            return m
    return None
