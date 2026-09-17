---
name: website-mcp
description: Build an MCP server that drives any website through headless Chromium and the Jev model, on the jev-driven-browser-mcp framework. Use when the user says "Make an MCP of website X", "add a site to the browser MCP", or wants an agent to operate a web app that has no usable API. Ends with a ready Docker container, a signed-in test account, and a verification record.
---

# Build a website MCP server

You turn "Make an MCP of website X" into a container the user can plug into any MCP client. The framework already handles Chromium, the Jev model, MCP transport, profiles, login, files, and Docker. Your job is the site: which tools it needs, exactly what each one types and checks, and proving they work on the real site.

## Ground rules

- Framework repo: `~/code/jev-driven-browser-mcp`. Read `AGENTS.md`, `README.md`, `docs/BUILDING_SERVERS.md`, `src/jev_mcp/spec.py` and `src/jev_mcp/sites/outlook.py` before writing anything. Outlook is the reference site; copy its shape.
- Jev chooses among observed controls and caller-supplied strings. It cannot invent text. Every string a tool needs typed must arrive as a tool argument or be computed in Python.
- Never accept credentials, CSS selectors, JavaScript or filesystem paths as tool arguments. Sign-in happens through the login view, by a human.
- Never send, submit, issue, pay, delete permanently or otherwise cause an externally visible mutation on the real site unless the user explicitly asks for that specific test. Read-only first.
- Paid model calls happen only in live tests you deliberately run. The offline suite is free.
- Report honestly. A fixture pass or a listed tool schema is not proof that a real-site workflow works. `docs/verification.md` separates the two; keep it that way.

## Phase 0: scope with the user (one short exchange)

Ask only what the site cannot tell you:

1. Which account or tenant, and is there a dedicated test account. Insist on a test account for anything with mutations.
2. Which workflows matter most. Offer a guess from your recon (Phase 1) if they say "everything".
3. Which mutations they want covered at all, and which are off limits.

If the user gave the workflows already, skip the question and confirm your tool list after Phase 2 instead.

## Phase 1: recon the real site

Use the framework's own browser, never your desktop browser, so you see what Jev will see.

```sh
cd ~/code/jev-driven-browser-mcp && uv sync --frozen
cat > /tmp/recon_site.py <<'EOF'
from jev_mcp.spec import Site
SITE = Site(name="recon", start_url="https://app.example.com/", domains=("example.com",), tools=())
EOF
PYTHONPATH=/tmp uv run python scripts/mcp_call.py recon_site browser_status --local
```

Record, in `docs/sites/<site>.md` as you go:

- The URL the app lands on when logged out, and every host in the sign-in chain. These become `login_domains`.
- Every host the app itself uses (app, CDN frames, auth). These become `domains`. Keep it minimal; subresources are not filtered, only navigations and frames.
- Whether the page rendered text and controls at all. Canvas-only UIs, closed shadow DOM, and anti-bot walls are out of scope for this framework; say so to the user immediately.
- Language, date and number formats the UI expects. Tools must format values for the UI, not for the API.
- Pagination style (virtualized list, "load more", pages), upload and download mechanics, and any account or business switcher.

Then have the user sign in (Phase 4 shows how) and repeat the observation on the authenticated app. Take a `browser_status` after opening each screen you intend to automate and keep the control names you see. Guidance strings and goals should use the site's own words.

## Phase 2: design the tool catalog

Think in the site's nouns. For each record type the user cares about, the usual set is:

| Tool shape | Example | Notes |
| --- | --- | --- |
| Search or list with filters | `x_search_invoices(after, before, customer, status, limit)` | Filters must map to something the UI can do. Compute the site's search syntax in Python. Bound `limit`. |
| Read one record | `x_read_invoice(identifier)` | Identity must be unambiguous: number, date plus name, exact subject. Say "stop if ambiguous" in the goal. |
| Download | `x_download_invoice_pdf(identifier)` | Result carries the file name; the caller reads bytes with `files_read`. |
| Create as draft | `x_create_invoice_draft(...)` | Every line item field is an argument. Draft and submit are separate tools. |
| Submit or send | `x_issue_invoice(draft_identifier)` | Irreversible. Description says so. `read_only=False`. |
| Manage state | `x_manage_invoice(identifier, action)` | One tool with an enum of actions beats ten tiny tools. |

Rules:

- Prefix every tool with the site name. Name the operation, not the UI element.
- Argument models subclass `Arguments` (extra fields rejected). Use enums, bounded ints, ISO dates, and cross-field validators. Make impossible combinations fail validation, not fail in the browser.
- `read_only=True` only for tools whose goal contains no mutation. It is an MCP hint, not enforcement.
- Each `Task.goal` states the exact observable end condition, what to capture, and what not to touch. Put every string to be typed in `values` with a semantic label. Set `max_steps` per tool; searches need fewer than multi-page forms.
- Add a deterministic `verifier` wherever the DOM gives evidence: a status badge, a row that now exists, a URL containing the record id, a downloaded file's size. Without one the result is only `model_complete`.
- Keep `website_task` for everything outside the catalog. Do not add a typed tool for one-off workflows.

Show the user the catalog as a table (tool, arguments, read-only, verifier yes or no) and get a yes before implementing. This is the one checkpoint that saves the most rework.

## Phase 3: implement

1. Create `src/jev_mcp/sites/<site>.py` exporting `SITE`. `load_site` finds it by short name; no registry edit.
2. Set `name`, `start_url`, `domains`, `login_domains`, `guidance` from your recon notes. Guidance is where site quirks live: "Save autosaves after 2 seconds", "the list is virtualized, capture before scrolling", "opening a record marks it read".
3. Implement argument models, task factories and verifiers. Computed strings (search syntax, formatted dates, totals the UI expects typed) live in methods on the argument model, as `MailQuery.search()` does for Outlook.
4. Add a Compose service by copying the `outlook-mcp` block. Naming convention, unless the user asks for something else: the service, the container (`--name` on `compose run`, since Compose ignores `container_name` for one-off runs) and the MCP server entry in the client config are all `<site>-mcp`. Set `--site <site>`, a new host port (8765 is Outlook; take the next free one), the same port in `--port`, and a new named volume `<site>-data`. One container per site, always; there is no separate login container.
5. Tests, all offline and free:
   - argument validation, including the computed strings;
   - the stdio handshake test in `tests/test_contracts.py`: add your site and one expected tool name;
   - a verifier test against a fixture page if the verifier has any logic beyond a locator read.
6. Run the gates. All must pass before anything live:

```sh
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
docker compose build && uv run python scripts/check_docker.py <site>
```

The Docker check proves the container starts, lists your tools, reaches the public site, and reports `login.required`.

## Phase 4: get the user signed in

The MCP container hosts its own login view; there is no separate login step. Open a persistent client session, which starts the container and prints the login URL, then hand the URL to the user and wait. Do not ask for credentials; do not type them.

```sh
export TYPESAFE_API_KEY=...   # or put it in .env next to compose.yaml
uv run python scripts/mcp_session.py <site> /tmp/<site>-session &
cat /tmp/<site>-session/status.json     # has the login URL and login.required
```

Tell the user: open the `http://127.0.0.1:<port>/#<token>` URL, sign in including MFA, and say when the app's main screen is showing. The session lives in the site's volume, so every later container starts signed in. Keep this session open for Phase 5; it is the same container.

If a tool ever returns `"login": {"required": true, "url": ...}` the session expired. Give the user that URL; the MCP client can stay connected.

## Phase 5: live acceptance

Each call below is one paid Jev run. Append a call to the open session's command file and read the numbered result; every call goes through a real MCP client, exactly as an agent's would:

```sh
echo '{"tool": "<site>_list_things", "arguments": {"limit": 10}}' >> /tmp/<site>-session/commands.jsonl
sleep 60; cat /tmp/<site>-session/results/1.json
```

`scripts/mcp_call.py <site> <tool> '<json>'` does a single call in a fresh container when you do not need the session.

Order of work:

1. Read-only tools on real data. Compare the result's captured pages with what the user can see. Fix guidance, goals and `values` labels when Jev picks the wrong control, and re-run.
2. Downloads. Check the byte count and open the file.
3. Mutations, only on records the user names for the test, only after they say go, one at a time. Draft before submit. After each, take `browser_status` and confirm the visible state matches.
4. Expiry and recovery: confirm a `login_required` result carries a working URL.

Common failures and the fix that worked on Outlook:

- Jev hits the context limit on big pages: the goal asks to capture too much at once. Narrow the goal, raise `limit` handling into pagination steps, rely on scrolling.
- Jev clicks a plausible but wrong control: name the control in the goal exactly as the snapshot names it, or add a rule to `guidance`.
- Result is `unverified` although the UI is right: the verifier is checking the wrong evidence. Verify from the page after `done`, not from the model's claim.
- `unstable_page`: the page re-renders between observation and action. Add a wait condition to the goal ("wait until the list has loaded") before the action.
- `action_error` after a mutation: never re-run blindly. Observe the state and reconcile with the user.

## Phase 6: hand over

1. `docs/verification.md`: add a section for the site with the date, the exact commands run, and a table of each tool with the evidence seen (or "not yet verified"). Do not round up.
2. `README.md`: add the site to the list, the client config block with its service name and port, and one example call per tool family.
3. Commit. The container is ready when `docker compose build && uv run python scripts/check_docker.py <site>` passes and the verification table shows real evidence for the tools the user asked for.
4. Tell the user what works, what was not exercised and why, and the exact MCP client config to paste.

## Reference: minimal site module

```python
from pydantic import Field
from jev_mcp.spec import Arguments, Site, Task, ToolSpec


class Search(Arguments):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=20, ge=1, le=100)


async def verify_results(browser):
    return "results" in browser.page.url


SITE = Site(
    name="catalog",
    start_url="https://app.catalog.example/",
    domains=("catalog.example",),
    login_domains=("login.catalog.example",),
    guidance="Use the top search box. Results are paged; capture each page before clicking Next.",
    tools=(
        ToolSpec(
            "catalog_search",
            "Search catalog entries and return the observed matching rows.",
            Search,
            lambda a: Task(
                f"Search for {a.query!r} and capture up to {a.limit} matching rows, paging as needed. Do not open entries.",
                {"query": a.query},
                max_steps=25,
                verifier=verify_results,
            ),
            read_only=True,
        ),
    ),
)
```
