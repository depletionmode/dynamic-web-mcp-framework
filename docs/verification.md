# Verification record

Date: 2026-09-17. This separates implemented interfaces from demonstrated behavior. No authenticated Outlook or Morning account has yet been supplied. Live mailbox/accounting workflows remain an acceptance gate; the repository is not claiming those integrations are production-verified.

## Demonstrated

- Real headless Chromium: input, native select, click, iframe controls, open shadow DOM, file upload, download bytes, navigation restrictions, stale-target rejection and rejection when a different form field changes before submission.
- Profile lifecycle: authentication-like local storage persists across browser restart; different account profiles cannot read it; a concurrent process cannot open the same profile.
- Local human login view: unauthorized screen/actions rejected; authorized screenshot, coordinate click and text input operate actual headless Chromium. No Jev calls are involved in this path.
- Strict Content Security Policy: Chromium snapshots and field entry work without enabling `unsafe-eval` or bypassing CSP. This regression was discovered on the public Outlook page.
- MCP: official client initializes each server over stdio, discovers typed tools, uploads and reads binary attachment chunks, and receives an error on file traversal. Outlook advertises 12 site tools plus 5 framework tools; Morning advertises 13 plus 5.
- Real Jev API + actual Chromium, local fixture: exact recipient, subject and body entered; draft saved; independent DOM verifier checks every field and the saved status. Also selects High priority, uploads exact receipt bytes and downloads an invoice exactly once; verifier checks resulting UI and downloaded contents.
- Public third-site extension: Jev searched Wikipedia for Ada Lovelace and opened the article; independent checks confirmed the URL, heading and article content. This exposed and led to fixes for oversized DOM prompts and stale preflight recovery.
- False completion: a `done` decision with insufficient evidence remains `unverified`; execution errors are not replayed.
- Packaging: source distribution and wheel build; wheel contains JavaScript, login HTML and both site modules. Docker builds a shared headless-shell image; Compose gives the two services separate volumes and containers.
- Docker MCP smoke: both servers initialize and list tools from real containers; headless Chromium reaches a readable public Outlook landing page and Morning's login form.

Commands:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
RUN_LIVE_JEV=1 uv run pytest -q -s
uv build
docker compose config --quiet
docker build -t jev-browser-mcp:local .
uv run python scripts/check_docker.py
# Paid, read-only public-site extension check:
uv run python scripts/check_public_site.py
```

The offline suite has 15 tests plus two explicitly skipped live-model tests. The full opt-in suite has 17 tests. A Starlette/AnyIO deprecation warning is currently non-failing.

## Remaining live acceptance

Use dedicated test accounts. Login can be completed in the provided local headless view, retaining state in the relevant Docker volume. Read-only tests can then inspect actual data; sends/issuance and other externally visible mutations require explicit test instructions and appropriate test records.

| Requirement | Implemented interface | Remaining evidence |
| --- | --- | --- |
| Outlook mailbox/folder listing | `outlook_list_folders` | Nested folder names/counts match authenticated UI |
| Timeframes, filters and search | `outlook_search_mail` | Date boundaries, sender/read/category/attachment filters and multipage results match known messages |
| Read messages | `outlook_read_mail` | Correct unique message, full body/headers/attachment list |
| Grab attachments | `outlook_download_attachments`, `files_read` | Actual mail attachment bytes and filename |
| Manage emails/tags/folders | `outlook_manage_mail`, `outlook_manage_categories`, `outlook_manage_folders` | Each requested state transition checked in a test mailbox |
| Draft/edit/send/reply/forward | Four compose/draft tools plus `outlook_reply` | Exact recipients/body/attachments and Drafts/Sent Items evidence in an authorized test scenario |
| Morning documents | List/read/download/create-draft/issue/send tools | Actual app navigation, filters, draft field mapping, PDF bytes and authorized issuance/email evidence |
| Morning customers | List/read/create/update tools | Correct records and field mappings, duplicate handling |
| Morning expenses/reports | List/record-expense/report tools | Receipt upload, exact amounts/categories, date filters and exports |
| Real login persistence | `login`, isolated volume | User sign-in/MFA followed by successful authenticated MCP after restarting |

Do not interpret a fixture pass, advertised tool schema, or a public login page as proof of authenticated site behavior. Use failures from live acceptance to refine site guidance, exact field candidates and deterministic verifiers. No unrequested real email was sent and no real accounting document was issued during development.
