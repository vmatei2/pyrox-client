# pyrox-client — agent instructions

Repository conventions (structure, style, testing, commits) live in
`AGENTS.md`. Codebase orientation lives in the wiki below; don't duplicate
either here.

## Wiki

`wiki/` is an agent-maintained knowledge base: you write it, the human reads
it. Start every session by reading `wiki/index.md`. Pages carry `updated:` and
`sources:` frontmatter; if a source file changed after the page's date, the
code wins.

After changing code, grep the changed paths against the `sources:` lists in
`wiki/*.md`, update the affected pages (content and `updated:` date), and
append a line-or-three entry to `wiki/log.md` as
`## [YYYY-MM-DD] sync | <title>`. No affected page and no new concept means no
wiki edit; just say so in your summary. A Stop hook nags once per change-set
if code moved and `wiki/` didn't.

Analyses that took real digging get filed into the wiki (a page or an
`active-work.md` entry), not left in chat history. Run `/wiki` occasionally
for the lint checklist. `docs/` is the separate user-facing mkdocs site; the
wiki links to it rather than duplicating it.
