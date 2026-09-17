# Working in this repository

Read README.md and docs/BUILDING_SERVERS.md before extending site support. Keep the reusable framework independent from site-specific schemas and goals. Site workflow verification must distinguish actual live website evidence from fixture/model tests. Never report `done` as deterministic success without an independent verifier.

Use `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest -q` for changes. Live Jev tests are opt-in paid API calls (`RUN_LIVE_JEV=1`). Do not run sends, accounting issuance, or other live mutations unless the user explicitly requests those actions. Keep account state, keys and page traces out of git.
