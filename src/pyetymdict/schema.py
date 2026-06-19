"""
CLDF metadata for the schema of an EtymDict.
"""
import pycldf

def cldf_markdown_comment() -> dict[str, str]:
    """A CSVW column spec for a CLDF Markdwon Comment column."""
    return {
        'name': 'Comment',
        "dc:format": "text/markdown",
        "dc:conformsTo": "CLDF Markdown",
        'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#comment'}


def schema(cldf: pycldf.Dataset):
    """Add the EtymDict-specific schema."""
    cldf.add_component('TreeTable')
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
