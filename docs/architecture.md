# Architecture

```mermaid
flowchart LR
    C[MCP client] --> S[Typed site tool]
    S --> T[Goal + exact values]
    T --> R[Serialized bounded runner]
    R --> B[Isolated headless Chromium]
    B --> O[DOM controls + page text]
    O --> J[Jev choices]
    J --> G[Candidate and freshness guards]
    G --> B
    B --> E[Page and download evidence]
    E --> V[Verifier]
    V --> C
    H[Human login view] --> B
```

`spec.py` is the extension API and `load.py` loads a site from a file path or module. Site files under `servers/<site>/` supply schemas, goals and verifiers, not model clients or browser lifecycles; the framework package contains no site. `server.py` registers them with the official low-level MCP server and adds file/custom-task tools. `runner.py` serializes calls, enforces bounds, tracks action evidence and captures, and handles completion. It never blindly repeats a failed action.

`browser.py` owns Playwright, a persistent profile lock and file lifecycle. `snapshot.js` returns observed controls and retained nodes, traversing open shadow roots. Each allowed frame has a separate snapshot. The executor rechecks the target description and uses Playwright actionability (including click visibility/occlusion). A page/target change detected before input triggers a fresh observation, at most three consecutive times. History distinguishes executed inputs from rejected preflight attempts. Failures after dispatch stop the task so a possibly committed mutation is not replayed.

`policy.py` sends one batch per step: operation plus speculative target/value/option/key questions. It consumes only the selected branch. Model predictions cannot execute code or supply new text. `done` triggers a fresh observation and either a site-specific deterministic verifier or a second model assessment.

`auth.py` provides the local human login page routes. `serve --transport http` mounts them on one Starlette app together with the MCP endpoint at `/mcp` (streamable HTTP, stateless, bearer token), so any number of agents share one browser and one signed-in session while their calls serialize on the browser lock. `--transport stdio` keeps the login view beside a stdio server for a single spawning client. A random capability token is passed in the URL fragment, then used as a bearer header. No model or website credentials are stored in this web UI. Chromium keeps its normal auth state in its isolated profile; there is no separate login process or container. `Site.login_domains` tells the runner which hosts mean logged out; on those it returns `login_required` and the login URL instead of calling the model.

Persistence is per `<state>/<site>/<account>`. Files are private, downloaded names get random prefixes, caller-provided paths must resolve inside the file store, and MCP retrieval is bounded base64 chunks. Profile and download data are intentionally excluded from version control and Docker build contexts.

The framework is a trusted single-user service bound to the host loopback with one shared bearer token per site. It is not a multi-tenant hosted browser service; exposing it beyond the local machine would need per-client authentication and authorization. Website navigation allowlists and model instructions are useful boundaries but are not a network sandbox or a proof against prompt injection.
