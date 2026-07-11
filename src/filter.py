"""Two-stage relevance filter: cheap prefilter, then Claude adjudication."""
import json
import os
import urllib.request

from fetch import TROPICAL_TERMS, ECON_TERMS

MATH_CATS = {"math.AG", "math.CO", "math.OC", "math.MG"}
ECON_CATS = {"econ.TH", "econ.EM", "econ.GN", "q-fin.EC"}

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
MODEL = "claude-opus-4-8"

CLASSIFY_PROMPT = """You are curating a bibliography of papers that genuinely APPLY \
tropical geometry (or min-plus / max-plus algebra, tropical convexity, Newton \
polytopes used tropically) to ECONOMICS or economic theory (auctions, matching, \
mechanism design, general equilibrium, pricing, game theory, choice theory).

INCLUDE only if the paper substantively uses tropical/min-plus mathematical \
machinery AND has a real economic application or motivation.

EXCLUDE: papers about tropical agriculture/climate/biology; pure tropical geometry \
with no economics; pure economics with no tropical methods; papers that only mention \
one side in passing.

Here are positive examples of the target class:
- Baldwin & Klemperer, "Demand Types and Equilibrium with Indivisibilities" (tropical hypersurface arrangements for auction equilibrium)
- Tran & Yu, "Product-Mix Auctions and Tropical Geometry"

Respond with ONLY a JSON object: {"relevant": true|false, "reason": "<one sentence>", "topics": ["...","..."]}

Title: {title}
Abstract: {abstract}"""


def prefilter(paper):
    """Cheap keyword / category gate."""
    text = f"{paper.get('title','')} {paper.get('abstract','')}".lower()
    has_trop = any(t.lower() in text for t in TROPICAL_TERMS)
    has_econ = any(t.lower() in text for t in ECON_TERMS)
    cats = set(paper.get("categories") or [])
    cross_listed = bool(cats & MATH_CATS) and bool(cats & ECON_CATS)
    return (has_trop and has_econ) or (has_trop and cross_listed)


def classify(paper):
    """Ask Claude whether the paper is in-scope. Returns dict or None on error."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        # No key: fall back to prefilter verdict, flag for manual review.
        return {"relevant": True, "reason": "prefilter only (no API key)", "topics": []}
    prompt = CLASSIFY_PROMPT.replace("{title}", paper.get("title", "")) \
                            .replace("{abstract}", paper.get("abstract", "")[:2000])
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(ANTHROPIC_API, data=body, headers={
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        text = "".join(b["text"] for b in data["content"] if b["type"] == "text")
        return json.loads(text.strip().strip("`").replace("json\n", "", 1))
    except Exception as e:
        print(f"WARN classify failed for {paper['id']}: {e}")
        return {"relevant": True, "reason": f"classifier error: {e}", "topics": []}


def run(candidates, known_ids):
    """Return list of new, relevant candidates with classifier metadata."""
    accepted = []
    for p in candidates:
        if p["id"] in known_ids:
            continue
        if not prefilter(p):
            continue
        verdict = classify(p)
        if verdict.get("relevant"):
            p["topics"] = verdict.get("topics", [])
            p["_reason"] = verdict.get("reason", "")
            accepted.append(p)
    return accepted
