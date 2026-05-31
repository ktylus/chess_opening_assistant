import json
import re
import sys
from pathlib import Path

import mwparserfromhell

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.chess_utils.eco_codes import EcoCodeLookup

SECTIONS_TO_DROP = {"history", "theory table", "references", "see also"}


def extract_opening_name(parsed):
    """Pull the opening name from the Chess Opening Theory/Position template."""
    for template in parsed.filter_templates():
        if "Chess Opening Theory/Position" in template.name:
            name = template.get(1).value.strip() if template.has(1) else None
            return {"name": name}
    return {}


def _clean_markup(text):
    """Resolve wikilinks to display text, then strip bold/italic markers."""
    # [[link|display]] -> display, [[link]] -> link
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", lambda m: m.group(2), text)
    text = re.sub(r"\[\[([^\]]+)\]\]", lambda m: m.group(1), text)
    # strip ''' and ''
    text = text.replace("'''", "").replace("''", "")
    return text.strip()


def extract_main_prose(wikitext):
    """Return only the prose sections, dropping unwanted ones."""
    # Split on == headings (level 2+)
    parts = re.split(r"(={2,}[^=]+={2,})", wikitext)

    kept = []
    include = (
        True  # include content before the first heading (preamble / position template)
    )

    for part in parts:
        heading_match = re.match(r"(={2,})([^=]+)={2,}", part)
        if heading_match:
            heading_text = heading_match.group(2).strip().lower()
            include = not any(drop in heading_text for drop in SECTIONS_TO_DROP)
        elif include:
            kept.append(part)

    return "".join(kept)


def parse_pgn_from_title(title):
    prefix = "Chess Opening Theory/"
    if not title or not title.startswith(prefix):
        return None
    segments = title[len(prefix) :].split("/")
    moves = []
    for seg in segments:
        # Black move: "1...e5" -> "e5"
        black = re.match(r"\d+\.\.\.(.+)", seg)
        if black:
            moves.append(black.group(1))
        else:
            moves.append(seg)
    return " ".join(moves)


def clean_article(wikitext, title=None, eco_lookup=None):
    parsed = mwparserfromhell.parse(wikitext)
    metadata = extract_opening_name(parsed)
    metadata["pgn"] = parse_pgn_from_title(title)
    metadata["eco"] = (
        eco_lookup.get(metadata["pgn"]) if eco_lookup and metadata["pgn"] else None
    )

    prose_wikitext = extract_main_prose(wikitext)
    parsed_prose = mwparserfromhell.parse(prose_wikitext)

    # Strip all remaining templates and <ref> tags
    plain = parsed_prose.strip_code(
        normalize=True,
        collapse=True,
        keep_template_params=False,
    )

    plain = _clean_markup(plain)

    # Fix encoding artifact and strip mediawiki directives
    plain = plain.replace("Â·", "·").replace("Â·", "·")
    plain = re.sub(r"__[A-Z]+__", "", plain)

    # Collapse excess blank lines
    plain = re.sub(r"\n{3,}", "\n\n", plain).strip()

    return {"metadata": metadata, "text": plain}


INPUT = "data/wikibooks_openings/raw_openings.jsonl"
OUTPUT = "data/wikibooks_openings/cleaned_openings.jsonl"

eco_lookup = EcoCodeLookup()

with (
    open(INPUT, encoding="utf-8") as f_in,
    open(OUTPUT, "w", encoding="utf-8") as f_out,
):
    for i, line in enumerate(f_in):
        raw = json.loads(line)
        try:
            result = clean_article(
                raw["wikitext"], title=raw.get("title"), eco_lookup=eco_lookup
            )
            f_out.write(json.dumps(result, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[{i}] Failed on '{raw.get('title')}': {e}")

print(f"Done. Output written to {OUTPUT}")
