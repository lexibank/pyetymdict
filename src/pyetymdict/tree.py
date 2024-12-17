import pycldf
from pycldf.trees import TreeTable
import newick


def reconstruction_tree(cldf: pycldf.Dataset, csid: str, language_attr=None) -> newick.Node:
    """
    Plot (proto-)forms from a cognate set on a language tree.

    :param cldf:
    :param csid:
    :param language_attr:
    :return:
    """
    for tree in TreeTable(cldf):
        tree = tree.newick()
        break
    else:
        raise ValueError('no tree in dataset')  # pragma: no cover
    lids = [n.name for n in tree.walk() if n.name]
    if language_attr:
        language_attr = {
            r['id']: r[language_attr] for r in cldf.iter_rows('LanguageTable', 'id')}
    forms = {
        f['id']: (f['value'], f['languageReference'])
        for f in cldf.iter_rows('FormTable', 'id', 'languageReference', 'value')}
    pfs = {lid: language_attr[lid] if language_attr else '' for lid in lids}
    for cog in cldf.iter_rows('CognateTable', 'cognatesetReference', 'formReference'):
        if cog['cognatesetReference'] == csid:
            form, lid = forms[cog['formReference']]
            if lid in lids:
                if language_attr:
                    pfs[lid] = '{} {}'.format(language_attr[lid], form)
                else:
                    pfs[lid] = form
    tree.rename(auto_quote=True, **pfs)
    return tree
