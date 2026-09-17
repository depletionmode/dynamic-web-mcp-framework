# Original scope and completion audit

Source: the user-provided pasted text attachment read at the start of the task. The scope is a reusable Jev-driven browser MCP framework plus an Outlook.com server in its own container, with agent instructions for future servers. Morning.co.il was in the original request; on 2026-09-17 David removed it from this repository so that it can later be built from the SKILL by a fresh agent as the framework's first real test.

| Requested outcome | Current artifact/evidence | Audit status |
| --- | --- | --- |
| Easily expose MCP tools controlling arbitrary websites | `Site`, `ToolSpec`, `Task`, typed schemas, module loading, runnable Wikipedia extension and generic `website_task`; real MCP tests | Framework implemented/tested; arbitrary UI coverage has documented bounds |
| Headless Chromium execution | Playwright persistent contexts, CLI forbids headed serving; real Chromium tests and Docker smoke | Proven for exercised controls |
| Driven by Jev, similar to jev-ultrafast | Batched action/target/value Choice heads; live paid model tests with independent outcome verification | Proven on representative fixture workflows |
| Login/auth support with contained credentials | Human login portal, isolated persistent profiles, process locks and per-account directories/volumes | Mechanism tested; real account sign-in still pending |
| Lightweight separate Docker container for each MCP | Shared slim image/headless shell, two Compose services, separate volumes, non-root runtime | Built and exercised through MCP |
| Instructions for future agents | `docs/BUILDING_SERVERS.md`, `skills/website-mcp/SKILL.md`, `servers/wikipedia` | Written and reviewed against framework API |
| Outlook browsing/search/mailboxes/timeframes/filters/attachments | Outlook typed tools and exact search construction | Implemented; authenticated acceptance pending |
| Outlook attachment retrieval | Browser download store + MCP binary retrieval + download tool | Primitive verified; actual Outlook attachment pending |
| Outlook email/tag/folder management | Manage-mail, categories, folders tools | Implemented; authenticated acceptance pending |
| Outlook send/draft emails | Compose/update/send-draft/reply tools with supplied content and files | Draft primitive verified with Jev; actual Outlook acceptance pending |

See `verification.md` for commands and the remaining workflow-level evidence. The goal remains open until the authenticated acceptance gap is resolved or the user changes the acceptance scope.
