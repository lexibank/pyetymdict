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
from .languoids import Languoids, Language
from .schema import schema
from .forms import Form, Forms

__all__ = ['Language', 'Form', 'Dataset']


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
    ):
        schema(cldf, with_cf=with_cf, with_borrowings=with_borrowings)
        if self.taxa:
            self.taxa.schema(cldf)
        Forms.schema(cldf, with_taxa=bool(self.taxa))

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
                        Name=f'Volume {vol.dir.number} {p.stem}',
                        Description=label,
                        Download_URL=str(mddir.joinpath(p.name).relative_to(self.cldf_dir)),
                        Media_Type='image/png',
                    ))
                p = mddir.joinpath(f'chapter{num}.md')
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
                    Name=f'Volume {vol.dir.number} Chapter {num}',
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
            self.taxa.add(writer, taxon2sections)
        return reconstructions, fgs, egs
