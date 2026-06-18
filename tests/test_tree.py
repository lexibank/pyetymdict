from pyetymdict import reconstruction_tree


def test_reconstruction_tree(ds):
    tree = reconstruction_tree(ds.cldf_reader(), '1-1-1-1-None-poc-mata-a')
    names = [n.name for n in tree.walk()]
    for f in ['mata', 'word']:
        assert f in names

    tree = reconstruction_tree(ds.cldf_reader(), '1-1-1-1-None-poc-mata-a', language_attr='Name')
    assert 'Bebeli' in [n.unquoted_name for n in tree.walk()]
