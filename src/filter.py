"""Two-stage relevance filter: cheap prefilter, then Claude adjudication."""
import json
import os
import pathlib
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

Here are positive examples of the target class -- note they span MANY fields of
economics, not just auctions/mechanism design. The economic application may be in
ANY field: trade, macro/dynamics, IO/pricing, matching, decision theory, finance,
game theory, econometrics. Do not require the paper to resemble the auction papers:
- Baldwin & Klemperer, "Demand Types and Equilibrium with Indivisibilities" (tropical hypersurface arrangements for auction equilibrium)
- Tran & Yu, "Product-Mix Auctions and Tropical Geometry"
- Crowell & Tran, "Tropical Geometry and Mechanism Design" (incentive compatibility, revenue equivalence)
- Shiozawa, "International Trade Theory and Exotic Algebras" (min-times/subtropical semirings for Ricardian trade)
- Akian, Bouhtou, Eytard & Gaubert, "A Bilevel Optimization Model for Load Balancing... through Price Incentives" (tropical geometry and discrete convexity for pricing)
- Papers using the demand-types / strong-substitutes framework (which is tropical-hypersurface machinery) even when the abstract never says "tropical".

Here are NEGATIVE examples that must be EXCLUDED (these look tempting but are pure math):
- A paper on tropical algebraic degree of network games as a computational/algebraic-geometry result, where "game" is only a source of polynomial equations and there is no economic question (no preferences, welfare, incentives, market, or equilibrium analysis in the economic sense).
- A paper on max-plus algebra spectral theory or tropical linear systems with no economic model.
- Any paper whose primary contribution is a theorem in combinatorics, algebraic geometry, or optimization, even if an economic application is mentioned in one sentence.

Decision rule: INCLUDE only if the paper contains a genuine ECONOMIC question — about preferences, valuations, incentives, welfare, prices, competitive equilibrium, mechanism/auction design, or strategic behavior with economic payoffs — AND uses tropical/min-plus machinery to address it. If the economics is merely a label, source of equations, or passing motivation, EXCLUDE. When in doubt, EXCLUDE and set relevant=false.

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


class AuthError(Exception):
    """Raised when the Anthropic API rejects the key -- fatal, abort the run."""


CACHE_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "classify_cache.json"
_cache = None


def _load_cache():
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            _cache = {}
    return _cache


def _save_cache():
    try:
        CACHE_PATH.write_text(json.dumps(_cache, indent=1, ensure_ascii=False),
                              encoding="utf-8")
    except Exception as e:
        print(f"WARN could not save classify cache: {e}")


def classify(paper):
    """Ask Claude whether the paper is in-scope. Verdicts are cached by paper
    id in data/classify_cache.json so re-runs and weekly runs never re-pay
    for papers already judged."""
    cache = _load_cache()
    pid = paper.get("id")
    if pid and pid in cache:
        return cache[pid]
    verdict = _classify_uncached(paper)
    # Only cache real verdicts, not skip/error placeholders.
    if pid and "classifier error" not in verdict.get("reason", "") \
            and "classifier skipped" not in verdict.get("reason", ""):
        cache[pid] = verdict
        _save_cache()
    return verdict


def _classify_uncached(paper):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        # No key: do NOT silently pass everything. Mark as needs-review so the
        # human sees it, but make the missing-key situation obvious.
        return {"relevant": True,
                "reason": "NEEDS REVIEW - classifier skipped, ANTHROPIC_API_KEY not set",
                "topics": []}
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
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise AuthError(
                "Anthropic API rejected the key (HTTP %d). Check that "
                "ANTHROPIC_API_KEY is set to a valid key." % e.code) from e
        print(f"WARN classify failed for {paper['id']}: {e}")
        # FAIL CLOSED: an error must never silently admit a paper.
        return {"relevant": False,
                "reason": f"classifier error ({e}) - dropped, re-run to retry",
                "topics": []}
    except Exception as e:
        print(f"WARN classify failed for {paper['id']}: {e}")
        return {"relevant": False,
                "reason": f"classifier error ({e}) - dropped, re-run to retry",
                "topics": []}


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
