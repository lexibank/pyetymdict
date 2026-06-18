"""
Functionality related to the to-be-standardized EtymDict module.

This package supports a plaintext authoring format for etymological information - basically
commented etyma, i.e. reconstructions followed by lists of reflexes. Modeled on
"The lexicon of Proto-Oceanic", it supports such information encoded as multi-volume work with
the plaintext (and some supporting) data in

raw/
- vol[0-9]/
  - text.txt

The ability to robustly parse dictionary data from plaintext files (implemented in the
`pyetymdict.parser` package) relies on "controlled" data for core entities being supplied in a
structured format. In accordance with the philosophy of `cldfbench`, this data is expected in a
dataset's etc/ directory, namely:

etc/
- citation.bib - a BibTeX file containing a single entry with the bibliographical data of the whole
  (possibly multi-volume) EtymDict. This entry should be of type "book" and will be used as template
  for the citations of volumes.
- languages.csv
- sources.bib - a BibTeX file providing a consolidated bibliography across all volumes of an
  EtymDict
- gbif_taxa.csv - an optional CSV file listing biological taxa which are referenced in the EtymDict.
- orthography.tsv - a default orthography profile
- orthography/<lid>.tsv - language-specific orthography profiles (optional)


See parser/__init__.py
"""
from .tree import reconstruction_tree
from .dataset import Dataset, Form, Language

assert reconstruction_tree and Dataset and Form and Language

__version__ = '1.0.1.dev0'
