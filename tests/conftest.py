import shutil
import logging
import pathlib
import argparse
import dataclasses

import pytest
from pycldf.sources import Source, Sources
from cldfbench.catalogs import CLTS

from pyetymdict import Dataset, Language
from pyetymdict.languoids import Languoids
from pyetymdict.forms import Forms


@pytest.fixture(scope='session')
def testsdir():
    return pathlib.Path(__file__).parent


@pytest.fixture(scope='session')
def CLTS_api(testsdir):
    return CLTS(testsdir / 'clts')


@pytest.fixture(scope='session')
def repos():
    return pathlib.Path(__file__).parent / 'repos'


@pytest.fixture(scope='session')
def repos2():
    return pathlib.Path(__file__).parent / 'repos2'


@pytest.fixture(scope='session')
def ds2(tmpdir_factory, repos2, CLTS_api):
    tmp = pathlib.Path(tmpdir_factory.mktemp('repos')) / 'repos'
    shutil.copytree(repos2, tmp)

    class DS(Dataset):
        id = 'test'
        dir = tmp

        def cmd_makecldf(self, args):
            self.schema(args.writer.cldf, with_borrowings=False)

            args.writer.cldf.sources = self.sources
            reconstructions, fgs, egs = self.parse_chapters(args.writer)
            self.languoids.add(args.writer, {}, {})
            formtable = Forms(args.writer, self.languoids, self.taxa)
            formtable.add_reconstructions(reconstructions)
            formtable.add_formgroups(fgs)
            formtable.add_examplegroups(egs)
            self.add_tree(args.writer, '((lang,lang2)pmp)poc;', separate_file=True)

    ds = DS()
    ds._cmd_makecldf(argparse.Namespace(
        dev=True,
        verbose=False,
        clts=CLTS_api,
        log=logging.getLogger(__name__)))
    return ds


@pytest.fixture(scope='session')
def ds(tmpdir_factory, repos, CLTS_api):
    tmp = pathlib.Path(tmpdir_factory.mktemp('repos')) / 'repos'
    shutil.copytree(repos, tmp)

    @dataclasses.dataclass
    class L(Language):
        custom: str = None

    class DS(Dataset):
        id = 'test'
        dir = tmp
        language_class = L

        def cmd_makecldf(self, args):
            self.schema(args.writer.cldf, with_borrowings=False)

            args.writer.cldf.sources = self.sources
            reconstructions, fgs, egs = self.parse_chapters(args.writer)
            self.languoids.add(args.writer, {}, {})
            formtable = Forms(args.writer, self.languoids, self.taxa)
            formtable.add_reconstructions(reconstructions)
            formtable.add_formgroups(fgs)
            formtable.add_examplegroups(egs)
            self.add_tree(args.writer, '((lang,lang2)pmp)poc;', separate_file=True)

    ds = DS()
    ds._cmd_makecldf(argparse.Namespace(
        dev=True,
        verbose=False,
        clts=CLTS_api,
        log=logging.getLogger(__name__)))
    return ds


@pytest.fixture(scope='session')
def parser(repos):
    from pyetymdict.parser.spec import Parser
    from pyetymdict.dataset import Dataset

    class DS(Dataset):
        dir = repos
        id = 'test'

    return Parser(
        'pid',
        [repos / 'raw' / 'vol1'],
        Languoids.from_dataset(DS()),
        pos_map={'N': 'N', 'V': 'V', 'VT': 'VT'},
        citation_template=Source('book', 'pid', title='The Dict'),
    )


@pytest.fixture(scope='session')
def volume1(parser, repos):
    from pyetymdict.parser.models import Volume

    sources = Sources.from_file(repos / 'etc' / 'sources.bib')
    return Volume(parser, parser.volumes[0], sources)
