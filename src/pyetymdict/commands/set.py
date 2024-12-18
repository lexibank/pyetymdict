"""
Display a cognate set.

For large EtymDict datasets it will typically be a lot quicker to run this command against the
SQLite database created from the dataset via `cldf createdb`. If such a database is available, its
path can be passed using the `--db` option.
"""
import types
import dataclasses

from termcolor import colored
from bs4 import BeautifulSoup
from markdown import markdown
import pycldf
from pycldf.cli_util import add_dataset, get_dataset
from clldutils.clilib import Table, add_format
from pycldf.db import Database

from pyetymdict.tree import reconstruction_tree


def register(parser):
    add_dataset(parser)
    parser.add_argument('--set', default=None, help="ID or Name of the cognate set.")
    parser.add_argument(
        '--language-property',
        default=None,
        help="Name of a language property (i.e. of a column in LanguageTable) to plot as labels "
             "on the tree as well.",
    )
    add_format(parser, default='simple')
    parser.add_argument('--db', default=None)


@dataclasses.dataclass
class Cognateset:
    id: str
    comment: str
    form: str
    meaning: str
    language: str

    @property
    def cldf(self):
        return types.SimpleNamespace(comment=self.comment)

    def related(self, what):
        assert what == 'formReference'
        return types.SimpleNamespace(
            cldf=types.SimpleNamespace(value=self.form, description=self.meaning),
            language=types.SimpleNamespace(cldf=types.SimpleNamespace(name=self.language))
        )


class Source:
    def __init__(self, key):
        self.key = key

    def refkey(self):
        return self.key


@dataclasses.dataclass
class Cognate:
    ds: pycldf.Dataset
    lid: str
    lname: str
    is_proto: str
    form: str
    meaning: str
    source: str

    def related(self, what):
        assert what == 'formReference'
        return types.SimpleNamespace(
            dataset=self.ds,
            cldf=types.SimpleNamespace(
                value=self.form, description=self.meaning, languageReference=self.lid),
            language=types.SimpleNamespace(
                cldf=types.SimpleNamespace(name=self.lname),
                data=dict(Is_Proto=self.is_proto == 1),
            )
        )

    @property
    def references(self):
        return [types.SimpleNamespace(source=Source(src)) for src in (self.source or '').split()]


def run(args):
    cldf = get_dataset(args)
    # Aggregate the subsets linked to the etymon:
    css = []
    db = Database(cldf, fname=args.db) if args.db else None
    if db:
        if not args.set:
            for i, res in enumerate(db.query("""
select cs.cldf_id, cs.cldf_comment, f.cldf_value, f.cldf_description, l.cldf_name
from cognatesettable as cs, formtable as f, languagetable as l
where  l.cldf_id = f.cldf_languageReference
and f.cldf_id = cs.cldf_formReference
""")):
                css.append(Cognateset(*res))
        else:
            for i, res in enumerate(db.query("""
select cs.cldf_id, cs.cldf_comment, f.cldf_value, f.cldf_description, l.cldf_name
from cognatesettable as cs, formtable as f, languagetable as l
where  l.cldf_id = f.cldf_languageReference
    and f.cldf_id = cs.cldf_formReference
    and (cs.cldf_id = ? or f.cldf_value like ?);
""", (args.set, '%' + args.set.replace('*', '') + '%'))):
                css.append(Cognateset(*res))
    else:
        for cs in cldf.objects('CognatesetTable'):
            if args.set:
                if cs.id == args.set or args.set.replace('*', '') in cs.cldf.name.replace('*', ''):
                    css.append(cs)
                    break
            else:
                css.append(cs)
    if not css:
        raise ValueError()  # pragma: no cover

    for cs in css:
        print_cs(args, cldf, db, cs)


def print_cs(args, cldf, db, cs):
    if db:
        cognates = []
        for res in db.query("""
    select
        l.cldf_id,
        l.cldf_name,
        l.is_proto,
        f.cldf_value,
        f.cldf_description,
        group_concat(csrc.SourceTable_id, ' ')
    from languagetable as l, formtable as f, cognatetable as c
    left join CognateTable_SourceTable as csrc on c.cldf_id = csrc.CognateTable_cldf_id
    where l.cldf_id = f.cldf_languageReference
        and c.cldf_formReference = f.cldf_id
        and c.cldf_cognatesetReference = ?
    group by l.cldf_id, l.cldf_name, l.is_proto, f.cldf_value, f.cldf_description
    """, (cs.id,)):
            cognates.append(Cognate(cldf, *res))
    else:
        cognates = [
            cog for cog in cldf.objects('CognateTable') if cog.cldf.cognatesetReference == cs.id]

    protoform = cs.related('formReference')
    print("\n{} {} '{}'\n".format(
        colored(protoform.language.cldf.name, 'green', attrs=['bold']),
        colored('*' + protoform.cldf.value, 'red', attrs=['bold']),
        protoform.cldf.description,
    ))
    if 'TreeTable' in cldf:
        tree = reconstruction_tree(cldf, cognates, language_attr=args.language_property)
        print(tree.ascii_art())
        print('')
    with Table(args, 'Language', 'Form', 'Meaning', 'Source') as t:
        for cog in cognates:
            form = cog.related('formReference')
            t.append([
                fmt_lang(form.language), fmt_form(form), fmt_meaning(form), fmt_references(cog)])
    if cs.cldf.comment:
        print('')
        print(fmt_comment(cs.cldf.comment, cldf))


def fmt_references(obj):
    return '; '.join(ref.source.refkey() for ref in obj.references)


def fmt_form(obj):
    return colored(
        '{}{}'.format(
            '*' if obj.language.data['Is_Proto'] and not obj.cldf.value.startswith('*') else '',
            obj.cldf.value),
        'red' if obj.language.data['Is_Proto'] else 'blue')


def fmt_meaning(obj):
    return '‘{}’'.format(fmt_comment(obj.cldf.description, obj.dataset))


def fmt_lang(obj):
    return colored(obj.cldf.name, 'red' if obj.data['Is_Proto'] else 'light_green')


def fmt_comment(t, cldf):
    if not t:
        return ''
    bs = BeautifulSoup(markdown(t), 'html.parser')
    for a in bs.find_all('a'):
        if a['href'].startswith('LanguageTable'):
            a.replace_with(fmt_lang(cldf.get_object('LanguageTable', a['href'].split(':')[-1])))
        if a['href'].startswith('Source'):
            a.replace_with(colored(a.text, attrs=['underline']))
    for a in bs.find_all('em'):
        a.replace_with(a.text if a.text in ['Cf.'] else colored(a.text, 'blue'))
    return bs.get_text().replace('&ast;', '*')
