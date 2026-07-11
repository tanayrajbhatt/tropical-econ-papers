"""Fetch candidate papers from arXiv and OpenAlex."""
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

TROPICAL_TERMS = [
    "tropical geometry", "tropical hypersurface", "min-plus", "max-plus",
    "polytrope", "Newton polytope", "tropical linear", "tropical semiring",
    "tropical convexity", "tropical polynomial",
]
ECON_TERMS = [
    "economic", "auction", "equilibrium", "market", "utility", "preference",
    "mechanism design", "matching", "pricing", "welfare", "game theory",
]

ARXIV_API = "http://export.arxiv.org/api/query"
OPENALEX_API = "https://api.openalex.org/works"
UA = {"User-Agent": "tropical-econ-papers/1.0 (mailto:you@example.com)"}


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def fetch_arxiv(max_results=100):
    """Search arXiv for tropical terms, cross-listed with econ/math categories."""
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    query = " OR ".join(f'all:"{t}"' for t in TROPICAL_TERMS)
    params = {
        "search_query": f"({query})",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
    root = ET.fromstring(_get(url))
    for e in root.findall("a:entry", ns):
        arxiv_id = e.find("a:id", ns).text.split("/abs/")[-1].split("v")[0]
        cats = [c.get("term") for c in e.findall("a:category", ns)]
        out.append({
            "id": f"arxiv:{arxiv_id}",
            "title": " ".join(e.find("a:title", ns).text.split()),
            "authors": [a.find("a:name", ns).text for a in e.findall("a:author", ns)],
            "year": int(e.find("a:published", ns).text[:4]),
            "venue": "preprint",
            "abstract": " ".join(e.find("a:summary", ns).text.split()),
            "url": e.find("a:id", ns).text,
            "doi": None,
            "categories": cats,
            "source": "arxiv",
        })
    return out


def fetch_openalex(max_results=100):
    """Search OpenAlex full text for tropical geometry + econ concepts."""
    out = []
    search = "tropical geometry economics"
    params = {
        "search": search,
        "per-page": min(max_results, 50),
        "sort": "publication_date:desc",
    }
    url = f"{OPENALEX_API}?{urllib.parse.urlencode(params)}"
    import json
    data = json.loads(_get(url))
    for w in data.get("results", []):
        doi = (w.get("doi") or "").replace("https://doi.org/", "") or None
        # reconstruct abstract from inverted index
        abstract = ""
        inv = w.get("abstract_inverted_index")
        if inv:
            positions = {}
            for word, idxs in inv.items():
                for i in idxs:
                    positions[i] = word
            abstract = " ".join(positions[i] for i in sorted(positions))
        pid = doi or w["id"].split("/")[-1]
        out.append({
            "id": f"doi:{doi}" if doi else f"openalex:{pid}",
            "title": w.get("title") or "",
            "authors": [a["author"]["display_name"] for a in w.get("authorships", [])],
            "year": w.get("publication_year"),
            "venue": (w.get("primary_location") or {}).get("source", {} ).get("display_name") or "preprint",
            "abstract": abstract,
            "url": w.get("doi") or w["id"],
            "doi": doi,
            "categories": [],
            "source": "openalex",
        })
    return out


def fetch_all():
    results = []
    for fn in (fetch_arxiv, fetch_openalex):
        try:
            results.extend(fn())
        except Exception as e:
            print(f"WARN {fn.__name__} failed: {e}")
        time.sleep(1)
    return results


if __name__ == "__main__":
    import json
    print(json.dumps(fetch_all(), indent=2)[:2000])
