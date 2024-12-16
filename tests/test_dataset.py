import pathlib
import contextlib

import pytest

from pycldf import Wordlist

from pyetymdict.dataset import Dataset


@pytest.fixture
def testsdir():
    return pathlib.Path(__file__).parent


@pytest.fixture
def ds(tmp_path):
    class DS(Dataset):
        id = 'test'
        dir = tmp_path

    return DS()


def test_dataset(tmp_path, ds):
    cldf = Wordlist.in_dir(tmp_path)
    ds.schema(cldf)


def test_dataset_(ds, mocker, testsdir):
    mocker.patch('builtins.input', lambda *args, **kw: str(testsdir / 'glottolog-cldf'))
    mocker.patch('pyetymdict.dataset.Catalog', lambda d, *args, **kw: contextlib.nullcontext(d))
    res = ds.glottolog_cldf_languoids('')
    assert 'surm1244' in res
