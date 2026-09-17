# depletionmode.com verification record

Framework-level evidence (real Chromium, MCP transport, profiles, Docker) lives in `docs/verification.md`. This file tracks the depletionmode server against the live public site.

Status on 2026-09-17. The site is public, so there is no authenticated state to establish: every tool below was exercised against the real site through a real MCP client talking to the running container.

Commands used:

```sh
uv run ruff check . && uv run ruff format --check . && uv run pytest -q      # 35 passed, 2 skipped
uv run python scripts/check_docker.py servers/depletionmode                  # builds, handshakes, lists 4 tools, login.required false
bin/site-mcp up depletionmode
uv run python scripts/mcp_call.py servers/depletionmode <tool> '<json>'      # one paid Jev run each
```

| Tool | Call exercised | Evidence seen | Status |
| --- | --- | --- | --- |
| `depletionmode_list_index` | `{"section":"patents"}` | Five captures covering the page top to footer; entry numbers `0x01`–`0x33` present, i.e. every entry of every section including all nine patents. Reproduced identically on four consecutive runs. | Works; `unverified` (0.63) |
| `depletionmode_list_archive` | `{"year_from":2013}` | Scrolled the index, clicked `Archive: the old stuff`, captured the archive from its heading down; years 2011–2015 observed, covering everything at or after 2013. | Works; `unverified` (0.65) |
| `depletionmode_find` | `{"query":"Themida","include_archive":false}` | Five captures; `Unpacking Themida #1`, `#2` and `#3` all present. | Works; `unverified` (0.57) |
| `depletionmode_read_post` (on-site) | `{"title":"Unpacking Themida #1"}`, `{"title":"All Your Claude Are Belong To Us - Redux"}` | The Themida post's body was first captured across three screens. After the tool moved to `read_page`, the Redux post came back whole in one capture: 4055 chars, untruncated, masthead and date through to the footer, in three steps (click, `read_page`, done). | Works; `unverified` (0.88) |
| `depletionmode_read_post` (off-site) | `{"title":"A PDF Picked My Model"}` | Followed the entry across the domain boundary to `www.originhq.com/research/a-pdf-picked-my-model`; four captures containing article body text. Origin's sticky banner occupies part of every capture. | Works, shallower evidence; `unverified` (0.70) |
| Off-site PDF entries | not called | Not exercised. By design these report a URL rather than being read; the browser's document viewer exposes no text to observe. | Not verified |
| `depletionmode_download_post_pdf` | — | **Removed from the catalog.** The post page's `Download PDF` is a `<button>` calling `window.print()`, confirmed by hooking `window.print` (1 call) and by `expect_download` timing out against a real click. No file can be produced headless, so the tool and the `attachments` file-store tools were dropped. | Impossible on this site |

## Why the listings read `unverified`

Every run above is a genuine `unverified`, not a failure. The framework's model completion check is given the final page text, the executed actions and each capture's URL and leading text. For a listing walked over several screens of a **single URL**, it sees one repeated URL and a final page text showing only the last screen, so it cannot confirm that the earlier screens covered the request; the probabilities settle around 0.6 rather than the 0.9 needed for `model_complete`.

The captured evidence is nonetheless complete, and reproducibly so — the `list_index` coverage of `0x01`–`0x33` was byte-identical across four runs. A deterministic `Task.verifier` was considered and deliberately not added: the only thing it could cheaply assert is that the footer was reached, which would not prove the requested section was captured, so it would turn the status green on a narrower claim than the tool makes. An honest `unverified` with complete evidence is the accurate report.

## Recovering from an off-site page

Because this site's `domains` follow outbound links, a `depletionmode_read_post` on an off-site entry leaves the browser on that external page, which carries no link back here. Before the framework had a `home` operation the next call started stranded there and failed; a client was seen reporting "the first list call landed on leftover Origin page state".

Exercised on 2026-09-17: `read_post` on "A PDF Picked My Model" ended on `www.originhq.com/research/a-pdf-picked-my-model`, and the following `list_index` call recovered on its first step (`home`, confidence 0.99), landed on `https://depletionmode.com/` and captured the 2026 articles. `guidance` tells the model to use `home` whenever the current page is not the front page.

## Framework changes this build required

Two defects surfaced here and were fixed in the framework, with a regression test in `tests/test_guardrails.py`:

- `runner.py` recorded a `capture` in history without `executed: true`, while the policy rules state that only executed actions changed the browser. Every capture therefore read to the model as a failed action and was retried until the no-progress guard killed the run, making any multi-screen listing impossible. Single-capture sites such as Wikipedia never hit it.
- `policy.py` passed the completion check `captured_pages` as URLs only, although its rubric allows captured evidence to satisfy a listing goal. It now passes each capture's leading text as well.
- Reading a document meant scrolling and capturing screen by screen, so a read tool returned only the screens the model happened to record; a client reported "the MCP landed mid-post" and re-called to get the rest. A `read_page` operation now records the whole page's text at once, independent of the viewport clip.
- There was no way to return to a site's own start page. The model can only click what it observes, and `start_url` is loaded once when the page is first opened, so any site permitting outbound links stranded the browser on the first external page it reached. A `home` operation, navigating to the site's own `start_url` and available on every site, was added to the action vocabulary.

Also worth knowing when handing a server over: the live-test helpers (`scripts/mcp_call.py`, `scripts/mcp_session.py`) start the container with `--debug`, which writes `WEBSITE_MCP_DEBUG_TOOLS=1` into `servers/<site>/.env` and exposes the internal `browser_status` tool to every connected client. Finish with a plain `bin/site-mcp up <site>`; this server's clients now see its four tools and nothing else, checked over raw HTTP rather than through the helpers, which re-enable debug.
