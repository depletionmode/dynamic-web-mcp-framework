# Jev Browser MCP

A Python framework for exposing website workflows as MCP tools. TypeSafe's Jev chooses actions over observed visible DOM controls; Playwright executes them in headless Chromium. Each server/account has its own persistent browser profile and file store. No Outlook/Graph or Morning business API is used.

Included servers:

- **Outlook.com:** folders, filtered/time-bounded mail search, message reading, attachment downloads/uploads, read state, flags, archive/trash/restore, moves, categories, folder management, drafts, sending, replies and forwarding.
- **Morning / חשבונית ירוקה:** document search/read/PDF downloads, document drafts and issuance, document emailing, customers, expenses and report exports. Uses the live app at `app.greeninvoice.co.il`.
- **Framework tools:** `browser_status`, `website_task`, `files_list`, `files_put`, `files_read`.

These are Jev-driven UI workflows, not fixed selector scripts. Their completion depends on the current UI and model judgments. Responses expose observed text, controls, captured pages, downloaded files and action history. `model_complete` is explicitly probabilistic; only a supplied deterministic verifier can return `verified`. See [verification status](docs/verification.md) for what has actually been exercised.

## Run locally

Requires Python 3.12+, uv, and a TypeSafe API key. No text-generation provider is required: callers supply exact text strings in tool arguments, and Jev selects which string to type.

```sh
uv sync --frozen
uv run playwright install --with-deps chromium --only-shell
export TYPESAFE_API_KEY='your-key'
uv run jev-mcp login --site outlook
# Open the URL printed to stderr; sign in and complete MFA.
# Ctrl-C closes Chromium and releases the profile.
uv run jev-mcp serve --site outlook
```

`serve` speaks MCP **stdio**; it normally waits for an MCP client. Run `tools --site outlook` to see the site tools without launching Chromium. Replace `outlook` with `morning` for the other server.

Login defaults to a local, token-protected web page displaying and controlling the same headless browser. It makes no Jev calls. Type passwords/MFA into that page, not MCP arguments. For a normal visible Chromium login, install full Chromium (`uv run playwright install chromium`) and use `login --headed`. Login and MCP cannot use the same profile concurrently.

Profiles live at `.state/<site>/<account>/profile`; files at `.state/<site>/<account>/files`. `--state-dir` changes the root; `--account work` creates another isolated account. Reuse the same options for login and serving. There is no connection to your everyday browser or imported machine credentials. To switch Morning businesses, explicitly name the business in `website_task`, then use its typed tools.

## Separate Docker containers

```sh
docker compose build
# Login with the Outlook volume, publishing the login view to localhost only.
docker compose run --rm -p 127.0.0.1:8765:8765 outlook login --site outlook --host 0.0.0.0
# Sign in via printed URL, then Ctrl-C.
docker compose run --rm -p 127.0.0.1:8766:8766 morning login --site morning --host 0.0.0.0 --port 8766
# Sign in, then Ctrl-C.
```

Use the following MCP client configuration, replacing the path with your checkout. `TYPESAFE_API_KEY` must be available to the Docker Compose process (export it or place it in an ignored `.env`). Never put keys in committed client configuration.

```json
{
  "mcpServers": {
    "outlook": {
      "command": "docker",
      "args": ["compose", "-f", "/absolute/path/jev-driven-browser-mcp/compose.yaml", "run", "--rm", "--no-deps", "-T", "outlook"]
    },
    "morning": {
      "command": "docker",
      "args": ["compose", "-f", "/absolute/path/jev-driven-browser-mcp/compose.yaml", "run", "--rm", "--no-deps", "-T", "morning"]
    }
  }
}
```

Each client starts its own container. Separate named volumes preserve each site's login. Do not run `docker compose up` and stdio `compose run` simultaneously against the same account. For local stdio, use the absolute `.venv/bin/jev-mcp` executable and absolute `--state-dir`.

The shared image installs only Chromium's headless shell, Python and dependencies. It runs as UID 10001 with capabilities dropped by Compose. Chromium's inner sandbox is disabled inside this container; the container is the process boundary. Locally Chromium sandboxing defaults on. Website subresources still use the network; the navigation domain list is not a full egress firewall. Do not expose the login port publicly. The MCP transport itself has no listening port.

## Tool examples

Search/list matching messages (dates inclusive):

```json
{"folder":"Inbox","after":"2026-09-01","before":"2026-09-17","sender":"billing@example.com","has_attachments":true,"limit":100}
```

Call `outlook_search_mail` with this object. Use observed sender, exact subject, timestamp and folder to identify a message for `outlook_read_mail`, `outlook_download_attachments` or `outlook_manage_mail`. Subjects alone may be ambiguous. Search uses Outlook search syntax; the model must check the applied UI filters. Results contain DOM evidence, not a guaranteed normalized/full-mailbox export. Pagination/scrolling is bounded; limit, timeout and truncation indicators must be respected.

To attach files, call `files_put` with `{ "filename": "invoice.pdf", "data_base64": "..." }`, then pass the returned `name` in `attachments`. Downloads also return a `name`; retrieve bytes with `files_read`, following `next_offset` until `eof`. Files persist across restarts. Direct filesystem access is confined to this server/account's file directory; no arbitrary local paths are accepted.

Create a Morning invoice draft:

```json
{
  "document_type": "tax_invoice",
  "customer": "Example Ltd — tax ID 123456789",
  "date": "2026-09-17",
  "currency": "ILS",
  "language": "en",
  "items": [{"description":"Consulting","quantity":"1","unit_price":"1000.00","vat":"excluded"}]
}
```

Call `morning_create_draft`; issuance is a separate `morning_issue_document` call identifying the saved draft. Receipt types require caller-supplied payment details. The framework does not calculate accounting rules, choose VAT treatment, or invent missing values.

For workflows outside a typed tool:

```json
{
  "goal": "Select the business named Example Ltd, then stop on its dashboard.",
  "values": {"business_name": "Example Ltd"},
  "max_steps": 20
}
```

Call `website_task`. It has the same isolated browser, domain restrictions and Jev driver.

## Operational behavior

- Tools on a profile execute serially. A filesystem lock prevents concurrent login/MCP processes from corrupting it.
- Model outputs never become selectors, JavaScript, shell commands or arbitrary URLs. Targets must be observed DOM nodes. Stale nodes and changed form values are rejected before input; the runner can re-observe up to three times when no input was dispatched. Covered controls fail execution.
- Models receive page text and caller arguments. Treat the TypeSafe service as a processor of email/business data. The dedicated login view bypasses the model. Password fields are redacted from snapshots and excluded from typing candidates.
- Website text is explicitly treated as untrusted in prompts. This is not a hard security boundary against prompt injection. MCP read-only hints describe intent; arbitrary DOM clicks cannot guarantee zero side effects (opening mail can mark it read).
- Timeout, low confidence, login challenges, ambiguous targets, model context limits or execution errors return incomplete status. The framework never automatically retries a possibly committed action. Reconcile the visible state before retrying sends, issuance or other mutations.
- Common HTML/ARIA controls, open shadow DOM, allowed-origin frames, popups, nested scrolling, uploads and downloads are supported. Canvas-only UIs, closed shadow DOM, native OS dialogs and site anti-bot restrictions may require human intervention. JavaScript dialogs are dismissed.
- Runs are bounded by 60 steps (tool-specific overrides), 240 seconds, 25 captured pages, 350 controls/frame and 12,000 visible text characters/frame. Set `TASK_TIMEOUT` and `JEV_MIN_CONFIDENCE` via environment. The default confidence threshold 0.15 is a starting point, not calibrated reliability. Files upload up to 10 MiB; reads are chunked at up to 1 MiB.

## Develop and extend

Read [the agent guide](docs/BUILDING_SERVERS.md) and [architecture](docs/architecture.md). A runnable third-site example is [wiki_site.py](examples/wiki_site.py).

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
# Optional paid Jev test, using a local fixture and independent DOM verification:
RUN_LIVE_JEV=1 uv run pytest tests/test_live_jev.py -q -s
uv build
```

Design references: [Jev Ultrafast](https://github.com/browser-use/jev-ultrafast), [TypeSafe Python SDK](https://docs.typesafe.ai/sdk/python), [speculative fan-out](https://docs.typesafe.ai/patterns/fan-out), [Playwright persistent Chromium contexts](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context), and the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk). This implementation is original; it uses the indexed-choice approach, with an isolated Playwright runtime and exact caller values in place of the demo's attached browser and text-generating helper.
