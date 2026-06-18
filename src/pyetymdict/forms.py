import dataclasses
from collections.abc import Iterable
from typing import Any, Optional

import pylexibank
from clldutils.misc import slug

from pyetymdict.parser.models import (
    Gloss, Protoform, Reflex, ExampleGroup, FormGroup, Reconstruction, Form as FormModel)
from .taxa import Taxa
from .languoids import Languoids

GLOSS_ID = 0
COMPUTED_GLOSS_DEFAULT = 'none'


@dataclasses.dataclass
class RepresentativeProtoform:
    form: Protoform
    gloss: str
    lexeme: dict


@dataclasses.dataclass
class Cognatesets:
    sets: dict[tuple[str, str], tuple[str, list]] = dataclasses.field(default_factory=dict)

    def add(
            self,
            writer,
            rec: Reconstruction,
            rep: RepresentativeProtoform,
    ) -> tuple[str, list]:
        key = (rep.form.lang, rep.form.form)
        if key not in self.sets:
            writer.objects['CognatesetTable'].append(dict(  # pylint: disable=R1735
                ID=rec.id,
                Form_ID=rep.lexeme['ID'],
                Name=rep.form.form,
                Description=rep.gloss,
                Level=rep.form.lang,
                # Source=['pmr1'],
                # Doubt=cset.doubt,
            ))
            self.sets[key] = (rec.id, [])  # Map to reconstruction ID and an accumulator for forms.

        return self.sets[key]


@dataclasses.dataclass
class ReconstructionData:
    # We store the forms and glosses and footnote numbers listed in this cognateset reference
    lexemes: list[dict] = dataclasses.field(default_factory=list)
    gloss_ids: list[str] = dataclasses.field(default_factory=list)
    # Lexeme ID to footnote
    footnote_map: dict[str, str] = dataclasses.field(default_factory=dict)
    # Lexeme ID to subgroup
    subgroup_map: dict[str, str] = dataclasses.field(default_factory=dict)

    def add_form(self, pf, lex):
        self.lexemes.append(lex)
        if pf.subgroup:
            self.subgroup_map[lex['ID']] = pf.subgroup
        if pf.footnote_number:
            self.footnote_map[lex['ID']] = pf.footnote_number


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
    Morpheme_Gloss: str = dataclasses.field(  # pylint: disable=C0103
        default=None,
        metadata={
            'dc:description':
                'Some forms (often multi-word expressions) are listed with morpheme glosses.'})
    Kinship_Gloss: str = dataclasses.field(  # pylint: disable=C0103
        default=None,
        metadata={'dc:description': 'Formalized kinship gloss.'}
    )


@dataclasses.dataclass
class Forms:
    """Keeps track of lexemes that have already been encountered."""
    writer: pylexibank.LexibankWriter
    languoids: Languoids
    taxa: Taxa
    by_lang_and_form: dict[tuple[str, str], tuple[dict[str, Any], dict]] = dataclasses.field(
        default_factory=dict)
    lexid2fn: dict = dataclasses.field(default_factory=dict)
    gloss2id: dict = dataclasses.field(default_factory=dict)

    #
    # FIXME: store langs here? It's just dataset.parser.languoids
    #

    @staticmethod
    def schema(cldf, with_taxa: bool = False):
        cldf.add_table(
            'examplegroups.csv',
            {
                'name': 'ID',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#id'},
            {
                'name': 'Example_IDs',
                'separator': ' ',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#exampleReference'},
            'Number',
            {
                'name': 'Context',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#comment'},
        )
        cldf.add_component(
            'ExampleTable',
            {
                'name': 'Source',
                'separator': ';',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#source'},
            'Reference_Label',
            'label',
            {
                'name': 'Movement_Gloss',
                'separator': '\t',
            },
        )
        cldf.add_columns('CognatesetTable', 'Level')
        if 'cf.csv' in cldf:
            cldf.add_columns(
                'cf.csv',
                {'name': 'CognatesetReference_ID'},
                {
                    'name': 'Chapter_ID',
                    'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#contributionReference'},
            )
            cldf.add_columns(
                'cfitems.csv',
                'Footnote_Number',
                {'name': 'Ordinal', 'datatype': 'integer'},
                {
                    'name': 'Gloss_IDs',
                    'separator': ' '},
                {'name': 'Subgroup'},
            )
        cldf.add_table(
            'cognatesetreferences.csv',
            {
                'name': 'ID',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#id'},
            {
                'name': 'Cognateset_ID',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#cognatesetReference'},
            {
                'name': 'Chapter_ID',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#contributionReference'},
            # Cognateset references are selections of forms and specific glosses from a bigger,
            # somewhat gloss-agnostic cognateset.
            {
                'name': 'Form_IDs',
                'separator': ' ',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#formReference'},
            {  # Map Form_ID to subgroup name in case the reflexes are organized like that.
                'name': 'Subgroup_Mapping',
                'datatype': 'json'},
            {  # Map Form_ID to footnote number
                'name': 'Footnote_Numbers',
                'datatype': 'json'},
            {
                'name': 'Gloss_IDs',
                'separator': ' '},
        )
        cldf.add_table(
            'glosses.csv',
            {
                'name': 'ID',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#id'},
            {
                'name': 'Name',
                'dc:description':
                    '',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#name'},
            'qualifier',  # A gloss number or other kind of qualifier.
            {
                'name': 'Form_ID',
                'dc:description': 'Links to the form in FormTable.',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#formReference'},
            {
                'name': 'Comment',
                "dc:format": "text/markdown",
                "dc:conformsTo": "CLDF Markdown",
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#comment'},
            {
                'name': 'Source',
                'separator': ';',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#source'},
            'Part_Of_Speech'
        )
        if with_taxa:
            cldf.add_columns('glosses.csv', {'name': 'Taxon_IDs', 'separator': ' '})
            cldf.add_foreign_key('glosses.csv', 'Taxon_IDs', 'taxa.csv', 'ID')

        cldf.add_foreign_key('cognatesetreferences.csv', 'Gloss_IDs', 'glosses.csv', 'ID')
        if 'cf.csv' in cldf:
            cldf.add_foreign_key('cfitems.csv', 'Gloss_IDs', 'glosses.csv', 'ID')
            cldf.add_foreign_key('cf.csv', 'CognatesetReference_ID', 'cognatesetreferences.csv', 'ID')
        return

    def add_form(
            self,
            protoform_or_reflex,
            # Forms may have a default, inherited or otherwise computed gloss.
            computed_gloss: str = COMPUTED_GLOSS_DEFAULT,
    ):
        if computed_gloss != COMPUTED_GLOSS_DEFAULT:
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

        kw = dict(  # pylint: disable=R1735
            Parameter_ID=self.gloss2id[gloss],
            Description=gloss,
            Value=protoform_or_reflex.form,
            Morpheme_Gloss=protoform_or_reflex.morpheme_gloss,
            Kinship_Gloss=protoform_or_reflex.kinship_gloss,
        )
        if isinstance(protoform_or_reflex, Protoform):
            kw.update(
                ID=f'{slug(protoform_or_reflex.lang)}-{slug(protoform_or_reflex.form)}',
                Language_ID=slug(protoform_or_reflex.lang),
                Source=[r.cldf_id for r in protoform_or_reflex.sources or []],
                # Doubt=getattr(form, 'doubt', False),
            )
        else:
            assert isinstance(protoform_or_reflex, Reflex)
            kw.update(
                ID=f"{self.languoids.by_name[protoform_or_reflex.lang]['ID']}"
                   f"-{slug(protoform_or_reflex.form)}",
                Language_ID=self.languoids.by_name[protoform_or_reflex.lang]['ID'],
                Comment=None,
                Morpheme_Gloss=protoform_or_reflex.morpheme_gloss,
                Kinship_Gloss=protoform_or_reflex.kinship_gloss,
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

    def _add_glosses(self, protoform_or_reflex, fid, old_glosses, gloss_ids):
        for gloss in protoform_or_reflex.glosses:
            if gloss not in old_glosses:
                # Must create a new gloss
                global GLOSS_ID  # pylint: disable=W0603
                GLOSS_ID += 1
                g = dict(  # pylint: disable=R1735
                    Form_ID=fid,
                    ID=str(GLOSS_ID),
                    Name=gloss.gloss,
                    Comment=gloss.comment,
                    Part_Of_Speech=gloss.pos,
                    qualifier=gloss.qualifier,
                    Source=[ref.cldf_id for ref in gloss.sources],
                    Taxon_IDs=self.taxa.match(gloss.gloss) if self.taxa else [],
                )
                self.writer.objects['glosses.csv'].append(g)
                old_glosses[gloss] = g
                gloss_ids.append(g['ID'])
            else:
                # FIXME: make sure the existing gloss has all the metadata of the new one,
                #  e.g. comment, source, POS
                og = old_glosses[gloss]
                if gloss.sources:
                    if not og['Source']:
                        og['Source'] = [ref.cldf_id for ref in gloss.sources]
                    else:
                        assert [ref.cldf_id for ref in gloss.sources] == og['Source'], (
                            f"{protoform_or_reflex}: {[ref.cldf_id for ref in gloss.sources]}"
                            f" vs {og['Source']}")
                gloss_ids.append(og['ID'])
        return gloss_ids

    def add_protoform_or_reflex(
            self,
            form,
            lang: Optional[str] = None,
            computed_gloss: str = COMPUTED_GLOSS_DEFAULT,
            gloss_ids: Optional[list[str]] = None,
    ) -> tuple[dict, list]:
        key = (lang or form.lang, form.form)
        if key not in self.by_lang_and_form:
            lex = self.add_form(form, computed_gloss=computed_gloss)
            # FIXME: we'll adapt the Description and Parameter_ID lateron, when all glosses have
            # been collected!
            self.by_lang_and_form[key] = (lex, {})
        lex, glosses = self.by_lang_and_form[key]
        if gloss_ids is None:
            gloss_ids = []
        self._add_glosses(form, lex['ID'], glosses, gloss_ids)
        return self.by_lang_and_form[key][0], gloss_ids

    def add_reconstructions(self, reconstructions: Iterable[Reconstruction]):
        """Add data for extracted reconstructions to the dataset."""
        cognatesets = Cognatesets()

        for rec in reconstructions:
            # The representative protoform and its lexeme:
            rep = None
            # We store the forms and glosses and footnote numbers listed in this cognateset reference
            data = ReconstructionData()

            # This is used to fill in glosses for forms that don't have any.
            computed_gloss = rec.computed_gloss

            for pf in rec.reflexes:  # FIXME: pf.sources !
                if isinstance(pf, Protoform):
                    lex = self.add_protoform_or_reflex(pf, gloss_ids=data.gloss_ids)[0]
                    if not rep:
                        rep = RepresentativeProtoform(
                            pf,
                            (pf.glosses[0].gloss or pf.glosses[0].morpheme_gloss)
                            if pf.glosses else getattr(pf, 'comment', None),
                            lex)
                else:
                    assert isinstance(pf, Reflex)
                    lex = self.add_protoform_or_reflex(
                        pf,
                        lang=self.languoids.by_name[pf.lang]['ID'],
                        computed_gloss=computed_gloss,
                        gloss_ids=data.gloss_ids)[0]

                data.add_form(pf, lex)

            assert rep
            csid, cog_forms = cognatesets.add(self.writer, rec, rep)
            for lex in data.lexemes:
                if lex['ID'] not in cog_forms:
                    self.writer.add_cognate(lexeme=lex, Cognateset_ID=csid)
                    cog_forms.append(lex['ID'])

            self.writer.objects['cognatesetreferences.csv'].append(dict(  # pylint: disable=R1735
                ID=rec.id,
                Cognateset_ID=csid,
                Chapter_ID='-'.join(rec.id.split('-')[:2]),
                # section, subsection, page
                Form_IDs=[f['ID'] for f in data.lexemes],
                Footnote_Numbers=data.footnote_map,
                Gloss_IDs=data.gloss_ids,
                Subgroup_Mapping=data.subgroup_map,
            ))

            for i, (name, items) in enumerate(rec.cfs, start=1):
                self._add_cf(
                    rec, f'{rec.id}-{i}', name, computed_gloss, items, csid=csid, csrefid=rec.id)

    def _add_cf(  # pylint: disable=R0913,R0917
            self,
            obj,
            cfid: str,
            name: str,
            computed_gloss: str,
            items: Iterable[FormModel],
            csid: Optional[str] = None,
            csrefid: Optional[str] = None,
    ):
        self.writer.objects['cf.csv'].append(dict(  # pylint: disable=R1735
            ID=cfid,
            Name=name,
            Cognateset_ID=csid,
            CognatesetReference_ID=csrefid,
            Chapter_ID='-'.join(obj.id.split('-')[:2]),
        ))
        for j, w in enumerate(items, start=1):
            lex, gloss_ids = self.add_protoform_or_reflex(
                w, lang=self.languoids.by_name[w.lang]['ID'], computed_gloss=computed_gloss)
            self.writer.objects['cfitems.csv'].append(dict(  # pylint: disable=R1735
                ID=f'{cfid}-{j}',
                Form_ID=lex['ID'],
                Subgroup=w.subgroup,
                Cfset_ID=cfid,
                Footnote_Number=self.lexid2fn.get(lex['ID']),
                Ordinal=j,
                Gloss_IDs=gloss_ids,
                # FIXME:
                # Source=[str(ref) for ref in form.gloss.refs],
                # Doubt=form.doubt,
            ))

    def add_formgroups(self, fgs: Iterable[FormGroup]):
        """Add data for extracted form groups to the dataset."""
        for fg in fgs:
            self._add_cf(fg, fg.id, fg.id, COMPUTED_GLOSS_DEFAULT, fg.forms)

    def add_examplegroups(self, egs: Iterable[ExampleGroup]):
        """Add data from extracted example groups to the dataset."""
        for eg in egs:
            for ex in eg.examples:
                self.writer.objects['ExampleTable'].append(dict(  # pylint: disable=R1735
                    ID=ex.id,
                    Primary_Text=ex.igt.primary_text,
                    Language_ID=self.languoids.by_name[ex.language]['ID'],
                    Analyzed_Word=ex.analyzed,
                    Gloss=ex.gloss,
                    Translated_Text=ex.translation,
                    label=ex.label,
                    Movement_Gloss=ex.add_gloss,
                    Source=[ex.reference.cldf_id] if ex.reference else [],
                    Reference_Label=ex.reference.label if ex.reference else '',
                    Comment=ex.comment,
                ))
            self.writer.objects['examplegroups.csv'].append(dict(  # pylint: disable=R1735
                ID=eg.id,
                Number=eg.number,
                Example_IDs=[ex.id for ex in eg.examples],
                Context=eg.context,
            ))
