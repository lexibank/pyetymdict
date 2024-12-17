import contextlib

from pycldf import Wordlist
from pycldf.trees import TreeTable


def test_dataset(tmp_path, ds):
    cldf = Wordlist.in_dir(tmp_path)
    ds.schema(cldf)


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
    assert {n.name for n in tree.newick().walk()} == {'r', 'l1', 'l2'}
