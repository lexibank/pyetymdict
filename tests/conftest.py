import logging
import pathlib
import argparse

import pytest

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
            self.schema(args.writer.cldf)
            args.writer.objects['LanguageTable'].append(dict(ID='r', Name='root', Is_Proto=True))
            args.writer.objects['LanguageTable'].append(dict(ID='l1', Name='language1', Is_Proto=False))
            args.writer.objects['LanguageTable'].append(dict(ID='l2', Name='language2', Is_Proto=False))
            self.add_tree(args.writer, '(l2,l1)root', names={'root': 'r', 'l1': 'l1', 'l2': 'l2'})
            args.writer.objects['ParameterTable'].append(dict(ID='p1'))
            args.writer.objects['FormTable'].append(
                dict(ID='1', Value='f1', Form='f1', Language_ID='l1', Parameter_ID='p1'))
            args.writer.objects['FormTable'].append(
                dict(ID='2', Value='r1', Form='r1', Language_ID='r', Parameter_ID='p1'))
            args.writer.objects['CognateTable'].append(dict(ID='1', Form_ID='1', Cognateset_ID='1'))
            args.writer.objects['CognateTable'].append(dict(ID='2', Form_ID='2', Cognateset_ID='1'))

    ds = DS()
    ds._cmd_makecldf(argparse.Namespace(
        dev=True,
        verbose=False,
        log=logging.getLogger(__name__)))
    return ds
