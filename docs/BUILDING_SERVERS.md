# Instructions for agents building another website MCP

Use this framework to expose meaningful, typed website operations. Read `spec.py`, `sites/outlook.py`, and `examples/wiki_site.py` first. Do not fork the browser driver for each website.

1. **Inspect the real website.** Establish its canonical app URL, redirect/login origins, language, pagination, upload/download flow and account/business switching. Use a dedicated test account. Record what you observed and which workflows still need authenticated testing. Never assume a UI or hidden API exists.
2. **Create an importable module exporting `SITE: Site`.** Choose a lowercase unique site name. Set `start_url`, a minimal `domains` tuple for navigation/frames, and site guidance (terminology, ambiguity rules, save/submit behavior, pagination). Domain matching allows subdomains with a dot boundary. Subresource requests are not filtered by this list.
3. **Define typed arguments.** Subclass `Arguments` (extra fields are rejected). Use enums, bounded counts and validation for related fields. Keep dates, amounts, recipients, draft/issue/send intent and unique record identifiers explicit. Do not accept credentials, selectors, JavaScript or arbitrary filesystem paths as tool arguments.
4. **Map arguments to a `Task`.** `goal` describes the exact behavior and observable completion conditions. `values` maps semantic labels to all exact strings that may need typing. Jev cannot generate missing text: include computed search strings, dates formatted for the UI and every line-item field. Known calculations/formatting belong in code. `uploads` maps attachment purposes to existing file-store names. Set a bounded `max_steps`.
5. **Register each `ToolSpec`.** Use the site's prefix, an honest description and its argument model/task factory. Mark `read_only` only when appropriate; it is an MCP hint, not browser enforcement. Separate drafting and irreversible submission where useful. Include “stop if ambiguous” for record mutations. Do not add mandatory user confirmation steps to every operation; the tool call itself expresses the caller's requested action.
6. **Add a deterministic verifier when possible.** `Task.verifier` is an async callable receiving `Browser` and returning bool. Check actual state independently of the model decision: correct record identity, exact values, final status, download content or server-side fixture state. `done` alone is never verified success. Without this hook the framework makes a separate Jev evidence assessment and labels it `model_complete` or `unverified`.
7. **Run with `jev-mcp serve --site your_package.your_site`.** `load_site` imports the module and reads `SITE`; no core registry edits are required. For a local module set `PYTHONPATH` to its directory. Installed third-party site packages work directly. `website_task` and the file tools are added automatically.
8. **Package and isolate.** Add the site module to the image (or install your package), set the container command, and give the service its own volume. For multiple accounts, use different `--account` values, ideally separate containers/volumes. Never mount a real desktop browser profile. MCP and login must use identical site/account/state settings and run sequentially.
9. **Verify the complete contract.** Test actual Chromium controls and resulting state; MCP initialization/discovery/calls through a real stdio client; login persistence and isolation; uploads/downloads; validators; stale targets and incomplete outcomes. Then use paid Jev calls on representative fixtures. Finally test the live authenticated website, including pagination, filters, attachments and mutation evidence in a test account. Do not substitute mock tests for a claim that a real-site workflow works.
10. **Document the result.** Include setup, exact login/MCP commands, example tool arguments, supported workflows, known limitations and current verification evidence. Record failures honestly and keep incomplete requirements open.

## Minimal site

```python
from pydantic import Field
from jev_mcp.spec import Arguments, Site, Task, ToolSpec


class Search(Arguments):
    query: str = Field(min_length=1)


SITE = Site(
    name="catalog",
    start_url="https://catalog.example.com/",
    domains=("catalog.example.com", "login.example.com"),
    guidance="Use the search box. Capture all requested results, paging as needed.",
    tools=(
        ToolSpec(
            name="catalog_search",
            description="Search catalog entries and return observed matching rows.",
            arguments=Search,
            task=lambda args: Task(
                goal=f"Search for {args.query!r}, then capture the matching results.",
                values={"query": args.query},
            ),
            read_only=True,
        ),
    ),
)
```

## Jev's boundary

Jev selects operation, compatible element, supplied field value, observed dropdown option, key or upload. These independent questions are asked together; only answers relevant to the selected operation execute. Choices are validated against the current candidate set. DOM nodes are retained and rechecked before Playwright input. Text written into a website must be a caller-supplied or deterministically computed string. If a use case needs generated prose, have the caller generate it and supply the exact result.

Do not extend this by executing model-produced selectors/code. Extend the observed action vocabulary in `snapshot.js`, `policy.py` and `browser.py`, with real-browser tests for its preconditions and effects. Keep credentials out of goals/values; use the human login portal. Avoid logging raw page content or model SDK debug bodies in production.
