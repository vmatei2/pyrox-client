@AGENTS.md

# Claude-specific documentation rules

`codewiki_docs/overview.md` is the sole engineering architecture map. It is for
humans and agents, generated through `/codewiki`, and intentionally concise.
Do not add module chapters or a second `wiki/` knowledge base.

A Stop hook enforces that completed file-changing handoffs state the
architecture-impact decision required by `AGENTS.md`. The agent performs the
semantic review; the hook checks that the decision is explicit and does not
force an edit after every code change.

When sources disagree, precedence is: code and tests, user/maintainer `docs/`,
then `codewiki_docs/overview.md`.
