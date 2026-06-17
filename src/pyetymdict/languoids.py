import functools
import dataclasses
from typing import Any, Union

from segments import Profile

from . import util


@dataclasses.dataclass
class Languoids:
    langs: list[dict[str, Any]]
    by_name: dict[str, dict[str, Any]]
    orthography_profiles: dict[Union[None, str], Profile]

    @classmethod
    def from_dataset(cls, dataset):
        langs = {v['Name']: v for v in dataset.languages}
        for v in list(langs.values()):
            for alt in util.split(v.get('Alternative_Names', '')):
                assert alt not in langs, alt
                langs[alt] = v

        return cls(
            langs=dataset.languages,
            by_name=langs,
            orthography_profiles=dataset.orthography_profile_dict)

    @functools.cached_property
    def proto_languages(self):
        return [v for v in self.langs if not v['Group']]

    @functools.cached_property
    def reflex_groups(self):
        return sorted({v['Group'] for v in self.langs if v['Group']})

    def orthography_profile(self, name):
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
