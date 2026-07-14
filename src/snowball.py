"""Citation-graph snowball: find papers citing / cited by the corpus.

For every paper in the corpus (identified by arXiv ID or DOI), fetch its
citations and references from the Semantic Scholar Academic Graph API, and
keep only those that use tropical / min-plus language (hard gate). The Claude
classifier in filter.py then adjudicates economic relevance.

Because the corpus grows as papers are approved, the citation graph is
explored incrementally: each weekly run snowballs one hop from the current
corpus. For a one-off deeper backfill, set SNOWBALL_DEPTH=2.
"""
import json
import os
import time
import urllib.parse
import urllib.request

from fetch import TROPICAL_TERMS

S2_API = "https://api.semanticscholar.org/graph/v1/paper"
FIELDS = "title,abstract,year,venue,externalIds,authors,url"
UA = {"User-Agent": "tropical-econ-papers/1.0 (citation snowball)"}


def _get_json(url, retries=2):
    headers = dict(UA)
    s2_key = os.environ.get("S2_API_KEY")
    if s2_key:
        headers["x-api-key"] = s2_key
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(10 * (attempt + 1))  # back off on rate limit
                continue
            raise
    return None


def _s2_id(paper):
    """Map a corpus paper to a Semantic Scholar paper identifier."""
    pid = paper.get("id", "")
    if pid.startswith("arxiv:"):
        return "arXiv:" + pid.split(":", 1)[1]
    if pid.startswith("doi:"):
        return "DOI:" + pid.split(":", 1)[1]
    if paper.get("doi"):
        return "DOI:" + paper["doi"]
    return None


# In the citation graph of tropical-econ papers, the bare word "tropical"
# almost always means the mathematics (unlike in open web search, where it
# usually means climate). So the snowball gate accepts bare terms too.
SNOWBALL_TERMS = TROPICAL_TERMS + [
    "tropical", "max-plus", "minplus", "maxplus",
]


def _has_tropical(text):
    text = (text or "").lower()
    return any(t.lower() in text for t in SNOWBALL_TERMS)


def _to_candidate(item, via, relation):
    """Convert an S2 paper record to our candidate schema."""
    ext = item.get("externalIds") or {}
    if ext.get("ArXiv"):
        pid = f"arxiv:{ext['ArXiv']}"
        url = f"https://arxiv.org/abs/{ext['ArXiv']}"
    elif ext.get("DOI"):
        pid = f"doi:{ext['DOI']}"
        url = f"https://doi.org/{ext['DOI']}"
    else:
        pid = f"s2:{item.get('paperId','')}"
        url = item.get("url") or ""
    return {
        "id": pid,
        "title": item.get("title") or "",
        "authors": [a.get("name", "") for a in (item.get("authors") or [])],
        "year": item.get("year"),
        "venue": item.get("venue") or "preprint",
        "abstract": item.get("abstract") or "",
        "url": url,
        "doi": ext.get("DOI"),
        "categories": [],
        "source": f"snowball:{relation}:{via}",
    }


def _fetch_edges(s2_id, edge):
    """edge is 'citations' or 'references'. Returns list of S2 paper dicts."""
    out = []
    offset = 0
    while True:
        params = urllib.parse.urlencode(
            {"fields": FIELDS, "limit": 100, "offset": offset})
        url = f"{S2_API}/{urllib.parse.quote(s2_id)}/{edge}?{params}"
        data = _get_json(url)
        if not data:
            break
        key = "citingPaper" if edge == "citations" else "citedPaper"
        for row in (data.get("data") or []):
            p = row.get(key)
            if p:
                out.append(p)
        nxt = data.get("next")
        if nxt is None or offset >= 900:  # hard cap per seed per edge
            break
        offset = nxt
        time.sleep(1)
    return out


def snowball(corpus, depth=None, max_candidates=500, classify_fn=None):
    """Snowball hop(s) of the citation graph from the corpus.

    Iterates up to `depth` hops (default from SNOWBALL_DEPTH env, else 1),
    stopping early when the frontier is empty (fixpoint) or when
    `max_candidates` is reached.

    If `classify_fn` is given, every gated paper is classified immediately
    and ONLY papers judged relevant join the frontier. This confines the
    transitive closure to the tropical-ECON subgraph instead of the whole
    tropical-geometry literature. Each returned candidate then carries
    "_relevant", "_reason", and "topics".
    """
    depth = depth or int(os.environ.get("SNOWBALL_DEPTH", "1"))
    known = {p["id"] for p in corpus}
    frontier = list(corpus)
    seen_s2 = set()
    candidates = {}

    for hop in range(depth):
        if not frontier:
            print(f"snowball: fixpoint reached after {hop} hop(s)")
            break
        print(f"snowball: hop {hop + 1}, frontier size {len(frontier)}")
        next_frontier = []
        for paper in frontier:
            if len(candidates) >= max_candidates:
                print(f"snowball: stopped at max_candidates={max_candidates}")
                return list(candidates.values())
            sid = _s2_id(paper)
            if not sid or sid in seen_s2:
                continue
            seen_s2.add(sid)
            for edge, relation in (("citations", "cites"),
                                   ("references", "cited-by")):
                try:
                    items = _fetch_edges(sid, edge)
                except Exception as e:
                    print(f"WARN snowball {edge} failed for {sid}: {e}")
                    continue
                time.sleep(1)  # politeness between calls
                for item in items:
                    text = f"{item.get('title','')} {item.get('abstract','')}"
                    if not _has_tropical(text):
                        continue  # hard tropical gate
                    cand = _to_candidate(item, paper["id"], relation)
                    if cand["id"] in known or cand["id"] in candidates:
                        continue
                    if classify_fn is not None:
                        verdict = classify_fn(cand)
                        cand["_relevant"] = bool(verdict.get("relevant"))
                        cand["_reason"] = verdict.get("reason", "")
                        cand["topics"] = verdict.get("topics", [])
                        candidates[cand["id"]] = cand
                        if cand["_relevant"]:
                            next_frontier.append(cand)
                        print(f"    {'KEEP' if cand['_relevant'] else 'drop'} "
                              f"{cand['title'][:64]}")
                    else:
                        candidates[cand["id"]] = cand
                        next_frontier.append(cand)
        frontier = next_frontier

    return list(candidates.values())


if __name__ == "__main__":
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    corpus = json.loads((root / "data" / "papers.json").read_text(encoding="utf-8"))
    cands = snowball(corpus)
    print(f"{len(cands)} tropical candidates from citation graph")
    for c in cands[:20]:
        print(f"  [{c['source']}] {c['title'][:70]}")
