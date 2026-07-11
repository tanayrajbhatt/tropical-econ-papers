# Setup

A human-in-the-loop bibliography of tropical-geometry-in-economics papers, with a
weekly pipeline that proposes new papers and a static site you can share.

## How it works

```
weekly cron ──> pipeline.py ──> fetch (arXiv + OpenAlex)
                             └─> prefilter (keywords / cross-listing)
                             └─> classify (Claude adjudication)
                             └─> data/candidates.json ──> GitHub issue
                                                              │
                    you review ──> review.py ──> data/papers.json (corpus)
                                                              │
                                        render.py ──> docs/index.html ──> Pages
```

Nothing enters the corpus automatically. The pipeline only *proposes*; you approve.

## One-time setup

1. **Create the repo** and push these files to `main`.
2. **Add the API key.** Repo → Settings → Secrets and variables → Actions →
   New secret named `ANTHROPIC_API_KEY`. (Without it, the classifier is skipped
   and everything passing the prefilter becomes a candidate — noisier but works.)
3. **Enable Pages.** Settings → Pages → Source: *GitHub Actions*.
4. **Enable Actions write access.** Settings → Actions → General → Workflow
   permissions: *Read and write*, and allow Actions to create issues.
5. Replace `YOURNAME` in `src/render.py` (footer + README link) with your handle.

## Weekly loop

- Monday 08:00 UTC the pipeline runs and, if it finds anything, opens a
  **review issue** listing candidates with Claude's one-line reasons.
- Locally: `python src/review.py` (interactive y/N), or `--all`, or
  `--ids arxiv:1234,doi:10.xxxx`.
- Then `python src/render.py` and commit. Pushing to `main` redeploys the site.

You can also trigger a run anytime from the Actions tab (`Run workflow`).

## Adding a paper by hand

Append an object to `data/papers.json` (see existing entries for the shape:
`id`, `title`, `authors`, `year`, `venue`, `abstract`, `url`, `doi`, `topics`),
run `render.py`, commit.

## Tuning scope

- Broaden/narrow keyword gates in `src/fetch.py` (`TROPICAL_TERMS`, `ECON_TERMS`).
- Edit the scope definition and positive examples in `CLASSIFY_PROMPT` in
  `src/filter.py` — that prompt is where "what counts" really lives.
