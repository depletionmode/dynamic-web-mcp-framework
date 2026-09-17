# Outlook.com verification record

Framework-level evidence (real Chromium, MCP transport, profiles, login view, Docker) lives in `docs/verification.md`. This file tracks the Outlook server against a real, signed-in mailbox.

Status on 2026-09-17: no authenticated mailbox has been exercised yet. The container starts, lists 17 tools, reaches the public Outlook landing page and reports `login.required: true` (`scripts/check_docker.py servers/outlook`). Argument validation and search syntax are covered by `tests/test_outlook.py`.

| Requirement | Tool | Evidence so far | Remaining |
| --- | --- | --- | --- |
| Folder listing | `outlook_list_folders` | none | Nested folder names and counts match the authenticated UI |
| Timeframes, filters, search | `outlook_search_mail` | search string construction (offline test) | Date boundaries, sender/read/category/attachment filters and paging match known messages |
| Read messages | `outlook_read_mail` | none | Correct unique message, full body, headers, attachment list |
| Attachments | `outlook_download_attachments` + `files_read` | download primitive (fixture) | Real attachment bytes and filename |
| Manage mail, categories, folders | `outlook_manage_mail`, `outlook_manage_categories`, `outlook_manage_folders` | none | Each state transition checked in a test mailbox |
| Draft, edit, send, reply, forward | compose tools + `outlook_reply` | draft primitive (fixture, live Jev) | Recipients, body, attachments and Drafts/Sent Items evidence in an authorized test |
| Login persistence | login view + `outlook-mcp-data` volume | login view exercised on fixtures | Sign-in with MFA, then authenticated calls after a container restart |

Rules for filling this in: read-only tools first; mutations only on messages the user names; no send unless the user asks for that specific test. Record failures as failures.
