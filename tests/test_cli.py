import argparse

import pytest
from cldfbench.__main__ import main
from pycldf import Database

from pyetymdict.commands import set as setcommand


def test_set_register(capsys):
    with pytest.raises(SystemExit):
        main(['etymdict.set', '-h'])
    out, _ = capsys.readouterr()
    assert 'etymdict.set' in out


def test_set(ds, tmp_path, capsys):
    setcommand.run(argparse.Namespace(
        set='1',
        dataset=str(ds.cldf_dir),
        download_dir='',
        language_property=None,
        format='simple',
        db=None))
    out, _ = capsys.readouterr()
    assert 'root *r1' in out


def test_set_from_db(ds, tmp_path, capsys):
    db = Database(ds.cldf_reader(), fname=tmp_path / 'db.sqlite')
    db.write_from_tg()
    setcommand.run(argparse.Namespace(
        set='1',
        dataset=str(ds.cldf_dir),
        download_dir='',
        language_property=None,
        format='simple',
        db=str(tmp_path / 'db.sqlite'),))
    out, _ = capsys.readouterr()
    assert 'root *r1' in out
