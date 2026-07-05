# Attribution and license — Wikibooks openings data

The files in this directory (`raw_openings.jsonl`, `cleaned_openings.jsonl`) are
derived from the Wikibooks book **"Chess Opening Theory"**:

- Source: https://en.wikibooks.org/wiki/Chess_Opening_Theory
- Publisher: English Wikibooks, a project of the Wikimedia Foundation
- Authors: the Wikibooks contributors to that book (see each page's revision
  history via the URLs below)

Each record in `raw_openings.jsonl` carries a `title` field
(e.g. `Chess Opening Theory/1. a4`) that identifies its source page. The page
URL is `https://en.wikibooks.org/wiki/` followed by the title with spaces
replaced by underscores.

## License

This data is licensed under the **Creative Commons Attribution-ShareAlike
License, version 4.0** (CC BY-SA 4.0), matching the terms
under which Wikibooks text is made available.

- CC BY-SA 4.0: https://creativecommons.org/licenses/by-sa/4.0/

Under ShareAlike, any redistribution of this data or adaptations of it must be
released under the same license.

## Modifications

The original wikitext was retrieved and stored in `raw_openings.jsonl`. The
`cleaned_openings.jsonl` file is an adaptation: wiki markup, templates,
references, and internal links were stripped, and per-position metadata
(name, PGN, EPD) was added. These are modifications of the original Wikibooks
content.

## Relation to the rest of this repository

This license applies only to the files in this directory. The project's source
code is licensed separately under the MIT License (see `LICENSE` at the
repository root).
