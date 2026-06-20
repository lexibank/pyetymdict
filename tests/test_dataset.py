import logging
import argparse
import contextlib

from pycldf import Wordlist
from pycldf.trees import TreeTable

from pyetymdict.dataset import Dataset


def test_dataset(tmp_path, ds):
    cldf = Wordlist.in_dir(tmp_path)
    ds.schema(cldf)


def test_dataset_non_default(ds2):
    assert ds2


def test_dataset_add_tree(tmp_path, CLTS_api):
    class DS(Dataset):
        id = 'test'
        dir = tmp_path

        def cmd_makecldf(self, args):
            self.add_tree(args.writer, '((lang,lang2)pmp)poc;', names=dict(poc='POc'))

    ds = DS()
    ds._cmd_makecldf(argparse.Namespace(
        dev=True,
        verbose=False,
        clts=CLTS_api,
        log=logging.getLogger(__name__)))


def test_dataset_glottolog_cldf(ds, mocker, testsdir):
    mocker.patch('builtins.input', lambda *args, **kw: str(testsdir / 'glottolog-cldf'))
    mocker.patch('pyetymdict.dataset.Catalog', lambda d, *args, **kw: contextlib.nullcontext(d))
    res = ds.glottolog_cldf_languoids('')
    assert 'surm1244' in res


def test_dataset_makecldf(ds):
    for tree in TreeTable(ds.cldf_reader()):
        break
    else:
        raise AssertionError()  # pragma: no cover
    assert {n.name for n in tree.newick().walk()} == {'lang', 'lang2', 'pmp', 'poc'}
