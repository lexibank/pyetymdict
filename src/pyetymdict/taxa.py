"""
Biological taxa are supported as follows:

1. Taxa are assumed to be referenced in text (including glosses) by using their (binomial)
   name, marked up with leading and trailing underscores, e.g. _Panthera leo_.
2. Taxa that might be encountered in text must be "declared" in a file etc/gbif_taxa.csv
   with the following columns:
   > ID,name,name_eng,rank,kingdom,phylum,class,order,family,genus,genus_eng,family_eng,synonyms
   It is recommended to only list accepted taxa in this file. Should the text refer to one
   of these using a synonym, this synonym can be added to the row of the corresponding
   accepted taxon.
"""
import dataclasses

from csvw.dsv import reader

from . import util


@dataclasses.dataclass
class Taxa:
    taxa: list[dict[str, str]]
    names: dict[str, str]

    @classmethod
    def from_file(cls, p):
        names, rows = {}, []
        for row in reader(p, dicts=True):
            # ID,name,name_eng,rank,kingdom,phylum,class,order,family,genus,genus_eng,family_eng,
            # synonyms
            rows.append(row)
            if row['synonyms']:
                for syn in util.split(row.get('synonyms')):
                    syn = syn.strip()
                    names['_' + syn + '_'] = row['ID']
            names['_' + row['name'] + '_'] = row['ID']
        return cls(rows, names)

    def match(self, text):
        if not text:
            return []
        return [v for k, v in self.names.items() if k in text]

    @staticmethod
    def schema(cldf):
        cldf.add_table(
            'taxa.csv',
            {'name': 'ID', 'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#id'},
            {'name': 'GBIF_ID', 'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#gbifReference'},
            {'name': 'name', 'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#name'},
            {'name': 'name_eng'},
            {'name': 'rank', 'datatype': {'base': 'string', 'format': 'SPECIES|GENUS'}},
            {'name': 'kingdom'},
            {'name': 'phylum'},
            {'name': 'class'},
            {'name': 'order'},
            {'name': 'family'},
            {'name': 'genus'},
            {'name': 'genus_eng'},
            {'name': 'family_eng'},
            {'name': 'synonyms', 'separator': '; '},
            {'name': 'sections', 'datatype': 'json'},
        )

    def add(self, writer, taxon2sections):
        for row in self.taxa:
            row['GBIF_ID'] = row['ID']
            row['synonyms'] = util.split(row.get('synonyms'))
            row['sections'] = taxon2sections.get(row['ID'], [])
            writer.objects['taxa.csv'].append(row)
