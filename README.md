# Dynamic Web MCP Framework

A framework for turning any website into an MCP server. Each server drives the site in its own headless Chromium: TypeSafe's Jev model picks the next action from the controls it can see, Playwright executes it, and the caller's exact strings are the only text ever typed. Every server runs as one Docker container with its own persistent browser profile, so credentials for one site never share a process, a profile or a volume with another.

The framework itself knows nothing about any website. Sites live under `servers/<site>/`, each one a small Python file plus a Compose file. Agents build new ones with the `website-mcp` skill in `skills/`.

```
src/website_mcp/       the framework: browser, Jev policy, runner, MCP server, login view
servers/wikipedia/     reference site, no login
servers/outlook/       Outlook.com mail server
skills/website-mcp/    the skill an agent uses to build servers/<site>/ for a new site
scripts/               MCP client helpers for smoke checks, one-shot calls and persistent sessions
```

Every server gets these framework tools for free: `browser_status`, `website_task` (any workflow described in words), `files_list`, `files_put`, `files_read`.

Results are evidence, not claims: observed page text and controls, captured pages, downloaded files, and the action history. A tool ends `verified` only when the site's own deterministic verifier confirmed the outcome in the browser. `model_complete` means Jev believes it succeeded and nobody checked.

## Run a server

Requires Docker and a TypeSafe API key. Each site has its own Compose file and container, named `<site>-mcp`. Compose reads `TYPESAFE_API_KEY` from the environment of whatever runs it, or from a gitignored `.env` next to the Compose file, and refuses to start without it.

```sh
export TYPESAFE_API_KEY='your-key'
docker compose -f servers/wikipedia/compose.yaml build
```

The container speaks MCP on stdio, so an MCP client starts it. Add it to Claude Code from this directory:

```sh
claude mcp add wikipedia-mcp -e TYPESAFE_API_KEY="$TYPESAFE_API_KEY" -- \
  docker compose -f "$PWD/servers/wikipedia/compose.yaml" run --rm --no-deps --service-ports --name wikipedia-mcp -T wikipedia-mcp
```

Or with any client's JSON configuration, replacing the path with your checkout:

```json
{
  "mcpServers": {
    "wikipedia-mcp": {
      "command": "docker",
      "args": ["compose", "-f", "/absolute/path/dynamic-web-mcp-framework/servers/wikipedia/compose.yaml", "run", "--rm", "--no-deps", "--service-ports", "--name", "wikipedia-mcp", "-T", "wikipedia-mcp"],
      "env": {"TYPESAFE_API_KEY": "your-key"}
    }
  }
}
```

`.mcp.json` in this repository declares both servers the same way for Claude Code, taking the key from your environment. Replace `wikipedia` with `outlook` for the mail server. `--service-ports` publishes the login view on the host loopback and `--name` names the container, because `compose run` ignores `container_name`.

## Login

Login happens inside the running server; there is no separate step or container. Every tool result carries a `login` block. `{"required": true, "url": "http://127.0.0.1:8765/#<token>"}` means the browser is on a sign-in or logged-out page. Open that URL: it is a local, token-protected page that shows and controls the same headless Chromium, with no model calls. Type the password and MFA there, never into tool arguments, then retry the tool. While the page is a login page, tools return `login_required` without spending model calls. The session persists in the site's volume, so later containers start signed in until the site expires it.

To sign in from a terminal before wiring up a client, keep one client session open with `scripts/mcp_session.py servers/<site> <workdir>`; it prints the login URL and then runs any tool calls appended to `<workdir>/commands.jsonl`.

## Run locally without Docker

```sh
uv sync --frozen
uv run playwright install --with-deps chromium --only-shell
export TYPESAFE_API_KEY='your-key'
uv run website-mcp serve --site servers/wikipedia/site.py
uv run website-mcp tools --site servers/outlook/site.py   # list a site's tools, no browser
```

Profiles live at `.state/<site>/<account>/profile`, files at `.state/<site>/<account>/files`. `--state-dir` changes the root; `--account work` creates another isolated account. Only one process can hold a profile at a time. There is no connection to your everyday browser or its credentials.

## Operational behavior

- Tools on a profile execute serially. A file lock stops two processes from opening the same profile.
- Model outputs never become selectors, JavaScript, shell commands or arbitrary URLs. Targets must be observed DOM nodes. Stale nodes and changed form values are rejected before input; the runner re-observes up to three times when no input was dispatched.
- Models receive page text and caller arguments. Treat the TypeSafe service as a processor of whatever the site shows. Password fields are redacted from snapshots and excluded from typing candidates.
- Website text is treated as untrusted in prompts, which is not a hard boundary against prompt injection. Read-only hints describe intent; a click cannot guarantee zero side effects.
- Timeout, low confidence, ambiguous targets, model context limits or execution errors return an incomplete status. The framework never automatically retries a possibly committed action. Reconcile the visible state before retrying a mutation.
- Common HTML/ARIA controls, open shadow DOM, allowed-origin frames, popups, nested scrolling, uploads and downloads are supported. Canvas-only UIs, closed shadow DOM, native OS dialogs and anti-bot walls need a human.
- Runs are bounded: 60 steps by default, 120 seconds, 25 captured pages, 350 controls and 12,000 text characters per frame. `TASK_TIMEOUT` and `JEV_MIN_CONFIDENCE` are environment overrides. Three guardrails stop runs that burn model calls without progress: `no_progress` after four consecutive unchanged observations (checked before the next model call), `looping` when the same action would execute a third time on an identical page, and `low_confidence` when the mean confidence of the last five decisions falls below 0.4. Files upload up to 10 MiB and read back in chunks of up to 1 MiB.

## Container security

The image installs only Chromium's headless shell, Python and dependencies, and runs as UID 10001 with all capabilities dropped. Chromium's inner sandbox is off inside the container; the container is the boundary. The navigation allowlist per site is not an egress firewall. Only the login view listens, bound to the host loopback; the MCP transport has no port. Do not expose the login port publicly.

## Build a server for a new site

Use the skill: `skills/website-mcp/SKILL.md`. It takes an agent from "Make an MCP of website X" through recon, tool design, implementation, sign-in, live acceptance and handover. The human-readable reference is [docs/BUILDING_SERVERS.md](docs/BUILDING_SERVERS.md); [docs/architecture.md](docs/architecture.md) explains the moving parts.

```sh
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
RUN_LIVE_JEV=1 uv run pytest tests/test_live_jev.py -q -s      # paid, local fixture
uv run python scripts/check_docker.py servers/wikipedia         # container smoke, free
uv run python scripts/mcp_call.py servers/wikipedia wiki_search '{"query": "Ada Lovelace"}'   # paid
```

## Prior art

This project is inspired by [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast), which showed that TypeSafe's Jev model can drive a browser by choosing among indexed, observed controls instead of generating code or selectors. This framework keeps that indexed-choice idea and wraps it in what an MCP server for a specific site needs: typed tools with exact caller-supplied values, an isolated persistent Chromium profile per site, a human login view that keeps credentials away from the model, evidence-based results, and one container per site.

Related work worth knowing:

- [browser-use](https://github.com/browser-use/browser-use), the general-purpose browser agent library from the same team.
- [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp), which exposes raw browser actions (click, type, navigate) as MCP tools for a general model to drive; here the site tools are the MCP surface and the browser driving is internal.
- [browserbase/stagehand](https://github.com/browserbase/stagehand), natural-language browser automation on Playwright.
- [TypeSafe Python SDK](https://docs.typesafe.ai/sdk/python) and the [speculative fan-out pattern](https://docs.typesafe.ai/patterns/fan-out) used to ask Jev the action, target and value questions in one batch.
- [Playwright persistent contexts](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context) and the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk).
