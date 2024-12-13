from pycldf import Wordlist

from pyetymdict.dataset import Dataset


def test_dataset(tmp_path):
    class DS(Dataset):
        id = 'test'
        dir = tmp_path

    ds = DS()
    cldf = Wordlist.in_dir(tmp_path)
    ds.schema(cldf)
