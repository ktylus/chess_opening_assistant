"""
Fetches chess opening pages from Wikibooks by:
1. Paginating through Category:Book:Chess_Opening_Theory to collect all member pages
2. Filtering out pages below a minimum character length threshold
3. Saving qualifying page titles and wikitext to a JSONL file
"""

import json
import time

import requests

API_URL = "https://en.wikibooks.org/w/api.php"
CATEGORY = "Category:Book:Chess_Opening_Theory"
# Includes about 2000 chars of other page content not specific
# to the article.
MIN_LENGTH = 2500
OUTPUT_FILE = "openings.jsonl"

HEADERS = {"User-Agent": "chess-opening-assistant/1.0 (https://github.com/ktylus)"}


def api_get(params: dict) -> dict:
    params["format"] = "json"
    response = requests.get(API_URL, params=params, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def get_category_members(category: str) -> list[str]:
    """Returns all page titles in the category."""
    titles = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category,
        "cmtype": "page",
        "cmprop": "title",
        "cmlimit": "500",
    }
    while True:
        data = api_get(params)
        titles.extend(m["title"] for m in data["query"]["categorymembers"])
        if "continue" not in data:
            break
        params["cmcontinue"] = data["continue"]["cmcontinue"]

    return titles


def get_page_lengths(titles: list[str]) -> dict[str, int]:
    lengths = {}
    for i in range(0, len(titles), 10):
        batch = titles[i : i + 10]
        data = api_get(
            {
                "action": "query",
                "titles": "|".join(batch),
                "prop": "info",
            }
        )
        for page in data["query"]["pages"].values():
            if "title" in page and "length" in page:
                lengths[page["title"]] = page["length"]
    return lengths


def get_wikitext(title: str) -> str:
    data = api_get(
        {
            "action": "parse",
            "page": title,
            "prop": "wikitext",
        }
    )
    return data["parse"]["wikitext"]["*"]


def main():
    print(f"Collecting all pages in '{CATEGORY}'...")
    titles = get_category_members(CATEGORY)
    print(f"Total pages found: {len(titles)}")

    print("Fetching page lengths...")
    lengths = get_page_lengths(titles)

    qualifying = [t for t in titles if lengths.get(t, 0) >= MIN_LENGTH]
    skipped = len(titles) - len(qualifying)
    print(f"Pages >= {MIN_LENGTH} chars: {len(qualifying)} (skipped {skipped} stubs)")

    print(f"Fetching wikitext and writing to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for i, title in enumerate(qualifying, 1):
            print(f"  [{i}/{len(qualifying)}] {title}")
            try:
                wikitext = get_wikitext(title)
                record = {
                    "title": title,
                    "length": lengths[title],
                    "wikitext": wikitext,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            except Exception as e:
                print(f"    ERROR: {e}")
            time.sleep(0.5)

    print(f"\nDone. Saved {len(qualifying)} pages to {OUTPUT_FILE}.")


if __name__ == "__main__":
    main()
