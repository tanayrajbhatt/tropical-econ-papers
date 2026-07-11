"""Approve candidates into the corpus.

Usage:
  python src/review.py                 # interactive: y/n per candidate
  python src/review.py --all           # approve every candidate
  python src/review.py --ids A,B,C     # approve specific ids
Then run render.py to rebuild the site.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAPERS = ROOT / "data" / "papers.json"
CANDIDATES = ROOT / "data" / "candidates.json"


def load(p):
    return json.loads(p.read_text()) if p.exists() else []


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def main():
    papers = load(PAPERS)
    cands = load(CANDIDATES)
    if not cands:
        print("No candidates.")
        return

    approve_all = "--all" in sys.argv
    ids = None
    for a in sys.argv:
        if a.startswith("--ids"):
            ids = set(sys.argv[sys.argv.index(a) + 1].split(","))

    kept, remaining = [], []
    for c in cands:
        take = approve_all or (ids and c["id"] in ids)
        if not take and ids is None and not approve_all:
            print(f"\n{c['title']}\n  {', '.join(c['authors'][:4])} ({c.get('year')})")
            print(f"  reason: {c.get('_reason','')}")
            print(f"  {c['url']}")
            take = input("  approve? [y/N] ").strip().lower() == "y"
        (kept if take else remaining).append(c)

    for c in kept:
        c.pop("_reason", None)
        c.pop("categories", None)
    papers.extend(kept)
    save(PAPERS, papers)
    save(CANDIDATES, remaining)
    print(f"\nApproved {len(kept)}, {len(remaining)} left in candidates.")


if __name__ == "__main__":
    main()
