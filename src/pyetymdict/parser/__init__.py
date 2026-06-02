"""
Functionality to read etymological data from plaintext.

Etymological (or comparative) dictionaries have been assembled for a long time. And some of the
longest-running data collection projects in Historical Linguistics have been devoted to creating
such a dictionary (e.g. Blust's ACD, Kaufman's PMED, or Ross et al.'s Lexicon of Proto-Oceanic).

Keeping data consistent over years, or even decades, has always been an issue for these projects.
For works like the Lexicon of Proto-Oceanic, which were published as separate volumes, this issue
was typically solved by listing errata of previous volumes in the latest one - basically accepting
inconsistency across volumes. For web-based works such as the ACD, corrections could be made at any
time - but lacking consistency checks, such changes often resulted in added inconsistency.

So, while no clear model of consistent data curation emerged from these projects, the format in
which etyma were presented was quite homogeneous. The `pyetymdict` package attempts to turn this
format into a suitable curation format, by specifying enough guard-rails to make it automatically
parseable and implementing consistency checks on top of it.

At the core of this format are etyma, reconstructed proto-forms (possibly on different levels of the
reconstruction tree) followed by a list of reflexes. Such etyma may be embedded in text. We
recognize text with the following structural (or typographic) elements:
- volume
- chapter
- section
- subsection
- page
"""
