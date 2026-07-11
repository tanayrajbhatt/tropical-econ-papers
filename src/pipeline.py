"""Weekly pipeline: fetch -> filter -> write candidates for human review.

Does NOT auto-add to the corpus. Writes data/candidates.json, which the
GitHub Action turns into an issue. A human moves approved entries into
data/papers.json (via the review script or by editing).
"""
import datetime
import json
import pathlib

import fetch
import filter as filt

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAPERS = ROOT / "data" / "papers.json"
CANDIDATES = ROOT / "data" / "candidates.json"


def main():
    papers = json.loads(PAPERS.read_text(encoding="utf-8"))
    known = {p["id"] for p in papers}
    # also dedup by normalized title
    known_titles = {p["title"].lower().strip() for p in papers}

    raw = fetch.fetch_all()
    raw = [p for p in raw if p["title"].lower().strip() not in known_titles]

    new = filt.run(raw, known)
    for p in new:
        p["added"] = datetime.date.today().isoformat()

    CANDIDATES.write_text(json.dumps(new, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(new)} candidate(s) written to {CANDIDATES}")
    return new


if __name__ == "__main__":
    main()
