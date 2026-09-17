# Verification record

Date: 2026-09-17. This separates implemented interfaces from demonstrated behavior. No authenticated Outlook account has yet been supplied. Live mailbox workflows remain an acceptance gate; the repository is not claiming those integrations are production-verified.

## Demonstrated

- Real headless Chromium: input, native select, click, iframe controls, open shadow DOM, file upload, download bytes, navigation restrictions, stale-target rejection and rejection when a different form field changes before submission.
- Profile lifecycle: authentication-like local storage persists across browser restart; different account profiles cannot read it; a concurrent process cannot open the same profile.
- Local human login view: unauthorized screen/actions rejected; authorized screenshot, coordinate click and text input operate actual headless Chromium. No Jev calls are involved in this path.
- Strict Content Security Policy: Chromium snapshots and field entry work without enabling `unsafe-eval` or bypassing CSP. This regression was discovered on the public Outlook page.
- MCP: official client initializes each server over stdio, discovers typed tools, uploads and reads binary attachment chunks, and receives an error on file traversal. The Outlook server advertises 12 site tools plus 5 framework tools; Wikipedia 1 plus 5.
- Real Jev API + actual Chromium, local fixture: exact recipient, subject and body entered; draft saved; independent DOM verifier checks every field and the saved status. Also selects High priority, uploads exact receipt bytes and downloads an invoice exactly once; verifier checks resulting UI and downloaded contents.
- Public third-site extension: Jev searched Wikipedia for Ada Lovelace and opened the article; independent checks confirmed the URL, heading and article content. This exposed and led to fixes for oversized DOM prompts and stale preflight recovery.
- False completion: a `done` decision with insufficient evidence remains `unverified`; execution errors are not replayed.
- Packaging: source distribution and wheel build; wheel contains JavaScript, login HTML and both site modules. Docker builds a shared headless-shell image; Compose gives the two services separate volumes and containers.
- Docker MCP smoke: the server initializes and lists tools from a real container; headless Chromium reaches a readable public Outlook landing page.

Commands:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
RUN_LIVE_JEV=1 uv run pytest -q -s
uv build
docker compose config --quiet
docker compose -f servers/wikipedia/compose.yaml build
uv run python scripts/check_docker.py servers/wikipedia servers/outlook
# Paid, read-only public-site extension check:
uv run python scripts/check_public_site.py
```

The offline suite has 19 tests plus two explicitly skipped live-model tests. A Starlette/AnyIO deprecation warning is currently non-failing.

## Remaining live acceptance

Per-site acceptance against real accounts is tracked next to each server: `servers/outlook/verification.md`. The framework does not claim any site works until that file shows evidence from a signed-in session. No unrequested real email was sent during development.
