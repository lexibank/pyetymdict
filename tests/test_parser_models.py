import pytest

from pyetymdict.parser.models import *


def test_Reference():
    ref = Reference('id', 'label', 'pages')
    assert ref.cldf_id == 'id[pages]'
    assert str(ref) == '[label](id)'


def test_Example(volume1):
    ex = Example.from_lines(volume1, [
        'a. a b c',
        'A B C',
        "'The translation' (Author 2000)"
    ], lang='POc')
    assert ex.label == 'a.'
    assert ex.igt.conformance.name == 'MORPHEME_ALIGNED'
    assert str(ex)

    ex = Example.from_lines(volume1, [
        'a b c',
        'A B C',
        'X Y Z',
        "'The translation' (Author 2000)"
    ], lang='POc')
    assert ex.add_gloss

    ex = Example.from_lines(volume1, [
        'Language (Adm)',
        'a b c',
        'A B C',
        "'The translation' (Author 2000)"
    ])
    assert ex.language == 'Language'

    # Comments may be added to the analyzed text line or to the translation line:
    ex = Example.from_lines(volume1, [
        'a b c',
        'A B C',
        "'The translation' (a comment)"
    ], lang='POc')
    assert ex.comment == 'a comment'

    ex = Example.from_lines(volume1, [
        'a b c (a comment)',
        'A B C',
        "'The translation'"
    ], lang='POc')
    assert ex.comment == 'a comment'


def test_comment_or_sources(volume1):
    cmt, srcs = comment_or_sources(volume1, 'Author 2000, Author 2000')
    assert not cmt
    cmt, srcs = comment_or_sources(volume1, 'Author 2000, but also other stuff')
    assert not srcs


def test_ExampleGroup(volume1):
    eg = ExampleGroup.from_data(1, volume1, (1, 'C'), (1, 'S'), (1, 'SS'), 10, """\
    (1) Language (Adm): (Author 2000:204, 231)
    a. Au   rabe.
       s:1s kick
       'I'm kicking.'
    b. Au    rabe-t-a     a   polo.
       s:1s  kick-TR-O:3s ART ball
       'I'm kicking the ball.'\
""".split('\n'))
    eg = ExampleGroup.from_data(1, volume1, (1, 'C'), (1, 'S'), (1, 'SS'), 10, """\
1) a. Language (Adm)
       Au   rabe.
       s:1s kick
       'I'm kicking.'\
""".split('\n'))



@pytest.mark.parametrize(
    'text,assertion',
    [
        ("'the gloss'", lambda g: g.gloss == 'the gloss'),
        ("'the gloss'[1]", lambda g: g.fn == '1'),
        ("[A.B.C]", lambda g: g.morpheme_gloss == 'A.B.C'),
        ("(1) 'the gloss'", lambda g: g.qualifier == '1'),
        ("'the gloss' (cmt)", lambda g: g.comment == 'cmt'),
        ("'the gloss' (Author 2000)", lambda g: not g.comment and len(g.sources) == 1),
        ("'lion' [Panthera leo]", lambda g: g.species == 'Panthera leo'),
        ("'the gloss' (first) (second)", lambda g: g.comment == 'first; second'),
        ("? 'the gloss'", lambda g: g.doubt),
        ("[Not_a_morpheme_gloss]", lambda g: g.morpheme_gloss == 'Not_a_morpheme_gloss'),
        # Yet another use for morpheme glosses: Kinship term coding.
        ("‘the gloss’, PZ", lambda g: g.morpheme_gloss == 'PZ'),
    ]
)
def test_Gloss(volume1, text, assertion, parser):
    from pyetymdict.parser.forms import iter_glosses
    g = Gloss.from_dict(volume1, next(iter_glosses(text, parser.pos_pattern, parser.kinship_pattern)))
    assert assertion(g), g
    assert isinstance(str(g), str)


def test_Gloss_cmp(volume1, parser):
    from pyetymdict.parser.forms import iter_glosses
    g1 = Gloss.from_dict(volume1, next(iter_glosses("(V) 'gloss'", parser.pos_pattern)))
    g2 = Gloss.from_dict(volume1, next(iter_glosses("(V) 'gloss'", parser.pos_pattern)))
    assert g2 in {g1: '1'}
    assert g1 == g2
    g3 = Gloss.from_dict(volume1, next(iter_glosses("(VT) 'gloss'", parser.pos_pattern)))
    assert g3 != g2


@pytest.mark.parametrize(
    'text,assertion',
    [
        ("POc *mata 'eye'", lambda pf: pf.form == 'mata'),
        ("POc *mata ? 'eye'", lambda pf: pf.pfdoubt),
        # In the next case, we shuffle the question mark around, taking a doubtful pos of the gloss
        # as doubtful form.
        ("POc *mata (N) (?) 'eye'", lambda pf: pf.pfdoubt and pf.glosses[0].pos == 'N'),
        ("POc (?) *mata 'eye'", lambda pf: pf.pldoubt),
        ("POc *mata (Author 2000) 'eye'", lambda pf: len(pf.sources) == 1),
        ("POc *mata 'eye' (Author 2000)", lambda pf: len(pf.glosses[0].sources) == 1),
        ("POc *mata [eye]", lambda pf: pf.morpheme_gloss == 'eye'),
        ("POc (N) *mata 'eye' [1]", lambda pf: pf.footnote_number == '1'),
    ]
)
def test_ProtoForm(volume1, text, assertion):
    pf = Protoform.from_line(volume1, text)
    assert assertion(pf), pf


@pytest.mark.parametrize(
    'text,assertion',
    [
        ("Adm: Language form 'gloss'", lambda r: r.forms[0] == 'form'),
        ("Adm: Language |two words| 'gloss'", lambda r: r.forms[0] == 'two words'),
        ("Adm: Language forma, formb 'gloss'", lambda r: r.form == 'forma, formb'),
        ("Adm: Language form 'gloss' [1]", lambda r: r.footnote_number == '1'),
    ]
)
def test_Reflex(volume1, text, assertion):
    ref = Reflex.from_line(volume1, text)
    assert assertion(ref), ref
    assert str(ref)


def test_Reflex_with_bad_form(volume1):
    with pytest.raises(ValueError):
        Reflex.from_line(volume1, " Adm: Language form1 'gloss'")


def test_FormGroup(volume1):
    fg = FormGroup.from_data(
        volume1,
        ('2', 'Chapter'),
        ('3', 'Section'),
        ('4', 'Subsection'),
        '123',
        [" Adm: Language  form 'gloss'"]
    )
    assert len(fg.forms) == 1
    assert fg.forms[0].lang == 'Language'
    assert fg.id == '1-2-3-4-123-adm-language-form'
    assert 'cf.csv#cldf:' in fg.cldf_markdown_link()
    assert fg not in {}


def test_Reconstruction(volume1):
    rec = Reconstruction.from_data(
        volume1,
        ('2', 'Chapter'),
        ('3', 'Section'),
        ('4', 'Subsection'),
        '123',
        ("""\
POc *mata 'eye'
-sg1
 Adm: Language form 'gloss'""".split('\n'), [('loans', [" Adm: Language loan 'yes'"])])
    )
    assert rec.reflexes[1].subgroup == 'sg1'
    assert rec.poc_gloss == 'eye'

    rec = Reconstruction.from_data(
        volume1,
        ('2', 'Chapter'),
        ('3', 'Section'),
        ('4', 'Subsection'),
        '123',
        ("""\
PMP *mata 'eye'
-sg1
 Adm: Language form 'gloss'""".split('\n'), [('loans', [" Adm: Language loan 'yes'"])])
    )
    assert rec.first_oceanic_protoform.lang == 'PMP'
    assert str(rec)


def test_Volume(volume1):
    assert len(volume1.chapters) == 1
    assert len(volume1.reconstructions) == 3
    assert len(volume1.igts) == 2
    assert len(volume1.formgroups) == 2
    assert len(list(list(volume1.chapters.values())[0].iter_sections())) == 3


@pytest.mark.parametrize(
    'text,replacement',
    [
        ('abc', 'abc'),
        ('§4.1.1', '[§4.1.1](ContributionTable?anchor=s-4-1-1#cldf:1-1)'),
        ('Ch 4, §4.1', '[Ch 4, §4.1](ContributionTable?anchor=s-4-1#cldf:1-4)'),
        ('vol. 1, p.247', '[vol.1,247](ContributionTable?anchor=p-247#cldf:1-9)'),
        ('vol. 1, ch. 3', '[vol. 1, ch. 3](ContributionTable#cldf:1-3)'),
        ('', ''),
    ]
)
def test_replace_cross_refs(volume1, text, replacement):
    """
# (vol. 1, pp.293–294)
# vol.1, ch.6, §5.6
# vol.1 (ch.6, §5.6)
# (vol.1, p.80)
# (vol.1:155)
# volume 1 (p.93)
    """
    assert volume1.replace_cross_refs(text, '1') == replacement
