# Jev Browser MCP

A Python framework for exposing website workflows as MCP tools. TypeSafe's Jev chooses actions over observed visible DOM controls; Playwright executes them in headless Chromium. Each server/account has its own persistent browser profile and file store. No Outlook/Graph API is used.

Included servers:

- **Outlook.com:** folders, filtered/time-bounded mail search, message reading, attachment downloads/uploads, read state, flags, archive/trash/restore, moves, categories, folder management, drafts, sending, replies and forwarding.
- **Framework tools:** `browser_status`, `website_task`, `files_list`, `files_put`, `files_read`.

These are Jev-driven UI workflows, not fixed selector scripts. Their completion depends on the current UI and model judgments. Responses expose observed text, controls, captured pages, downloaded files and action history. `model_complete` is explicitly probabilistic; only a supplied deterministic verifier can return `verified`. See [verification status](docs/verification.md) for what has actually been exercised.

## Run locally

Requires Python 3.12+, uv, and a TypeSafe API key. No text-generation provider is required: callers supply exact text strings in tool arguments, and Jev selects which string to type.

```sh
uv sync --frozen
uv run playwright install --with-deps chromium --only-shell
export TYPESAFE_API_KEY='your-key'
uv run jev-mcp serve --site outlook
```

`serve` speaks MCP **stdio** and waits for an MCP client. It also prints a login view URL to stderr. Run `tools --site outlook` to see the site tools without launching Chromium.

**Login happens inside the running server.** Every tool result carries a `login` block: `{"required": true, "url": "http://127.0.0.1:8765/#<token>"}` means the browser is on a sign-in or logged-out page. Open that URL: it is a local, token-protected page that shows and controls the same headless Chromium, with no Jev calls. Type the password and MFA there, not into MCP arguments, then retry the tool. While the page is a login page, tools return `login_required` without spending model calls. The session persists in the profile, so later container starts are already signed in until the site expires it.

`login --site outlook` runs the same page without MCP, for signing in ahead of time. For a normal visible Chromium login, install full Chromium (`uv run playwright install chromium`) and use `login --headed`. Only one process can hold a profile at a time.

Profiles live at `.state/<site>/<account>/profile`; files at `.state/<site>/<account>/files`. `--state-dir` changes the root; `--account work` creates another isolated account. Reuse the same options for login and serving. There is no connection to your everyday browser or imported machine credentials.

## Separate Docker containers

One container per MCP server. The container speaks MCP on stdio and publishes its login view on `127.0.0.1:8765` (`--service-ports` is what publishes it for `compose run`). The first time a tool reports `login.required`, open the URL from the result, sign in, and retry; the profile volume keeps the session for later containers.

```sh
docker compose build
```

The container takes `TYPESAFE_API_KEY` from the environment of whatever runs `docker compose`. Three ways to get it there: export it in the shell that starts the MCP client, put it in the client's `env` block for this server, or write it to `.env` next to `compose.yaml` (gitignored; see `.env.example`). Compose refuses to start without it. Never commit the key.

Use the following MCP client configuration, replacing the path with your checkout.

```json
{
  "mcpServers": {
    "outlook": {
      "command": "docker",
      "args": ["compose", "-f", "/absolute/path/jev-driven-browser-mcp/compose.yaml", "run", "--rm", "--no-deps", "--service-ports", "-T", "outlook"],
      "env": {"TYPESAFE_API_KEY": "your-key"}
    }
  }
}
```

To sign in ahead of any MCP client, run the login page alone in the same container and volume:

```sh
docker compose run --rm --service-ports outlook login --site outlook --host 0.0.0.0
# Open the printed URL, sign in, then Ctrl-C.
```

Each client starts its own container. The named volume preserves the login. Do not run `docker compose up` and stdio `compose run` simultaneously against the same account. For local stdio, use the absolute `.venv/bin/jev-mcp` executable and absolute `--state-dir`.

The shared image installs only Chromium's headless shell, Python and dependencies. It runs as UID 10001 with capabilities dropped by Compose. Chromium's inner sandbox is disabled inside this container; the container is the process boundary. Locally Chromium sandboxing defaults on. Website subresources still use the network; the navigation domain list is not a full egress firewall. Do not expose the login port publicly. The MCP transport itself has no listening port; only the login view listens, and Compose binds it to the host loopback.

## Tool examples

Search/list matching messages (dates inclusive):

```json
{"folder":"Inbox","after":"2026-09-01","before":"2026-09-17","sender":"billing@example.com","has_attachments":true,"limit":100}
```

Call `outlook_search_mail` with this object. Use observed sender, exact subject, timestamp and folder to identify a message for `outlook_read_mail`, `outlook_download_attachments` or `outlook_manage_mail`. Subjects alone may be ambiguous. Search uses Outlook search syntax; the model must check the applied UI filters. Results contain DOM evidence, not a guaranteed normalized/full-mailbox export. Pagination/scrolling is bounded; limit, timeout and truncation indicators must be respected.

To attach files, call `files_put` with `{ "filename": "invoice.pdf", "data_base64": "..." }`, then pass the returned `name` in `attachments`. Downloads also return a `name`; retrieve bytes with `files_read`, following `next_offset` until `eof`. Files persist across restarts. Direct filesystem access is confined to this server/account's file directory; no arbitrary local paths are accepted.

For workflows outside a typed tool:

```json
{
  "goal": "Open Settings, then the Rules page, and capture the list of inbox rules. Do not change anything.",
  "values": {},
  "max_steps": 20
}
```

Call `website_task`. It has the same isolated browser, domain restrictions and Jev driver.

## Operational behavior

- Tools on a profile execute serially. A filesystem lock prevents concurrent login/MCP processes from corrupting it.
- Model outputs never become selectors, JavaScript, shell commands or arbitrary URLs. Targets must be observed DOM nodes. Stale nodes and changed form values are rejected before input; the runner can re-observe up to three times when no input was dispatched. Covered controls fail execution.
- Models receive page text and caller arguments. Treat the TypeSafe service as a processor of email/business data. The dedicated login view bypasses the model. Password fields are redacted from snapshots and excluded from typing candidates.
- Website text is explicitly treated as untrusted in prompts. This is not a hard security boundary against prompt injection. MCP read-only hints describe intent; arbitrary DOM clicks cannot guarantee zero side effects (opening mail can mark it read).
- A login or logged-out page returns `login_required` with the login view URL before any model call. Timeout, low confidence, ambiguous targets, model context limits or execution errors return incomplete status. The framework never automatically retries a possibly committed action. Reconcile the visible state before retrying sends, issuance or other mutations.
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
