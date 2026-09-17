# Instructions for agents building another website MCP

Use this framework to expose meaningful, typed website operations. Read `src/website_mcp/spec.py`, `servers/wikipedia/site.py` and `servers/outlook/site.py` first. The skill in `skills/website-mcp/SKILL.md` is the step-by-step version of this page. Do not fork the browser driver for each website.

1. **Inspect the real website.** Establish its canonical app URL, redirect/login origins, language, pagination, upload/download flow and account/business switching. Use a dedicated test account. Record what you observed and which workflows still need authenticated testing. Never assume a UI or hidden API exists.
2. **Create `servers/<site>/site.py` exporting `SITE: Site`.** The directory name is the site name, lowercase and unique; the container and service are `<site>-mcp`. Set `start_url`, a minimal `domains` tuple for navigation/frames, and site guidance (terminology, ambiguity rules, save/submit behavior, pagination). Domain matching allows subdomains with a dot boundary. Subresource requests are not filtered by this list.
3. **Define typed arguments.** Subclass `Arguments` (extra fields are rejected). Use enums, bounded counts and validation for related fields. Keep dates, amounts, recipients, draft/issue/send intent and unique record identifiers explicit. Do not accept credentials, selectors, JavaScript or arbitrary filesystem paths as tool arguments.
4. **Map arguments to a `Task`.** `goal` describes the exact behavior and observable completion conditions. `values` maps semantic labels to all exact strings that may need typing. Jev cannot generate missing text: include computed search strings, dates formatted for the UI and every line-item field. Known calculations/formatting belong in code. `uploads` maps attachment purposes to existing file-store names. Set a bounded `max_steps`.
5. **Register each `ToolSpec`.** Use the site's prefix, an honest description and its argument model/task factory. Mark `read_only` only when appropriate; it is an MCP hint, not browser enforcement. Separate drafting and irreversible submission where useful. Include “stop if ambiguous” for record mutations. Do not add mandatory user confirmation steps to every operation; the tool call itself expresses the caller's requested action.
6. **Add a deterministic verifier when possible.** `Task.verifier` is an async callable receiving `Browser` and returning bool. Check actual state independently of the model decision: correct record identity, exact values, final status, download content or server-side fixture state. `done` alone is never verified success. Without this hook the framework makes a separate Jev evidence assessment and labels it `model_complete` or `unverified`.
7. **Run with `website-mcp serve --site servers/<site>/site.py`.** `--site` takes a file path or an importable module; either must export `SITE`. No registry edits. A site's tool list is its own functionality only: set `attachments=True` to get `<site>_put_file`, `<site>_read_file` and `<site>_list_files`, and `custom_task=True` to get `<site>_task`. The `browser_status` debug tool appears only with `WEBSITE_MCP_DEBUG_TOOLS=1`.
8. **Package and isolate.** Copy `servers/wikipedia/compose.yaml` to `servers/<site>/compose.yaml`: set `name`, service and `container_name` `<site>-mcp`, `SITE_DIR: servers/<site>`, a free host port, and volume name `<site>-mcp-data`. The generic `Dockerfile` copies the site directory to `/site`. `bin/site-mcp up <site>` starts it as a long-running HTTP MCP server and prints the client commands. For multiple accounts, use different `--account` values, ideally separate containers/volumes. Never mount a real desktop browser profile. Set `login_domains` so the runner reports `login_required` with the in-process login view URL instead of spending model calls on a sign-in page.
9. **Verify the complete contract.** Test actual Chromium controls and resulting state; MCP initialization/discovery/calls through a real stdio client; login persistence and isolation; uploads/downloads; validators; stale targets and incomplete outcomes. Then use paid Jev calls on representative fixtures. Finally test the live authenticated website, including pagination, filters, attachments and mutation evidence in a test account. Do not substitute mock tests for a claim that a real-site workflow works.
10. **Document the result.** Include setup, exact login/MCP commands, example tool arguments, supported workflows, known limitations and current verification evidence. Record failures honestly and keep incomplete requirements open.

## What the model observes

Goals fail most often because they were written against the page a human sees rather than the one the runner hands the model. These hold for every site:

- An observation is a **viewport clip**. `snapshot.js` keeps only elements and text whose rect intersects the 1440x1000 viewport; everything else is absent, not truncated. Listing anything taller than one screen is a walk down the page.
- `scroll_down` is a fixed **700px wheel**, less than the viewport, so captures and scrolls must strictly alternate: two scrolls in a row skip a band of content.
- `capture` **changes nothing**. Two in a row record the same screen, and four unchanged observations trip the no-progress guard. Put "never capture twice in a row" in `guidance`, which is seen on every decision, rather than in a single goal.
- A call **starts where the last one finished**. `start_url` is loaded only when the page is first opened, so on a long-running container each tool inherits the previous tool's page and scroll position. Anchor goals to a visible marker ("if the masthead is not on screen, scroll up"), because the model cannot read a scroll offset. The `home` operation returns to the site's own `start_url`; it is offered on every site and is the only way back from a page reached through an outbound link, since such a page has no link to the site. Widening `domains` to follow outbound links without telling the model in `guidance` when to use `home` leaves the browser stranded off-site for every later call.
- The completion check sees the final page text, the executed actions and each capture's URL and leading text, never a structured result. Phrase the end state as something the page displays; a goal that reads as an extraction request scores badly however well the run went.

Measure before writing goals: load the page at 1440x1000, run the repository's own `snapshot.js` after each 700px wheel, and print `scrollY` with the resulting text. That is free and shows exactly how many screens the page is and what its end looks like. Where a page has columns, also read `getBoundingClientRect()` with `scrollY`, since a short column beside a long one is not where DOM order suggests. Confirm a control's mechanism the same way before designing a tool around it: a "Download" button that calls `window.print()` can never produce a file headless, and that tool has to be dropped and reported rather than shipped hopeful.

## Minimal site

```python
from pydantic import Field
from website_mcp.spec import Arguments, Site, Task, ToolSpec


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
