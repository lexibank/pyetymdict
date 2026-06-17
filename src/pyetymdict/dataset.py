"""
An EtymDict-specific CLDFBench Dataset subclass.
"""
import shutil
import pathlib
import functools
import collections
import dataclasses
from typing import Optional, Union, Any

import newick
import pycldf
from pycldf import orm
from pycldf.sources import Sources, Source
from pycldf.ext.markdown import CLDFMarkdownLink
from cldfcatalog import Catalog
from cldfbench import CLDFWriter
import pylexibank
from clldutils.misc import data_url, slug

from pyetymdict.parser.spec import LanguageIdType
from pyetymdict.parser.models import Parser, Volume, Gloss, Protoform, Reflex
from pyetymdict.parser.util import nested_toc
from .taxa import Taxa
from .languoids import Languoids
from .schema import schema

__all__ = ['Language', 'Form', 'Dataset']


@dataclasses.dataclass
class Language(pylexibank.Language):
    """Languages in an EtymDict might be Proto-Languages."""
    Abbr: Optional[str] = dataclasses.field(  # pylint: disable=C0103
        default=None,
        metadata={'dc:description': 'Abbreviation for the (proto-)language name.'},
    )
    Group: Optional[str] = dataclasses.field(  # pylint: disable=C0103
        default=None,
        metadata={
            'dc:description':
                'Etymological dictionaries often operate with an assumed internal classification. '
                'This column lists such groups.'},
    )
    Source: list[str] = dataclasses.field(  # pylint: disable=C0103
        default_factory=list,
        metadata={
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#source',
            'separator': ';',
            'dc:description':
                'Etymological (or comparative) dictionaries typically compare lexical data from '
                'many source dictionaries.',
        },
    )
    Is_Proto: bool = dataclasses.field(  # pylint: disable=C0103
        default=False,
        metadata={
            'datatype': 'boolean',
            'dc:description':
                'Specifies whether a language is a proto-language (and thus its forms '
                'reconstructed proto-forms).',
        }
    )


@dataclasses.dataclass
class Form(pylexibank.Lexeme):
    """Forms in an EtymDict typically provide some commentary regarding their property as reflex."""
    Comment: Optional[str] = dataclasses.field(  # pylint: disable=C0103
        default=None,
        metadata={
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#comment',
            "dc:format": "text/markdown",
            "dc:conformsTo": "CLDF Markdown",
            'dc:description':
                "Comment on the word form (and also on its membership in cognate sets)."}
    )
    Description: Optional[str] = dataclasses.field(  # pylint: disable=C0103
        default=None,
        metadata={
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#description',
            "dc:format": "text/markdown",
            "dc:conformsTo": "CLDF Markdown",
            'dc:description':
                "Description of the meaning of the word (possibly in language-specific terms)."}
    )
    Sic: bool = dataclasses.field(  # pylint: disable=C0103
        default=False,
        metadata={
            'datatype': 'boolean',
            'dc:description':
                "For a form that differs from the expected reflex in some way "
                "this flag asserts that a copying mistake has not occurred."}
    )
    Doubt: bool = dataclasses.field(  # pylint: disable=C0103
        default=False,
        metadata={
            'datatype': 'boolean',
            'dc:description':
                "In particular reconstructions, i.e. proto-forms in etymological dictionaries, "
                "are often marked as being somewhat doubtful (typically displayed as proto-form "
                "prefixed with a '?' or similar)."}
    )


class Dataset(pylexibank.Dataset):
    """EtymDict-specific CLDFBench dataset."""
    language_class = Language
    lexeme_class = Form

    @functools.cached_property
    def sources(self) -> Sources:
        return Sources.from_file(self.etc_dir / 'sources.bib')

    @functools.cached_property
    def taxa(self):
        p = self.etc_dir / 'gbif_taxa.csv'
        if p.exists():
            return Taxa.from_file(p)
        return None

    @functools.cached_property
    def languoids(self):
        return Languoids.from_dataset(self)

    @functools.cached_property
    def parser(self):
        return Parser(
            self.id,
            list(self.raw_dir.glob('vol[0-9]')),
            self.languoids,
            pos_map={pos: pos for pos in self.etc_dir.read_json('pos.json')},
            citation_template=Source.from_bibtex(self.etc_dir.read('citation.bib')),
        )

    def add_tree(  # pylint: disable=R0913,R0917
            self,
            writer: CLDFWriter,
            tree_newick_string: str,
            names: Optional[dict[str, str]] = None,
            separate_file: bool = False,
            description: str = 'The tree structure of the reconstruction levels',
    ):
        """Add the reconstruction tree."""
        for comp in ['TreeTable', 'MediaTable']:
            if comp not in writer.cldf:
                writer.cldf.add_component(comp)

        # Add the classification tree
        t = newick.loads(tree_newick_string)[0]
        if names:
            t.rename(**names)
        if separate_file:
            self.cldf_dir.joinpath('tree.nwk').write_text(tree_newick_string, encoding='utf8')
            url = 'tree.nwk'
        else:
            url = data_url(t.newick, 'text/x-nh')
        writer.objects['MediaTable'].append(dict(  # pylint: disable=R1735
            ID='tree',
            Name='Newick tree',
            Description=description,
            Media_Type='text/x-nh',
            Download_URL=url,
        ))
        writer.objects['TreeTable'].append(dict(  # pylint: disable=R1735
            ID='tree',
            Name='1',
            Description=description,
            Tree_Is_Rooted='Yes',
            Tree_Type='summary',
            Media_ID='tree',
        ))

    def glottolog_cldf_languoids(
            self,
            default_path: Union[pathlib.Path, str],
            version: Optional[str] = None,
    ) -> dict[str, orm.Language]:
        """
        The Glottolog CLDF datasets provides geo-coordinates for subgroups as well. Thus, in order
        to provide locations for proto-languages, we provide a way to access this dataset.

        :return: A `dict` mapping Glottocodes to language objects.
        """
        default_path = pathlib.Path(default_path)
        path_to_glottolog_cldf = pathlib.Path(input(
            f'Path to glottolog-cldf repos [{default_path}]: ') or default_path)
        assert path_to_glottolog_cldf.exists()
        with Catalog(path_to_glottolog_cldf, tag=version):
            return {lg.id: lg for lg in pycldf.Dataset.from_metadata(
                path_to_glottolog_cldf / 'cldf' / 'cldf-metadata.json').objects('LanguageTable')}

    def schema(
            self,
            cldf: pycldf.Dataset,
            with_cf: bool = True,
            with_borrowings: bool = True,
            with_contributions: bool = True,
    ):
        return schema(
            cldf,
            with_cf=with_cf,
            with_borrowings=with_borrowings,
            with_contributions=with_contributions,
            taxa=self.taxa)

    def parse_chapters(
            self,
            writer: CLDFWriter,
            reconstruction_cls: Optional[type] = None,
    ):
        def srcids(agg, m):
            if m.table_or_fname == 'Source':
                agg.add(m.objid)

        if not self.parser:
            return

        taxon2sections = collections.defaultdict(list)
        reconstructions, fgs, egs = [], [], []
        for vol in self.parser.volumes:
            vol = Volume(
                self.parser,
                vol,
                self.parser.languoids,
                self.sources,
                reconstruction_cls=reconstruction_cls,
            )
            reconstructions.extend(vol.reconstructions)
            fgs.extend(vol.formgroups)
            egs.extend(vol.igts)

            mddir = self.cldf_dir.joinpath(vol.dir.path.name)
            mddir.mkdir(exist_ok=True)
            for num, chapter in vol.chapters.items():  # Add chapters as CLDF Markdown docs.
                cid = f'{vol.dir.number}-{num}'
                sources, source_to_sections = set(), collections.defaultdict(set)
                for fid, label, p in vol.dir.iter_figures(chapter.text):
                    shutil.copy(p, mddir / p.name)
                    writer.objects['MediaTable'].append(dict(
                        ID=fid,
                        Name='Volume {} {}'.format(vol.dir.number, p.stem),
                        Description=label,
                        Download_URL=str(mddir.joinpath(p.name).relative_to(self.cldf_dir)),
                        Media_Type='image/png',
                    ))
                p = mddir.joinpath('chapter{}.md'.format(num))
                p.write_text(chapter.text, encoding='utf-8')
                sid = None
                for sid, text in chapter.iter_sections():
                    if self.taxa:
                        for v in self.taxa.match(text):
                            taxon2sections[v].append((cid, sid))

                    sids = set()
                    CLDFMarkdownLink.replace(text, functools.partial(srcids, sids))
                    if sids:
                        sources |= sids
                        for s in sids:
                            source_to_sections[s].add(sid)
                if sid is None:  # Chapter has no sections.
                    sids = set()
                    CLDFMarkdownLink.replace(chapter.text, functools.partial(srcids, sids))
                    if sids:
                        sources |= sids

                writer.objects['MediaTable'].append(dict(
                    ID=f'{cid}-text',
                    Name='Volume {} Chapter {}'.format(vol.dir.number, num),
                    Description='Chapter text formatted as CLDF Markdown document',
                    Download_URL=str(p.relative_to(self.cldf_dir)),
                    Media_Type='text/markdown',
                    Conforms_To='CLDF Markdown',
                ))
                writer.objects['ContributionTable'].append(dict(
                    ID=cid,
                    Name=chapter.bib['title'],
                    Contributor=chapter.bib['author'],
                    Citation=chapter.bib.text(),
                    Volume_Number=vol.dir.number,
                    Volume=vol.dir.metadata.title,
                    Table_Of_Contents=nested_toc(chapter.toc),
                    Source=sorted(sources),
                    Source_To_Sections={k: list(v) for k, v in source_to_sections.items()},
                ))
        if self.taxa:
            for row in self.taxa.iter_rows(taxon2sections):
                writer.objects['taxa.csv'].append(row)
        return reconstructions, fgs, egs


@dataclasses.dataclass
class FormTable:
    """Keeps track of lexemes that have already been encountered."""
    writer: pylexibank.LexibankWriter
    langs: dict[LanguageIdType, collections.OrderedDict[str, Any]]
    by_lang_and_form: dict[tuple[str, str], tuple[dict[str, Any], dict]] = dataclasses.field(
        default_factory=dict)
    lexid2fn: dict = dataclasses.field(default_factory=dict)
    gloss2id: dict = dataclasses.field(default_factory=dict)

    #
    # FIXME: store langs here? It's just dataset.parser.languoids
    #

    def add_form(
            self,
            protoform_or_reflex,
            # Forms may have a default, inherited or otherwise computed gloss.
            computed_gloss='none',
    ):
        if computed_gloss != 'none':
            if not protoform_or_reflex.glosses:
                protoform_or_reflex.glosses.append(Gloss(gloss=computed_gloss, sources=[]))
        gloss = protoform_or_reflex.glosses[0].gloss if protoform_or_reflex.glosses else computed_gloss

        if gloss not in self.gloss2id:
            self.gloss2id[gloss] = slug(str(gloss))
            self.writer.add_concept(ID=slug(str(gloss)), Name=gloss)

        #
        # FIXME: add Source! either from Sources associated with glosses or from ldicts!
        #
        _source = set()
        for _gloss in protoform_or_reflex.glosses:
            if _gloss.sources:
                _source |= {ref.cldf_id for ref in _gloss.sources}

        kw = dict(
                Parameter_ID=self.gloss2id[gloss],
                Description=gloss,
                Value=protoform_or_reflex.form,
                Morpheme_Gloss=protoform_or_reflex.morpheme_gloss,
            )
        if isinstance(protoform_or_reflex, Protoform):
            kw.update(
                ID='{}-{}'.format(slug(protoform_or_reflex.lang), slug(protoform_or_reflex.form)),
                Language_ID=slug(protoform_or_reflex.lang),
                Source=[r.cldf_id for r in protoform_or_reflex.sources or []],
                # Doubt=getattr(form, 'doubt', False),
            )
        else:
            assert isinstance(protoform_or_reflex, Reflex)
            kw.update(
                ID='{}-{}'.format(self.langs[protoform_or_reflex.lang]['ID'], slug(protoform_or_reflex.form)),
                Language_ID=self.langs[protoform_or_reflex.lang]['ID'],
                Comment=None,
                Morpheme_Gloss=protoform_or_reflex.morpheme_gloss,
                # Hm. we add Source for the individual gloss.
                Source=[],  # FIXME: add the sources for the language!
                # Doubt=getattr(form, 'doubt', False),
            )
        if not kw['Source']:
            kw.update(Source=sorted(_source))
        lex = self.writer.add_lexemes(**kw)[0]
        if protoform_or_reflex.footnote_number:
            self.lexid2fn[lex['ID']] = protoform_or_reflex.footnote_number
        return lex

    def add_glosses(self, protoform_or_reflex, fid, old_glosses, gloss_ids=None):
        if gloss_ids is None:
            gloss_ids = []
        for k, gloss in enumerate(protoform_or_reflex.glosses, start=1):
            if gloss not in old_glosses:
                # Must create a new gloss
                global GLOSS_ID
                GLOSS_ID += 1
                g = dict(
                    Form_ID=fid,
                    ID=str(GLOSS_ID),
                    Name=gloss.gloss,
                    Comment=gloss.comment,
                    Part_Of_Speech=gloss.pos,
                    qualifier=gloss.qualifier,
                    Source=[ref.cldf_id for ref in gloss.sources],

                    # FIXME: How to handle these?
                    Taxon_IDs=sorted(v for k, v in self.taxa.items() if k in (gloss.gloss or '')),


                )
                self.writer.objects['glosses.csv'].append(g)
                old_glosses[gloss] = g
                gloss_ids.append(g['ID'])
            else:
                # FIXME: make sure the existing gloss has all the metadata of the new one, e.g. comment, source, POS
                og = old_glosses[gloss]
                if gloss.sources:
                    if not og['Source']:
                        og['Source'] = [ref.cldf_id for ref in gloss.sources]
                    else:
                        assert [ref.cldf_id for ref in gloss.sources] == og['Source'], (
                                f"{protoform_or_reflex}: {[ref.cldf_id for ref in gloss.sources]} vs {og['Source']}")
                gloss_ids.append(og['ID'])
        return gloss_ids


    def add(
            self,
            form,
            lang: Optional[str] = None,
            computed_gloss: str = 'none',
    ) -> dict:
        key = (lang or form.lang, form.form)
        if key not in self.by_lang_and_form:
            lex = self.add_form(form, computed_gloss=computed_gloss)
            # FIXME: we'll adapt the Description and Parameter_ID lateron, when all glosses have been collected!
            self.by_lang_and_form[key] = (lex, {})

        self.add_glosses(args.writer, pf, lex['ID'], words[(pf.lang, pf.form)][1], gloss_ids)

        return self.by_lang_and_form[key][0]


def handle_reconstructions(reconstructions, writer, langs):
    # map (lang, form) pairs to associated glosses (as dict mapping gloss to gloss object with all properties.).
    #
    # FIXME: must be accumulated across reconstructions and formgroups!
    #
    words = FormTable(writer, langs)

    cognatesets = {}

    for i, rec in enumerate(reconstructions):
        # Add protoforms and reflex forms and glosses, keep IDs of forms and glosses!
        pfrep, pflex = None, None
        # We store the forms and glosses and footnote numbers listed in this cognateset reference
        forms, gloss_ids, fns, sgmap = [], [], {}, {}

        computed_gloss = rec.computed_gloss

        for j, pf in enumerate(rec.reflexes):  # FIXME: pf.sources !
            # We have adopted the
            # convention of providing no gloss beside the items in a cognate set whose gloss is identical to
            # that of the POc (or other lower-order) reconstruction at the head of the set, i.e. the reconstruction
            # which they reflect.
            if j == 0:
                pfrep = pf
            pfgloss = (pf.glosses[0].gloss or pf.glosses[
                0].morpheme_gloss) if pf.glosses else getattr(pf, 'comment', None)
            if isinstance(pf, Protoform):

                lex = words.add(pf)
                self.add_glosses(args.writer, pf, lex['ID'], words[(pf.lang, pf.form)][1], gloss_ids)

                if pflex is None:
                    pflex = lex
            else:
                assert isinstance(pf, Reflex)
                w = pf
                assert w.lang in langs
                lid = langs[w.lang]['ID']

                lex = words.add(w, lang=lid, computed_gloss=computed_gloss)
                self.add_glosses(args.writer, w, lex['ID'], words[(lid, w.form)][1], gloss_ids)

            forms.append(lex)
            if pf.subgroup:
                sgmap[lex['ID']] = pf.subgroup
            if pf.footnote_number:
                fns[lex['ID']] = pf.footnote_number

        if (pfrep.lang, pfrep.form) not in cognatesets:
            args.writer.objects['CognatesetTable'].append(dict(
                ID=rec.id,
                Form_ID=pflex['ID'],
                Name=pfrep.form,
                Description=pfgloss,
                Level=pfrep.lang,
                # Source=['pmr1'],
                # Doubt=cset.doubt,
            ))
            cognatesets[(pfrep.lang, pfrep.form)] = (rec.id, [])

        csid, cog_forms = cognatesets[(pfrep.lang, pfrep.form)]
        for lex in forms:
            if lex['ID'] not in cog_forms:
                args.writer.add_cognate(lexeme=lex, Cognateset_ID=csid)
                cog_forms.append(lex['ID'])

        args.writer.objects['cognatesetreferences.csv'].append(dict(
            ID=rec.id,
            Cognateset_ID=csid,
            Chapter_ID='-'.join(rec.id.split('-')[:2]),
            # section, subsection, page
            Form_IDs=[f['ID'] for f in forms],
            Footnote_Numbers=fns,
            Gloss_IDs=gloss_ids,
            Subgroup_Mapping=sgmap,
        ))

        for i, (name, items) in enumerate(rec.cfs, start=1):
            args.writer.objects['cf.csv'].append(dict(
                ID='{}-{}'.format(rec.id, i),
                Name=name,
                Cognateset_ID=csid,
                CognatesetReference_ID=rec.id,
                Chapter_ID='-'.join(rec.id.split('-')[:2]),
            ))
            for j, w in enumerate(items, start=1):
                assert w.lang in langs, w.lang
                lid = langs[w.lang]['ID'] if isinstance(langs[w.lang], dict) else langs[w.lang]

                lex = words.add(w, lang=lid, computed_gloss=computed_gloss)
                gloss_ids = self.add_glosses(args.writer, w, lex['ID'], words[(lid, w.form)][1]),

                args.writer.objects['cfitems.csv'].append(dict(
                    ID='{}-{}-{}'.format(rec.id, i, j),
                    Form_ID=lex['ID'],
                    Ordinal=j,
                    Cfset_ID='{}-{}'.format(rec.id, i),
                    Footnote_Number=words.lexid2fn.get(lex['ID']),
                    Gloss_IDs=gloss_ids,
                    # Source=[str(ref) for ref in form.gloss.refs],
                    # Doubt=form.doubt,
                ))

def handle_formgroups(fgsreconstructions):
    for fg in fgs:
        args.writer.objects['cf.csv'].append(dict(
            ID=fg.id,
            Name=fg.id,
            Cognateset_ID=None,
            CognatesetReference_ID=None,
            Chapter_ID='-'.join(fg.id.split('-')[:2]),
        ))
        for j, w in enumerate(fg.forms, start=1):
            assert w.lang in langs
            lid = langs[w.lang]['ID']

            if (lid, w.form) not in words:
                lex = self.add_form(args.writer, w, gloss2id, langs, lexid2fn)
                words[(lid, w.form)] = (lex, {})
            else:
                lex = words[(lid, w.form)][0]

            args.writer.objects['cfitems.csv'].append(dict(
                ID='{}-{}'.format(fg.id, j),
                Form_ID=lex['ID'],
                Subgroup=w.subgroup,
                Cfset_ID=fg.id,
                Footnote_Number=lexid2fn.get(lex['ID']),
                Ordinal=j,
                Gloss_IDs=self.add_glosses(args.writer, w, lex['ID'], words[(lid, w.form)][1]),
                # Source=[str(ref) for ref in form.gloss.refs],
            ))

def handle_examplegroups(egs):
    for eg in egs:
        for ex in eg.examples:
            args.writer.objects['ExampleTable'].append(dict(
                ID=ex.id,
                Primary_Text=ex.igt.primary_text,
                Language_ID=langs[ex.language] if isinstance(langs[ex.language], str) else
                langs[ex.language]['ID'],
                Analyzed_Word=ex.analyzed,
                Gloss=ex.gloss,
                Translated_Text=ex.translation,
                label=ex.label,
                Movement_Gloss=ex.add_gloss,
                Source=[ex.reference.cldf_id] if ex.reference else [],
                Reference_Label=ex.reference.label if ex.reference else '',
                Comment=ex.comment,
            ))
        args.writer.objects['examplegroups.csv'].append(dict(
            ID=eg.id,
            Number=eg.number,
            Example_IDs=[ex.id for ex in eg.examples],
            Context=eg.context,
        ))
