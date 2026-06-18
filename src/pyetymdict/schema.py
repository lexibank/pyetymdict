from typing import Optional

import pycldf

from .taxa import Taxa


def schema(
        cldf: pycldf.Dataset,
        with_cf: bool = True,
        with_borrowings: bool = True,
):
    """Add the EtymDict-specific schema."""
    cldf.add_component('TreeTable')
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
    cldf.add_component(
        'MediaTable',
        {
            'name': 'Chapter_ID',
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#contributionReference'},
        {
            'name': 'Conforms_To',
            'propertyUrl': 'http://purl.org/dc/terms/conformsTo'},
    )
    if 'ContributionTable' not in cldf:
        cldf.add_component('ContributionTable')
    cldf.add_columns(
        'ContributionTable',
        {'name': 'Volume_Number', 'datatype': 'integer'},
        'Volume',
        {'name': 'Table_Of_Contents', 'datatype': 'json'},
        {
            'name': 'Source',
            'separator': ';',
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#source'},
        {'name': 'Source_To_Sections', 'datatype': 'json'},
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
            "dc:format": "text/markdown",
            "dc:conformsTo": "CLDF Markdown",
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
