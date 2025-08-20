import string
import logging
import pathlib
import argparse

import pytest
from csvw.dsv import reader
from pycldf.sources import Source, Sources

from pyetymdict import Dataset


@pytest.fixture
def testsdir():
    return pathlib.Path(__file__).parent


@pytest.fixture
def ds(tmp_path):
    class DS(Dataset):
        id = 'test'
        dir = tmp_path

        def cmd_makecldf(self, args):
            self.schema(args.writer.cldf, with_cf=False)
            args.writer.cldf.add_sources('@misc{key,\ntitle={t}}')
            args.writer.objects['LanguageTable'].append(dict(ID='r', Name='root', Is_Proto=True))
            args.writer.objects['LanguageTable'].append(dict(ID='l1', Name='language1', Is_Proto=False))
            args.writer.objects['LanguageTable'].append(dict(ID='l2', Name='language2', Is_Proto=False))
            self.add_tree(args.writer, '(l2,l1)root', names={'root': 'r', 'l1': 'l1', 'l2': 'l2'})
            args.writer.objects['ParameterTable'].append(dict(ID='p1'))
            args.writer.objects['FormTable'].append(
                dict(ID='1', Value='f1', Form='f1', Language_ID='l1', Parameter_ID='p1'))
            args.writer.objects['FormTable'].append(
                dict(ID='2', Value='r1', Form='r1', Language_ID='r', Parameter_ID='p1'))
            args.writer.objects['CognateTable'].append(dict(ID='1', Form_ID='1', Cognateset_ID='1', Source=['key']))
            args.writer.objects['CognateTable'].append(dict(ID='2', Form_ID='2', Cognateset_ID='1'))
            args.writer.objects['CognatesetTable'].append(dict(
                ID='1',
                Comment='See also [language1](LanguageTable#cldf:l1) _form_ ([x](Source#cldf:y))',
                Form_ID='2'))

    ds = DS()
    ds._cmd_makecldf(argparse.Namespace(
        dev=True,
        verbose=False,
        log=logging.getLogger(__name__)))
    return ds


@pytest.fixture(scope='session')
def repos():
    return pathlib.Path(__file__).parent / 'repos'


@pytest.fixture(scope='session')
def parser(repos):
    from pyetymdict.parser.models import Parser

    return Parser(
        [repos / 'raw' / 'vol1'],
        {r['Name']: r for r in reader(repos / 'etc' / 'languages.csv', dicts=True)},
        Source.from_bibtex('@book{b,\nauthor={a},\ntitle={the title}}'),
        Sources.from_file(repos / 'etc' / 'sources.bib'),
        {
            'POc': list(string.ascii_lowercase),
            'PMP': list(string.ascii_lowercase),
        },
        list(string.ascii_lowercase),
        ['Adm', 'NNG'],
        pos_map={'N': 'N', 'V': 'V', 'VT': 'VT'},
        kinship_tags=['PZ'],
    )


@pytest.fixture(scope='session')
def volume1(parser):
    return parser.volumes[0]
