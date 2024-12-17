from pyetymdict import reconstruction_tree


def test_reconstruction_tree(ds):
    tree = reconstruction_tree(ds.cldf_reader(), '1')
    assert all(f in [n.name for n in tree.walk()] for f in ['f1', 'r1'])

    tree = reconstruction_tree(ds.cldf_reader(), '1', language_attr='Name')
    assert 'language1 f1' in [n.unquoted_name for n in tree.walk()]
