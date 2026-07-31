# Growth and Docs Strategy

How we get people using the Python client and the MCP server. Written for
maintainers; it is not part of the published user docs.

Scope: the data surfaces — `pyrox-client` on PyPI and the public MCP/REST
service. The UI is out of scope here; it is a demo of the data, not the
product.

## Positioning

The repository is named after a delivery mechanism. The asset is the dataset.

> Every HYROX result, one URL. Ask it in plain English, or pull it in pandas.

Three properties do the selling, in this order:

1. **No key, no signup, no OAuth.** The MCP endpoint is public and read-only.
   Almost no remote MCP server can say that. It removes the entire activation
   step that kills adoption for hosted tools.
2. **Coverage and freshness.** Multiple seasons, every location, refreshed on a
   schedule against a verified artifact.
3. **Deterministic analytics.** Cohorts are computed server-side, in one place
   (ADR-0001), so two people asking the same question get the same answer. That
   is a genuine differentiator against "let the model write pandas".

Everything below is downstream of those three sentences.

## Audiences

| Audience | Where they are | What converts them | Funnel role |
|---|---|---|---|
| Agent / MCP users | MCP registries, connector directories, HN, dev Reddit | One copyable URL, zero auth | Highest conversion, lowest effort |
| HYROX athletes and coaches | r/hyrox, Instagram, TikTok, coaching newsletters | A chart that answers a question they already argue about | Highest volume |
| Python and data analysts | PyPI, GitHub, Colab, Kaggle, Medium | A notebook that runs without setup | Highest credibility, slowest |

They compound: athletes create demand, analysts create the credibility and the
posts athletes read, MCP registries convert both without friction. Produce each
piece of content once and cut it three ways.

Note that athletes do not want an API. They want the answer. Market the answer.

## Docs assessment

The written content is strong — filters, caching, data model, errors,
reproducible research, and a disciplined glossary in the MCP guide. The problems
are distribution and packaging, not prose.

### Fix first

1. **`[project.urls]` is commented out in `pyproject.toml`.** The PyPI page
   therefore has no homepage, docs, or repository links. PyPI is a top-of-funnel
   surface and it is currently a dead end. Two-minute fix, outsized effect. Add
   classifiers and keywords in the same pass.
2. **No docs deploy workflow.** `mkdocs.yml` and a Docs badge exist, but nothing
   in `.github/workflows/` runs `mkdocs gh-deploy`. Docs ship when someone
   remembers. Add `docs.yml` on push to `main`.
3. **Move to `mkdocs-material`.** The default theme has weak search, no dark
   mode, and no social cards, so every link shared to Reddit, X, or Slack
   renders as a bare URL with no preview image. `mkdocs-material[imaging]`
   generates a per-page card automatically. This one change does most of the
   work of "a cooler website".
4. **Add a Dataset page.** Nothing on the site states scale, coverage, or
   freshness — the single most important fact for a data provider. Generate it
   from `/api/filter-options` and `/api/races` in a script, and refresh it from
   the same workflow that refreshes the data. This also kills the current
   inconsistency where `faq.md` claims seasons 2–7 while the MCP examples use
   season 8.
5. **Publish the REST reference.** Fifteen endpoints are live and public; the
   user docs mention two of them in a footnote of `api.md`. Serve the FastAPI
   OpenAPI schema and render it in the docs. A data provider with an
   undocumented API is not a data provider.
6. **Promote MCP to a top-level tab** and lead `index.md` with it. It is the
   strongest hook and it currently sits three levels deep under "User Guide".

### Then

- **Widen install coverage.** The MCP guide covers Claude Code, Claude web, and
  Codex. Add Cursor, VS Code, Windsurf, and ChatGPT developer mode, plus
  one-click install deeplink buttons.
- **Ship `llms.txt`.** Our users are literally models. Cheap, on-brand, and it
  is a talking point in itself.
- **Show output.** An analytics product whose docs contain no charts.
  `example_notebooks/event_dists/*.png` already exist — use them.
- **Colab badges** on the three example notebooks. Zero-install trial for the
  analyst audience.
- **Resolve orphan pages.** `docs/duckdb-stabilization.md` and `docs/research/*`
  sit in the published tree but are not in the nav. Move them under
  `maintainers/` or put them in the nav deliberately.
- **Fix the dangling link** in `docs/maintainers/README.md`, which points at
  `mcp-launch-plan.md` — a file that has never existed.
- Missing and worth adding: `CHANGELOG.md`, `CONTRIBUTING.md`, and a "cite this"
  line for anyone using the data in research.

## Website

Yes, build one — but do not start with a bespoke site.

### Tier 1 — make the docs the site

`mkdocs-material` with a custom home page, social cards, dark mode, and a real
domain. This is roughly a day of work and gets most of the way there.

Buy a domain. `*.fly.dev` reads as a prototype, and a data provider is asking
people to depend on it. A domain also means we can move hosts without breaking
every link and every registry entry.

### Tier 2 — a live landing page

One static page, no framework required, that talks to the public API at load:

- **Live counters** — races, results, seasons, last refresh — read from the API.
  Proves the data is real and current in a way prose cannot.
- **The MCP endpoint** in a copy button, with one-click install buttons.
- **A "try it now" panel.** Three or four canned questions that hit
  `/api/distribution` and `/api/rankings` straight from the browser and render a
  chart. No install, no signup, works on a phone.
- **"Where would your time rank?"** — a time input against
  `/api/rankings?target_time_min=…`, returning a placement and a shareable card.
  This is the loop for the athlete audience: it is the thing people screenshot.
- **A trust strip** — schema-versioned artifacts, SHA-256 verification, weekly
  refresh, deterministic server-side cohorts, MIT licence, and the
  not-affiliated-with-HYROX disclaimer.

Hosting: Cloudflare Pages or GitHub Pages at the apex, docs at `/docs`. The
site's origin has to be added to `PYROX_API_ALLOW_ORIGINS` for the live panels
to work.

### Also: the API root is a 404

`GET /` on the service returns nothing. Anyone who trims the URL to poke around
— which is what developers do — hits a wall. Return a small JSON index: name,
version, docs URL, MCP URL, endpoint list. Free discoverability.

## Distribution

In order.

1. **Registries.** Add a `server.json` and submit to the official MCP registry,
   then PulseMCP, Glama, Smithery, `mcp.so`, the `awesome-mcp-servers` list, and
   the Anthropic connectors directory. One evening's work for permanent inbound
   traffic. This is the single highest-leverage item on the page and it is
   currently at zero.
2. **PyPI metadata**, per the docs fixes above.
3. **Colab badges** on the notebooks.
4. **r/hyrox post.** Lead with a chart and the free web widget, not the
   architecture. Nobody there knows what MCP is, and they do not need to.
5. **Show HN.** Lead with the opposite: remote MCP server, no key, read-only,
   real dataset. Link the live demo.
6. **"Season in numbers" data drops.** After each refresh, auto-generate a chart
   pack and a short write-up. Same asset works on Reddit, X, LinkedIn, and the
   site's blog, and it keeps the project visibly alive. Automate it off the
   existing refresh workflow — this is the compounding channel, the others are
   one-shots.
7. **Creator partnerships.** Coaches and HYROX content creators need structured
   numbers for their videos and newsletters. Give them the data and a link to
   cite. Cheap, and their audience is exactly audience two.

## Measurement

Instrument before launching anything, or the launch teaches us nothing.

- MCP tool-call volume, broken down per tool — tells us which questions people
  actually ask, which drives the roadmap.
- Distinct clients and repeat usage, not just totals.
- PyPI downloads, docs traffic, and the landing funnel: view → try panel →
  install.

Request logging already exists in `app.py`; a per-tool counter is a small
addition.

## Risks

- **Trademark.** Keep the "independent project, not affiliated with HYROX"
  disclaimer visible on every surface, especially a marketing site. Never use
  HYROX logos or brand styling. The risk rises with visibility, so it rises
  precisely when the marketing works.
- **Personal data.** The dataset is names attached to athletic performances. A
  public name-search box on a marketing page turns this project into a
  people-search tool and changes its privacy posture materially. Keep public,
  unauthenticated widgets to aggregate statistics and "rank my own time".
  Athlete lookup stays behind the deliberate act of connecting a client.
- **Cost and abuse.** A viral moment lands on one Fly machine with a DuckDB
  volume. Put caching in front of the aggregate endpoints and confirm the rate
  limits hold before any launch push.
