"""
etc/languages.csv
"""
import functools
import dataclasses
from typing import Any, Union, Optional

import pylexibank
from segments import Profile
from pyglottolog.languoids import Languoid

from . import util


@dataclasses.dataclass
class Language(pylexibank.Language):
    """Languages in an EtymDict might be Proto-Languages."""
    Abbr: Optional[str] = dataclasses.field(  # pylint: disable=C0103
        default=None,
        metadata={'dc:description': 'Abbreviation for the (proto-)language name.'},
    )
    Group: Optional[str] = dataclasses.field(  # pylint: disable=C0103
        default=None,
        metadata={
            'dc:description':
                'Etymological dictionaries often operate with an assumed internal classification. '
                'This column lists such groups.'},
    )
    Source: list[str] = dataclasses.field(  # pylint: disable=C0103
        default_factory=list,
        metadata={
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#source',
            'separator': ';',
            'dc:description':
                'Etymological (or comparative) dictionaries typically compare lexical data from '
                'many source dictionaries.',
        },
    )
    Is_Proto: bool = dataclasses.field(  # pylint: disable=C0103
        default=False,
        metadata={
            'datatype': 'boolean',
            'dc:description':
                'Specifies whether a language is a proto-language (and thus its forms '
                'reconstructed proto-forms).',
        }
    )
    Alternative_Names: list[str] = dataclasses.field(  # pylint: disable=C0103
        default_factory=list,
        metadata={'separator': ';', 'dc:description': 'Alternative names for the (proto-)language'},
    )


@dataclasses.dataclass
class Languoids:
    """Access to the data in etc/languages.csv and etc/orthography."""
    langs: list[dict[str, Any]]
    by_name: dict[str, dict[str, Any]]
    orthography_profiles: dict[Union[None, str], Profile]
    language_class: type

    @classmethod
    def from_dataset(cls, dataset):
        """Initialize from a dataset object, relaying access to the relevant data in etc/."""
        langs = {v['Name']: v for v in dataset.languages}
        for v in list(langs.values()):
            for alt in util.split(v.get('Alternative_Names', '')):
                assert alt not in langs, alt
                langs[alt] = v

        return cls(
            langs=dataset.languages,
            by_name=langs,
            orthography_profiles=dataset.orthography_profile_dict,
            language_class=dataset.language_class,
        )

    @functools.cached_property
    def proto_languages(self) -> list[dict[str, Any]]:
        """Proto languages - identified by not being assigned to any reflex group."""
        return [v for v in self.langs if not v['Group']]

    @functools.cached_property
    def reflex_groups(self) -> list[str]:
        """The language group names used for reflexes."""
        return sorted({v['Group'] for v in self.langs if v['Group']})

    @functools.cached_property
    def reflex_group_regex(self) -> str:
        """The language group names used for reflexes as regex."""
        return util.re_choice(self.reflex_groups)

    def orthography_profile(self, name: str) -> Profile:
        """Returns the orthography profile for a language specified by name."""
        lid = self.by_name[name]['ID']
        return self.orthography_profiles.get(lid, self.orthography_profiles[None])

    def grapheme_tokens(self, name):
        """
        For a preliminary check of transcriptions we return a string concatenating all graphemes
        from the relevant profile. This string can be used to lookup individual unicode characters,
        rather than fully-formed graphemes, which often consist of multiple unicode characters.
        """
        profile = self.orthography_profile(name)
        return ''.join(profile.graphemes) + '-'

    def add(self,
            writer: pylexibank.LexibankWriter,
            glangs: dict[str, Languoid],
            ldicts: dict[str, list[str]]):
        """
        Add the languoids as rows in LanguageTable to a dataset.
        """
        for lg in self.langs:
            #if not lg['Group']:
            #    assert any((lg[c] or 'x').split()[0] in
            #               {'Early', 'Proto'} for c in ('Alternative_Names', 'Name'))
            res = dict(  # pylint: disable=R1735
                ID=lg['ID'],
                Name=lg['Name'],
                Glottocode=lg['Glottocode'],
                Glottolog_Name=glangs[lg['Glottocode']].name if lg['Glottocode'] else None,
                Group=lg['Group'],
                Latitude=lg['Latitude'],
                Longitude=lg['Longitude'],
                Is_Proto=not bool(lg['Group']),
                Source=ldicts.get(lg['Glottocode'], []),
                Alternative_Names=util.split(lg['Alternative_Names']),
            )
            # We support custom language classes by relaying custom fields from etc/languages.csv:
            for f in dataclasses.fields(self.language_class):
                if f.name not in res and f.name in lg:
                    res[f.name] = lg[f.name]
            writer.add_language(**res)
