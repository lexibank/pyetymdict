# Designing the EtymDict format


## Goals

1. It must be possible to extract a CLDF EtymDict dataset fully automatically from the format.
   Ideally, this dataset should also contain all textual information formatted as CLDF Markdown.
2. The format must be expressive enough to handle
   - Blust's ACD
   - Ross et al.'s "The lexicon of Proto-Oceanic", henceforth TloPO
   - Kaufman's PMED


## Starting point

The starting point is the plain text extracted from the PDFs of The lexicon of Proto-Oceanic.


## Proof of concept

### PMED

While the plain text extracted from the PMED as PDF is fairly easy to parse automatically, it
doesn't fully match the format used for TloPO. Thus, it should be parsed and then formatted again
to match the requirements of EtymDict.
