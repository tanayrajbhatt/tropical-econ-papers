"""Weekly pipeline: fetch -> filter -> write candidates for human review.

Does NOT auto-add to the corpus. Writes data/candidates.json, which the
GitHub Action turns into an issue. A human moves approved entries into
data/papers.json (via the review script or by editing).
"""
import os
import datetime
import json
import pathlib

import fetch
import filter as filt
import snowball as sb

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAPERS = ROOT / "data" / "papers.json"
CANDIDATES = ROOT / "data" / "candidates.json"


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("WARNING: ANTHROPIC_API_KEY is not set. The Claude classifier will be "
              "SKIPPED, so candidates are prefilter-only and will include many "
              "false positives (pure-math papers). Set it and re-run for clean results.")
    papers = json.loads(PAPERS.read_text(encoding="utf-8"))
    known = {p["id"] for p in papers}
    # also dedup by normalized title
    known_titles = {p["title"].lower().strip() for p in papers}

    # Source 1: recency search (catches brand-new preprints nobody cites yet).
    raw = fetch.fetch_all()
    raw = [p for p in raw if p["title"].lower().strip() not in known_titles]
    new = filt.run(raw, known)

    # Source 2: citation snowball from the corpus (catches the lineage).
    # These already passed the hard tropical gate in snowball.py, so they
    # skip the search prefilter and go straight to the Claude classifier.
    try:
        sb_raw = sb.snowball(papers)
    except Exception as e:
        print(f"WARN snowball failed entirely: {e}")
        sb_raw = []
    sb_raw = [p for p in sb_raw
              if p["title"].lower().strip() not in known_titles
              and p["id"] not in known
              and p["id"] not in {c["id"] for c in new}]
    for p in sb_raw:
        verdict = filt.classify(p)
        if verdict.get("relevant"):
            p["topics"] = verdict.get("topics", [])
            p["_reason"] = verdict.get("reason", "")
            new.append(p)

    for p in new:
        p["added"] = datetime.date.today().isoformat()

    CANDIDATES.write_text(json.dumps(new, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(new)} candidate(s) written to {CANDIDATES}")
    return new


if __name__ == "__main__":
    main()
