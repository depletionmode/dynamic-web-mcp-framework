# Dynamic Web MCP Framework

Turn any website into an MCP server. Each server drives the site in its own headless Chromium: TypeSafe's Jev model picks the next action from the controls it can see, Playwright executes it, and the caller's exact strings are the only text ever typed. A server exposes only that site's functionality as tools and runs as one long-running Docker container named `<site>-mcp`, serving MCP over HTTP on the host loopback so any number of agents share one signed-in session; their calls queue on the single browser. Each container keeps its own browser profile, so credentials for one site never share a process or a volume with another. Sign-in happens in a local page served by the same container, never through the model.

The framework knows nothing about any website. Sites live under `servers/<site>/` as a small Python file plus a Compose file. `servers/wikipedia` is the reference (one tool, no login); `servers/outlook` is a full mail server.

## Use it

Ask an agent that has the `website-mcp` skill (`skills/website-mcp/SKILL.md`; symlink it into your agent's skills directory):

> Make an MCP of website X

The skill takes it from recon of the real site, through tool design, implementation, your sign-in and live acceptance, to a running container and the client config to paste. To run a server that already exists:

```sh
export TYPESAFE_API_KEY='your-key'
bin/site-mcp up wikipedia
```

`up` builds the image if needed, starts the container detached, saves the key to `servers/wikipedia/.env`, and prints the exact `grok mcp add`, `claude mcp add` and `codex mcp add` lines for `http://127.0.0.1:8767/mcp`. The endpoint is open on the loopback by default; `up <site> --token` requires a bearer token instead. `bin/site-mcp connect|status|down <site>` do what they say. `.mcp.json` declares both servers for Claude Code. When a tool result says `login.required`, open the URL it carries, sign in, and call again; the session persists in the site's volume across restarts.

Results are evidence, not claims: observed text, captured pages, downloaded files and the action history, with a status of `model_complete`, `verified`, or a named reason it stopped. Runs are bounded by steps, a 120 second timeout, and guardrails against no progress, loops and persistently low confidence. Each server's `README.md` and `verification.md` say what it does and what has actually been exercised on the real site.

## Develop

```sh
uv sync --frozen && uv run playwright install --with-deps chromium --only-shell
uv run ruff check . && uv run ruff format --check . && uv run pytest -q     # free
uv run python scripts/check_docker.py servers/wikipedia                     # starts the container, smoke over HTTP, free
uv run python scripts/mcp_call.py servers/wikipedia wiki_search '{"query": "Ada Lovelace"}'   # one paid Jev run
```

[docs/architecture.md](docs/architecture.md) explains the moving parts; [docs/BUILDING_SERVERS.md](docs/BUILDING_SERVERS.md) is the human-readable version of the skill. The container runs as a non-root user with capabilities dropped and listens only on the host loopback. The login view always needs the per-run token in its URL; the MCP endpoint is open unless started with `--token`. `serve --transport stdio` still exists for a single spawning client. The model sees page text, so treat the TypeSafe service as a processor of whatever the site shows.

## Inspiration and credits

Inspired by [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast), which showed that Jev can drive a browser by choosing among indexed, observed controls instead of generating code or selectors. This framework keeps that idea and adds what a per-site MCP server needs: typed tools with exact caller-supplied values, isolated persistent profiles, a human login view, evidence-based results and one container per site.

Related work: [browser-use](https://github.com/browser-use/browser-use); [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp), which exposes raw browser actions as MCP tools where this framework exposes site functionality; [browserbase/stagehand](https://github.com/browserbase/stagehand). Built on the [TypeSafe Python SDK](https://docs.typesafe.ai/sdk/python) and its [fan-out pattern](https://docs.typesafe.ai/patterns/fan-out), [Playwright](https://playwright.dev/python/), and the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk).
