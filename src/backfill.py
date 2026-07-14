"""One-time backfill: map the existing universe of tropical-econ papers.

Walks the citation graph from the current corpus to closure, classifying
each tropical-gated paper WITH CLAUDE INSIDE THE WALK: only papers judged
economically relevant expand the frontier. This confines the closure to the
tropical-ECONOMICS subgraph -- without it, the walk absorbs the entire
tropical geometry / tropical ML literature.

Usage (PowerShell):
    $env:ANTHROPIC_API_KEY = "sk-ant-..."
    py src/backfill.py

Optional: $env:S2_API_KEY = "..."   (free Semantic Scholar key, avoids 429s)

Outputs:
    data/candidates.json     -- relevant papers, review with `py src/review.py`
    data/backfill_report.md  -- keeps AND rejects, for spot-checking
"""
import json
import os
import pathlib
import sys

import filter as filt
import snowball as sb

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAPERS = ROOT / "data" / "papers.json"
CANDIDATES = ROOT / "data" / "candidates.json"
REPORT = ROOT / "data" / "backfill_report.md"

FIXPOINT_DEPTH = 25          # effectively "until closure"
MAX_CANDIDATES = 400         # safety cap on gated-graph size


def verify_key():
    """Fail fast if the Anthropic key is missing or invalid."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is not set. The backfill requires the "
              "classifier; without it the citation graph explodes into the "
              "whole tropical-geometry literature.")
        sys.exit(1)
    probe = {"title": "Product-Mix Auctions and Tropical Geometry",
             "abstract": "We use tropical geometry to characterize competitive "
                         "equilibrium in product-mix auctions.",
             "id": "probe"}
    try:
        verdict = filt.classify(probe)
    except filt.AuthError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    if not verdict.get("relevant"):
        print("WARNING: classifier rejected an obvious positive on the probe "
              "call; check the API key and model access before trusting results.")
    print("API key verified.")


def main():
    verify_key()
    corpus = json.loads(PAPERS.read_text(encoding="utf-8"))
    print(f"Backfill from {len(corpus)} corpus papers. This will take a while...")

    try:
        results = sb.snowball(corpus, depth=FIXPOINT_DEPTH,
                              max_candidates=MAX_CANDIDATES,
                              classify_fn=filt.classify)
    except filt.AuthError as e:
        print(f"\nFATAL: {e}\nAborting -- no candidates written.")
        sys.exit(1)

    accepted = [p for p in results if p.get("_relevant")]
    rejected = [p for p in results if not p.get("_relevant")]
    for p in accepted:
        p.pop("_relevant", None)
    accepted.sort(key=lambda p: (p.get("year") or 0))

    CANDIDATES.write_text(json.dumps(accepted, indent=2, ensure_ascii=False),
                          encoding="utf-8")

    lines = [
        "# Backfill report", "",
        f"Corpus seeds: {len(corpus)} | Passed tropical gate: {len(results)} | "
        f"Classifier kept: {len(accepted)} | Rejected: {len(rejected)}", "",
        "## Candidates (review with `py src/review.py`)", "",
    ]
    for p in accepted:
        a = ", ".join(p.get("authors", [])[:4])
        lines.append(f"- **{p['title']}** — {a} ({p.get('year','?')})  ")
        lines.append(f"  {p.get('_reason','')}  ")
        lines.append(f"  via `{p.get('source','')}` — {p['url']}")
    lines += ["", "## Rejected by classifier (spot-check for false negatives)", ""]
    for p in sorted(rejected, key=lambda x: (x.get("year") or 0)):
        lines.append(f"- {p['title']} ({p.get('year','?')}) — {p.get('_reason','')}")
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n{len(accepted)} candidates -> {CANDIDATES}")
    print(f"{len(rejected)} rejects logged in -> {REPORT}")
    print("Next: py src/review.py, then py src/render.py, then commit & push.")


if __name__ == "__main__":
    main()
