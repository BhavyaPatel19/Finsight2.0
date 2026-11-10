"""
Check that every claim and evidence quote in a gold file is verbatim in its source PDF page
(eval/gold/LABELLING.md §5). Whitespace and typographic quotes are normalised; nothing else is.

    uv run python -m eval.gold.check_quotes eval/gold/wtt_claims_multi.jsonl

Exits non-zero if any quote is missing, so it can gate a commit.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from eval.gold.enumerate_claims import MANIFEST, page_texts

QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "})


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.translate(QUOTES)).strip()


def squash(s: str) -> str:
    # Same characters, no spaces at all: tolerates PDF line breaks inside words ("pre- qualification").
    return re.sub(r"[\s-]+", "", s.translate(QUOTES))


def found(quote: str, text: str) -> bool:
    return norm(quote) in norm(text) or squash(quote) in squash(text)


def check(path: Path) -> list[str]:
    docs = {d["key"]: d for d in json.loads(MANIFEST.read_text())["documents"]}
    cache: dict[str, list[dict]] = {}

    def page(doc: str, n: int) -> str:
        if doc not in cache:
            cache[doc] = page_texts(docs[doc])
        pages = cache[doc]
        # a sentence may run onto the next page
        return " ".join(p["text"] for p in pages if p["page"] in (n, n + 1))

    errors = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        # `quote` holds the verbatim sentence when `claim` restates one part of a two-part sentence
        if not found(row.get("quote") or row["claim"], page(row["claims_doc"], row["claim_page"])):
            errors.append(f"{row['id']}: claim not on {row['claims_doc']} p{row['claim_page']}")
        for ev in row.get("evidence", []):
            if not found(ev["quote"], page(ev["doc"], ev["page"])):
                errors.append(f"{row['id']}: evidence not on {ev['doc']} p{ev['page']}: {ev['quote'][:60]}…")
        if row["human_verdict"] != "UNVERIFIABLE" and not row.get("evidence"):
            errors.append(f"{row['id']}: {row['human_verdict']} needs evidence")
    return errors


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "eval/gold/wtt_claims_multi.jsonl")
    errors = check(path)
    n = sum(1 for line in path.read_text().splitlines() if line.strip())
    for e in errors:
        print("FAIL", e)
    print(f"{n} labels, {len(errors)} problems")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
