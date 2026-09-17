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
| `depletionmode_read_post` (on-site) | `{"title":"Unpacking Themida #1"}` | Opened `/unpacking-themida-1/`; body captured across three screens, including the disassembly and Hex-Rays listing. | Works; `unverified` (0.64) |
| `depletionmode_read_post` (off-site) | `{"title":"A PDF Picked My Model"}` | Followed the entry across the domain boundary to `www.originhq.com/research/a-pdf-picked-my-model`; four captures containing article body text. Origin's sticky banner occupies part of every capture. | Works, shallower evidence; `unverified` (0.70) |
| Off-site PDF entries | not called | Not exercised. By design these report a URL rather than being read; the browser's document viewer exposes no text to observe. | Not verified |
| `depletionmode_download_post_pdf` | — | **Removed from the catalog.** The post page's `Download PDF` is a `<button>` calling `window.print()`, confirmed by hooking `window.print` (1 call) and by `expect_download` timing out against a real click. No file can be produced headless, so the tool and the `attachments` file-store tools were dropped. | Impossible on this site |

## Why the listings read `unverified`

Every run above is a genuine `unverified`, not a failure. The framework's model completion check is given the final page text, the executed actions and each capture's URL and leading text. For a listing walked over several screens of a **single URL**, it sees one repeated URL and a final page text showing only the last screen, so it cannot confirm that the earlier screens covered the request; the probabilities settle around 0.6 rather than the 0.9 needed for `model_complete`.

The captured evidence is nonetheless complete, and reproducibly so — the `list_index` coverage of `0x01`–`0x33` was byte-identical across four runs. A deterministic `Task.verifier` was considered and deliberately not added: the only thing it could cheaply assert is that the footer was reached, which would not prove the requested section was captured, so it would turn the status green on a narrower claim than the tool makes. An honest `unverified` with complete evidence is the accurate report.

## Framework changes this build required

Two defects surfaced here and were fixed in the framework, with a regression test in `tests/test_guardrails.py`:

- `runner.py` recorded a `capture` in history without `executed: true`, while the policy rules state that only executed actions changed the browser. Every capture therefore read to the model as a failed action and was retried until the no-progress guard killed the run, making any multi-screen listing impossible. Single-capture sites such as Wikipedia never hit it.
- `policy.py` passed the completion check `captured_pages` as URLs only, although its rubric allows captured evidence to satisfy a listing goal. It now passes each capture's leading text as well.
