"""Render docs/index.html (the shareable site) and README.md from papers.json."""
import json
import html
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAPERS = ROOT / "data" / "papers.json"
SITE = ROOT / "docs" / "index.html"
README = ROOT / "README.md"


def esc(s):
    return html.escape(str(s or ""))


def paper_card(p, n):
    authors = ", ".join(p.get("authors", []))
    topics = "".join(
        f'<span class="tag">{esc(t)}</span>' for t in p.get("topics", [])
    )
    venue = esc(p.get("venue") or "preprint")
    year = esc(p.get("year") or "")
    return f"""
      <article class="paper" data-title="{esc(p['title']).lower()}" data-authors="{esc(authors).lower()}" data-topics="{esc(' '.join(p.get('topics', []))).lower()}">
        <div class="idx"><span>{n:02d}</span></div>
        <div class="body">
          <h2><a href="{esc(p['url'])}" target="_blank" rel="noopener">{esc(p['title'])}</a></h2>
          <p class="meta">{esc(authors)}</p>
          <p class="meta sub"><span class="venue">{venue}</span> · {year}</p>
          <details class="abstract">
            <summary>Abstract</summary>
            <p>{esc(p.get('abstract',''))}</p>
          </details>
          <div class="tags">{topics}</div>
        </div>
      </article>"""


def render_site(papers):
    papers = sorted(papers, key=lambda p: (p.get("year") or 0, p.get("added") or ""), reverse=True)
    cards = "\n".join(paper_card(p, len(papers) - i) for i, p in enumerate(papers))
    count = len(papers)
    return TEMPLATE.replace("{{CARDS}}", cards).replace("{{COUNT}}", str(count))


def render_readme(papers):
    papers = sorted(papers, key=lambda p: (p.get("year") or 0), reverse=True)
    lines = [
        "# Tropical Geometry in Economics",
        "",
        "A curated, weekly-updated list of papers applying tropical geometry and "
        "min-plus methods to economics. Live site: **https://tanayrajbhatt.github.io/tropical-econ-papers/**",
        "",
        f"_{len(papers)} papers._",
        "",
    ]
    for p in papers:
        a = ", ".join(p.get("authors", [])[:4])
        lines.append(f"- [{p['title']}]({p['url']}) — {a} ({p.get('year','')}). *{p.get('venue','')}*")
    return "\n".join(lines) + "\n"


def main():
    papers = json.loads(PAPERS.read_text(encoding="utf-8"))
    SITE.parent.mkdir(exist_ok=True)
    SITE.write_text(render_site(papers), encoding="utf-8")
    README.write_text(render_readme(papers), encoding="utf-8")
    print(f"Rendered {len(papers)} papers -> {SITE}")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tropical Geometry in Economics</title>
<meta name="description" content="A curated, weekly-updated bibliography of papers applying tropical geometry and min-plus methods to economics.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root{
    --paper:#FBFAF7; --ink:#141414; --lattice:#C9C6BC;
    --accent:#3D3BD4; --muted:#6C6A63; --hair:#E4E1D8;
  }
  *{box-sizing:border-box}
  html{-webkit-text-size-adjust:100%}
  body{
    margin:0; background:var(--paper); color:var(--ink);
    font-family:"Newsreader",Georgia,serif; font-size:15px; line-height:1.5;
  }
  @media (prefers-reduced-motion: no-preference){
    .poly path{stroke-dasharray:1400;stroke-dashoffset:1400;animation:draw 2.4s ease forwards}
    .poly circle{opacity:0;animation:pop .4s ease forwards}
  }
  @keyframes draw{to{stroke-dashoffset:0}}
  @keyframes pop{to{opacity:1}}
  .wrap{max-width:860px;margin:0 auto;padding:0 24px}
  header{border-bottom:1px solid var(--ink);padding-top:44px}
  .eyebrow{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.18em;
    text-transform:uppercase;color:var(--accent);margin:0 0 14px}
  h1{font-family:"Space Grotesk",sans-serif;font-weight:700;font-size:clamp(28px,5vw,44px);
    line-height:1.03;letter-spacing:-.02em;margin:0 0 8px}
  .lede{color:var(--muted);max-width:54ch;margin:0 0 20px;font-size:15.5px}
  .poly{display:block;width:100%;height:96px;margin:6px 0 0}
  .poly path{fill:none;stroke:var(--accent);stroke-width:2}
  .poly circle{fill:var(--paper);stroke:var(--ink);stroke-width:2}
  .statline{display:flex;gap:20px;align-items:baseline;
    font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--muted);
    padding:14px 0;border-top:1px solid var(--hair);margin-top:18px}
  .statline b{color:var(--ink);font-weight:500}
  .controls{position:sticky;top:0;background:var(--paper);z-index:5;
    padding:12px 0;border-bottom:1px solid var(--hair)}
  #q{width:100%;font-family:"IBM Plex Mono",monospace;font-size:13px;
    padding:10px 12px;border:1px solid var(--lattice);background:#fff;color:var(--ink);
    border-radius:0}
  #q:focus{outline:2px solid var(--accent);outline-offset:1px;border-color:var(--accent)}
  main{padding:6px 0 64px}
  .paper{display:grid;grid-template-columns:48px 1fr;gap:16px;
    padding:22px 0;border-bottom:1px solid var(--hair)}
  .idx{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--muted);
    padding-top:4px;position:relative}
  .idx span{position:relative;z-index:1}
  .idx::before{content:"";position:absolute;left:5px;top:22px;bottom:-22px;
    width:1px;background:var(--hair)}
  .paper:last-child .idx::before{display:none}
  .idx::after{content:"";position:absolute;left:2px;top:8px;width:7px;height:7px;
    background:var(--paper);border:1.5px solid var(--accent);border-radius:50%}
  h2{font-family:"Space Grotesk",sans-serif;font-weight:600;font-size:17px;
    line-height:1.25;letter-spacing:-.01em;margin:0 0 6px}
  h2 a{color:var(--ink);text-decoration:none;background-image:linear-gradient(var(--accent),var(--accent));
    background-size:0% 1.5px;background-repeat:no-repeat;background-position:0 100%;
    transition:background-size .25s ease}
  h2 a:hover,h2 a:focus{color:var(--accent);background-size:100% 1.5px}
  .meta{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--muted);margin:0 0 2px}
  .meta.sub{margin-bottom:8px}
  .venue{color:var(--ink)}
  .abstract{margin:0 0 10px}
  .abstract summary{font-family:"IBM Plex Mono",monospace;font-size:11px;
    letter-spacing:.06em;text-transform:uppercase;color:var(--accent);
    cursor:pointer;list-style:none;display:inline-flex;align-items:center;gap:6px;
    user-select:none}
  .abstract summary::-webkit-details-marker{display:none}
  .abstract summary::before{content:"+";font-size:13px;line-height:1;
    display:inline-block;width:10px;transition:transform .2s ease}
  .abstract[open] summary::before{content:"–"}
  .abstract summary:hover{color:var(--ink)}
  .abstract p{margin:8px 0 0;color:#2b2b2b;font-size:14.5px;line-height:1.58;
    max-width:66ch}
  .tags{display:flex;flex-wrap:wrap;gap:6px}
  .tag{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.04em;
    padding:3px 7px;border:1px solid var(--lattice);color:var(--muted)}
  .empty{padding:48px 0;text-align:center;color:var(--muted);font-family:"IBM Plex Mono",monospace;font-size:13px}
  footer{border-top:1px solid var(--ink);padding:22px 0 48px;
    font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--muted)}
  footer a{color:var(--accent);text-decoration:none}
  @media(max-width:600px){
    body{font-size:14.5px}
    .paper{grid-template-columns:28px 1fr;gap:10px}
    .idx::before,.idx::after{display:none}
  }
</style>
</head>
<body>
<header>
  <div class="wrap">
    <p class="eyebrow">min-plus &middot; bibliography</p>
    <h1>Tropical Geometry<br>in Economics</h1>
    <p class="lede">Papers that bring tropical geometry and min-plus methods to auctions, matching, equilibrium, and choice. Curated by hand, refreshed weekly.</p>
    <svg class="poly" viewBox="0 0 860 120" preserveAspectRatio="none" aria-hidden="true">
      <path d="M0,96 L150,96 L330,40 L500,40 L640,84 L860,20"/>
      <circle cx="150" cy="96" r="4"/><circle cx="330" cy="40" r="4"/>
      <circle cx="500" cy="40" r="4"/><circle cx="640" cy="84" r="4"/>
    </svg>
    <div class="statline">
      <span><b>{{COUNT}}</b> papers</span>
      <span>ordered newest first</span>
      <span>tropical &cap; economic</span>
    </div>
  </div>
</header>
<div class="controls">
  <div class="wrap">
    <input id="q" type="search" placeholder="filter by title, author, or topic…" aria-label="Filter papers">
  </div>
</div>
<main>
  <div class="wrap" id="list">
{{CARDS}}
    <p class="empty" id="empty" hidden>No papers match that filter.</p>
  </div>
</main>
<footer>
  <div class="wrap">
    Contributions welcome — open an issue or PR on
    <a href="https://github.com/tanayrajbhatt/tropical-econ-papers" target="_blank" rel="noopener">GitHub</a>.
    Built with a human-in-the-loop weekly pipeline.
  </div>
</footer>
<script>
  const q=document.getElementById('q'),
        papers=[...document.querySelectorAll('.paper')],
        empty=document.getElementById('empty');
  q.addEventListener('input',()=>{
    const t=q.value.trim().toLowerCase();let shown=0;
    papers.forEach(p=>{
      const hit=!t||p.dataset.title.includes(t)||p.dataset.authors.includes(t)||p.dataset.topics.includes(t);
      p.style.display=hit?'':'none';if(hit)shown++;
    });
    empty.hidden=shown!==0;
  });
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
