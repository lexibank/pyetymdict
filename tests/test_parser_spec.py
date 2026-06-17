import pathlib

from pyetymdict.parser.spec import VolumeDir


def test_VolumeDir_iter_figures():
    vd = VolumeDir(pathlib.Path(__file__).parent / 'repos' / 'raw' / 'vol1')
    res = list(vd.iter_figures('[](MediaTable#cldf:fig-1-1)'))
    assert len(res) == 1
