# Outlook.com MCP server

Drives Outlook.com webmail through the framework: folders, filtered and time-bounded search, reading messages, attachment download and upload, read state, flags, archive, trash and restore, moves, categories, folder management, drafts, sending, replies and forwarding. Twelve typed tools, plus `outlook_task` for any other Outlook workflow described in words and `outlook_put_file`, `outlook_read_file`, `outlook_list_files` for attachments. No Graph API is used; everything happens in the signed-in web UI.

```sh
export TYPESAFE_API_KEY='your-key'
docker compose -f servers/outlook/compose.yaml build
claude mcp add outlook-mcp -e TYPESAFE_API_KEY="$TYPESAFE_API_KEY" -- \
  docker compose -f "$PWD/servers/outlook/compose.yaml" run --rm --no-deps --service-ports --name outlook-mcp -T outlook-mcp
```

The first tool call returns `login.required: true` with a URL on `127.0.0.1:8765`. Sign in there, including MFA, then retry. The session persists in the `outlook-mcp-data` volume. See [verification.md](verification.md) for what has actually been exercised against a real mailbox.

## Tool examples

Search matching messages, dates inclusive:

```json
{"folder":"Inbox","after":"2026-09-01","before":"2026-09-17","sender":"billing@example.com","has_attachments":true,"limit":100}
```

Call `outlook_search_mail` with this object. Identify a message for `outlook_read_mail`, `outlook_download_attachments` or `outlook_manage_mail` by observed sender, exact subject, timestamp and folder; subjects alone may be ambiguous. Search uses Outlook search syntax and the result reflects the filters the UI actually applied. Results are DOM evidence, not a normalized mailbox export, and pagination is bounded by `limit`.

To attach files, call `outlook_put_file` with `{"filename": "invoice.pdf", "data_base64": "..."}` and pass the returned `name` in `attachments`. Downloads return a `name`; read the bytes with `outlook_read_file`, following `next_offset` until `eof`.

Anything outside the typed tools goes through `outlook_task`:

```json
{"goal": "Open Settings, then the Rules page, and capture the list of inbox rules. Do not change anything.", "values": {}, "max_steps": 20}
```

Delete moves to Deleted Items and never purges. Opening a message can mark it read. Sending is a separate, explicit tool; drafts are never sent implicitly.
