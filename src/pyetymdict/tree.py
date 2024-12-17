import typing

import pycldf
from pycldf.trees import TreeTable
import newick


def reconstruction_tree(cldf: pycldf.Dataset,
                        cognateset: typing.Union[str, list],
                        language_attr=None) -> newick.Node:
    """
    Plot (proto-)forms from a cognate set on a language tree.

    :param cldf:
    :param cognateset:
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

    pfs = {lid: language_attr[lid] if language_attr else '' for lid in lids}

    if isinstance(cognateset, str):
        cognateset = [
            cog for cog in cldf.objects('CognateTable')
            if cog.cldf.cognatesetReference == cognateset]

    for cog in cognateset:
        form = cog.related('formReference')
        form, lid = form.cldf.value, form.cldf.languageReference
        if lid in lids:
            if language_attr:
                pfs[lid] = '{} {}'.format(language_attr[lid], form)
            else:
                pfs[lid] = form
    tree.rename(auto_quote=True, **pfs)
    return tree
