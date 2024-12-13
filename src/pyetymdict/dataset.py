import attr

import pylexibank


@attr.s
class Language(pylexibank.Language):
    Abbr = attr.ib(
        default=None,
        metadata={'dc:description': 'Abbreviation for the (proto-)language name.'},
    )
    Group = attr.ib(
        default=None,
        metadata={
            'dc:description':
                'Etymological dictionaries often operate with an assumed internal classification. '
                'This column lists such groups.'},
    )
    Source = attr.ib(
        default=None,
        metadata={
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#source',
            'separator': ';',
            'dc:description':
                'Etymological (or comparative) dictionaries typically compare lexical data from '
                'many source dictionaries.',
        },
    )
    Is_Proto = attr.ib(
        default=False,
        metadata={
            'datatype': 'boolean',
            'dc:description':
                'Specifies whether a language is a proto-language (and thus its forms '
                'reconstructed proto-forms).',
        }
    )


@attr.s
class Form(pylexibank.Lexeme):
    Comment = attr.ib(
        default=None,
        metadata={
            'propertyUrl': 'http://clld.org/v1.0/terms.rdf#comment',
            "dc:format": "text/markdown",
            "dc:conformsTo": "CLDF Markdown",
            'dc:description':
                "Comment on the word form (and also on its membership in cognate sets)."}
    )
    Description = attr.ib(
        default=None,
        metadata={
            'propertyUrl': 'http://clld.org/v1.0/terms.rdf#description',
            "dc:format": "text/markdown",
            "dc:conformsTo": "CLDF Markdown",
            'dc:description':
                "Description of the meaning of the word (possibly in language-specific terms)."}
    )
    Sic = attr.ib(
        default=False,
        metadata={
            'datatype': 'boolean',
            'dc:description':
                "For a form that differs from the expected reflex in some way "
                "this flag asserts that a copying mistake has not occurred."}
    )


class Dataset(pylexibank.Dataset):
    language_class = Language
    lexeme_class = Form

    def schema(self, cldf, with_cf=True, with_borrowings=True):
        # Etyma, aka cognate sets or reconstructions:
        cldf.add_component(
            'CognatesetTable',
            {
                'name': 'Name',
                'dc:description':
                    'A recognizable label for the cognateset, typically the reconstructed '
                    'proto-form and the reconstructed meaning.',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#name'},
            {
                'name': 'Form_ID',
                'dc:description': 'Links to the reconstructed proto-form in FormTable.',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#formReference'},
            {
                'name': 'Comment',
                "dc:format": "text/markdown",
                "dc:conformsTo": "CLDF Markdown",
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#comment'},
            {
                'name': 'Doubt',
                'dc:description': 'Flag indicating (un)certainty of the reconstruction.',
                'datatype': 'boolean'},
        )

        if not with_cf:
            return  # pragma: no cover

        # Other groups of related lexemes can be described in "cf" tables, listed in cf.csv:
        t = cldf.add_table(
            'cf.csv',
            {
                'name': 'ID',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#id'},
            {
                'name': 'Name',
                'dc:description':
                    'The title of a table of related forms; typically hints at the type of '
                    'relation between the forms or between the group of forms and an etymon.',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#name'},
            {
                'name': 'Description',
                "dc:format": "text/markdown",
                "dc:conformsTo": "CLDF Markdown",
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#description'},
            {
                'name': 'Category',
                'dc:description': 'An optional category for groups of forms such as "loans".'},
            {
                'name': 'Comment',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#comment'},
            {
                'name': 'Cognateset_ID',
                'dc:description': 'Links to an etymon, if the group of lexemes is related to one.',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#cognatesetReference'},
        )
        t.common_props['dc:description'] = \
            ('Etymological dictionaries sometimes mention "negative" results, e.g. groups of '
             'lexemes that appear to be cognates but are (temporarily) dismissed as proper '
             'cognates; for example the "noise" and "near" categories in the ACD. This includes '
             'the better defined category of loans where members of the group will be listed in '
             'BorrowingTable.')
        # membership of lexemes in a cf group is mediated through an association table:
        t = cldf.add_table(
            'cfitems.csv',
            {
                'name': 'ID',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#id'},
            {
                'name': 'Cfset_ID'},
            {
                'name': 'Form_ID',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#formReference'},
            {
                'name': 'Comment',
                "dc:format": "text/markdown",
                "dc:conformsTo": "CLDF Markdown",
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#comment'},
            {
                'name': 'Source',
                'separator': ';',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#source'},
        )
        cldf.add_foreign_key('cfitems.csv', 'Cfset_ID', 'cf.csv', 'ID')
        t.common_props['dc:description'] = \
            ('Membership of forms in a "cf" group is mediated through this association table '
             'unless more meaningful alternatives are available, like BorrowingTable for loans.')

        if with_borrowings:
            # Loans
            cldf.add_component(
                'BorrowingTable',
                {
                    'name': 'Cfset_ID',
                    'dc:description': 'Link to a set description.'}
            )
            cldf.add_foreign_key('BorrowingTable', 'Cfset_ID', 'cf.csv', 'ID')
