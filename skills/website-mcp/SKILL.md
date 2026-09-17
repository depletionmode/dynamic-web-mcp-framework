---
name: website-mcp
description: Build an MCP server that drives any website through headless Chromium and the Jev model, on the dynamic-web-mcp-framework. Use when the user says "Make an MCP of website X", "add a site to the web MCP framework", or wants an agent to operate a web app that has no usable API. Ends with a ready Docker container named <site>-mcp, a signed-in test account, and a verification record.
---

# Build a website MCP server

You turn "Make an MCP of website X" into a container the user can plug into any MCP client. The framework already handles Chromium, the Jev model, MCP transport, profiles, login, files and Docker. Your job is the site: which tools it needs, exactly what each one types and checks, and proving they work on the real site.

## Ground rules

- Framework repo: `~/dynamic-web-mcp-framework`. Read `AGENTS.md`, `README.md`, `docs/BUILDING_SERVERS.md`, `src/website_mcp/spec.py`, `servers/wikipedia/site.py` (minimal, no login) and `servers/outlook/site.py` (full, with login) before writing anything.
- Layout is fixed: everything for a site lives in `servers/<site>/`: `site.py` exporting `SITE`, `compose.yaml`, `README.md`, `verification.md`, `tests/`. The framework package never contains site code.
- Naming convention, unless the user asks for something else: the directory is `<site>`, and the Compose service, the container (`--name` on `compose run`, since Compose ignores `container_name` for one-off runs), the image (`<site>-mcp:local`), the volume (`<site>-mcp-data`) and the MCP client entry are all `<site>-mcp`. One container per site; there is never a separate login container.
- Jev chooses among observed controls and caller-supplied strings. It cannot invent text. Every string a tool needs typed must arrive as a tool argument or be computed in Python.
- Never accept credentials, CSS selectors, JavaScript or filesystem paths as tool arguments. Sign-in happens through the login view, by a human.
- Never send, submit, issue, pay, delete permanently or otherwise cause an externally visible mutation on the real site unless the user explicitly asks for that specific test. Read-only first.
- Paid model calls happen only in live tests you deliberately run. The offline suite is free.
- Report honestly. A fixture pass or a listed tool schema is not proof that a real-site workflow works. `servers/<site>/verification.md` separates the two; keep it that way.

## Phase 0: scope with the user (one short exchange)

Ask only what the site cannot tell you:

1. Which account or tenant, and is there a dedicated test account. Insist on a test account for anything with mutations.
2. Which workflows matter most. Offer a guess from your recon (Phase 1) if they say "everything".
3. Which mutations they want covered at all, and which are off limits.

If the user gave the workflows already, skip the question and confirm your tool list after Phase 2 instead.

## Phase 1: recon the real site

Use the framework's own browser, never your desktop browser, so you see what Jev will see. Start the site directory with a tool-less `site.py` and look at the public landing page. The helper scripts enable the `browser_status` debug tool, which returns the page without a model call.

```sh
cd ~/dynamic-web-mcp-framework && uv sync --frozen
mkdir -p servers/<site>/tests
cat > servers/<site>/site.py <<'PY'
from website_mcp.spec import Site
SITE = Site(name="<site>", start_url="https://app.example.com/", domains=("example.com",), tools=())
PY
uv run python scripts/mcp_call.py servers/<site> browser_status --local
```

Record, in `servers/<site>/README.md` as you go:

- The URL the app lands on when logged out, and every host in the sign-in chain. These become `login_domains`.
- Every host the app itself uses (app, CDN frames, auth). These become `domains`. Keep it minimal; subresources are not filtered, only navigations and frames.
- Whether the page rendered text and controls at all. Canvas-only UIs, closed shadow DOM and anti-bot walls are out of scope for this framework; say so to the user immediately.
- Language, date and number formats the UI expects. Tools must format values for the UI, not for the API.
- Pagination style (virtualized list, "load more", pages), upload and download mechanics, and any account or business switcher.

Then have the user sign in (Phase 4 shows how) and repeat the observation on the authenticated app. Take a `browser_status` after opening each screen you intend to automate and keep the control names you see. Guidance strings and goals should use the site's own words.

## Phase 2: design the tool catalog

Think in the site's nouns. For each record type the user cares about, the usual set is:

| Tool shape | Example | Notes |
| --- | --- | --- |
| Search or list with filters | `x_search_invoices(after, before, customer, status, limit)` | Filters must map to something the UI can do. Compute the site's search syntax in Python. Bound `limit`. |
| Read one record | `x_read_invoice(identifier)` | Identity must be unambiguous: number, date plus name, exact subject. Say "stop if ambiguous" in the goal. |
| Download | `x_download_invoice_pdf(identifier)` | Result carries the file name; the caller reads bytes with `<site>_read_file`, so set `attachments=True`. |
| Create as draft | `x_create_invoice_draft(...)` | Every line item field is an argument. Draft and submit are separate tools. |
| Submit or send | `x_issue_invoice(draft_identifier)` | Irreversible. Description says so. `read_only=False`. |
| Manage state | `x_manage_invoice(identifier, action)` | One tool with an enum of actions beats ten tiny tools. |

Rules:

- Prefix every tool with the site name. Name the operation, not the UI element.
- Argument models subclass `Arguments` (extra fields rejected). Use enums, bounded ints, ISO dates and cross-field validators. Make impossible combinations fail validation, not fail in the browser.
- `read_only=True` only for tools whose goal contains no mutation. It is an MCP hint, not enforcement.
- Each `Task.goal` states the exact observable end condition, what to capture, and what not to touch. The framework's model-based completion check reads the goal, the final URL and title, the executed actions, downloads and the page text, so name the end state in words the page will show ("stop once the article heading is visible", "stop when the Sent Items list shows the message"). Put every string to be typed in `values` with a semantic label. Set `max_steps` per tool; searches need fewer than multi-page forms.
- Add a deterministic `verifier` only for irreversible or high-stakes tools where the DOM gives hard evidence: a status badge, a row that now exists, a URL containing the record id, a downloaded file's size. It runs after Jev says done and makes the status `verified` or `unverified` on facts. Read-only tools normally rely on the model check and end `model_complete`.
- A site's tool list is its own functionality only; never expose the browser or file store as such. Two framework capabilities are opt-in on `Site`, named for the site: `attachments=True` adds `<site>_put_file`, `<site>_read_file`, `<site>_list_files` for sites that upload or download files; `custom_task=True` adds `<site>_task` for sites broad enough that users will ask for workflows outside the catalog (Outlook yes, Wikipedia no). `browser_status` is a debug tool that only exists with `WEBSITE_MCP_DEBUG_TOOLS=1`, which the helper scripts set.

Show the user the catalog as a table (tool, arguments, read-only, verifier yes or no) and get a yes before implementing. This is the one checkpoint that saves the most rework.

## Phase 3: implement

1. Fill in `servers/<site>/site.py`: `name`, `start_url`, `domains`, `login_domains`, `guidance`, argument models, task factories, verifiers. Guidance is where site quirks live: "Save autosaves after 2 seconds", "the list is virtualized, capture before scrolling", "opening a record marks it read". Computed strings (search syntax, formatted dates, totals the UI expects typed) live in methods on the argument model, as `MailQuery.search()` does for Outlook.
2. Copy `servers/wikipedia/compose.yaml` to `servers/<site>/compose.yaml`. Change `name`, the service key, `SITE_DIR`, the image, the volume name, and the port: Outlook uses 8765, Wikipedia 8767; take the next free one and set it both in `--port` and in `ports`. The generic `Dockerfile` copies the site directory to `/site`.
3. Add the site to `.mcp.json` at the repo root, copying an existing entry.
4. Tests in `servers/<site>/tests/`, all offline and free: argument validation including computed strings; `login_domains` against real sign-in URLs from your recon; the stdio handshake listing your tools (copy `servers/outlook/tests/test_outlook.py`); a verifier test against a fixture page if a verifier has logic beyond a locator read.
5. Run the gates. All must pass before anything live:

```sh
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
docker compose -f servers/<site>/compose.yaml build && uv run python scripts/check_docker.py servers/<site>
```

The Docker check proves the container starts, lists your tools, reaches the public site, and reports `login.required` correctly.

## Phase 4: get the user signed in

The MCP container hosts its own login view; there is no separate login step. Open a persistent client session, which starts the container and writes the login URL to a status file, then hand the URL to the user and wait. Do not ask for credentials; do not type them.

```sh
export TYPESAFE_API_KEY=...   # or put it in .env next to the compose file
uv run python scripts/mcp_session.py servers/<site> /tmp/<site>-session &
sleep 20; cat /tmp/<site>-session/status.json     # login URL and login.required
```

Tell the user: open the `http://127.0.0.1:<port>/#<token>` URL, sign in including MFA, and say when the app's main screen is showing. The session lives in the `<site>-mcp-data` volume, so every later container starts signed in. Keep this session open for Phase 5; it is the same container.

If a tool ever returns `"login": {"required": true, "url": ...}` later, the session expired. Give the user that URL; the MCP client can stay connected.

## Phase 5: live acceptance

Each call below is one paid Jev run. Append a call to the open session's command file and read the numbered result; every call goes through a real MCP client, exactly as an agent's would:

```sh
echo '{"tool": "<site>_list_things", "arguments": {"limit": 10}}' >> /tmp/<site>-session/commands.jsonl
sleep 60; cat /tmp/<site>-session/results/1.json
```

`scripts/mcp_call.py servers/<site> <tool> '<json>'` does a single call in a fresh container when you do not need the session.

Order of work:

1. Read-only tools on real data. Compare the result's captured pages with what the user can see. Fix guidance, goals and `values` labels when Jev picks the wrong control, and re-run.
2. Downloads. Check the byte count and open the file.
3. Mutations, only on records the user names for the test, only after they say go, one at a time. Draft before submit. After each, take `browser_status` and confirm the visible state matches.
4. Expiry and recovery: confirm a `login_required` result carries a working URL, using a fresh `--account` that has no session.

Common failures and the fix that worked:

- Jev hits the context limit on big pages: the goal asks to capture too much at once. Narrow the goal, page through with captures, rely on scrolling.
- Jev clicks a plausible but wrong control: name the control in the goal exactly as the snapshot names it, or add a rule to `guidance`.
- Result is `unverified` or a low `model_complete` probability although the UI is right: the goal does not name an end state the page shows. Rewrite the goal's stop condition in the page's words. Only reach for a verifier if the page genuinely offers no visible evidence.
- `unstable_page`: the page re-renders between observation and action. Add a wait condition to the goal ("wait until the list has loaded") before the action.
- `action_error` after a mutation: never re-run blindly. Observe the state and reconcile with the user.

## Phase 6: hand over

1. `servers/<site>/verification.md`: the date, the exact commands run, and a table of each tool with the evidence seen (or "not yet verified"). Do not round up.
2. `servers/<site>/README.md`: what the server does, the `claude mcp add` line and JSON client config with its service name and port, one example call per tool family, known limitations.
3. Commit. The container is ready when the gates in Phase 3 pass and the verification table shows real evidence for the tools the user asked for.
4. Tell the user what works, what was not exercised and why, and the exact MCP client config to paste.

## Reference: minimal site module

`servers/wikipedia/site.py` is the reference. It is a single search tool with no login and no verifier; the model check confirms the article opened because the goal names that end state.
