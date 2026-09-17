# depletionmode.com MCP server

Drives [depletionmode.com](https://depletionmode.com/) — "2 of 1; half a nybble of another", David Kaplan's zine on security, computing and engineering — through the framework. Four typed tools, all read-only: list the front-page index, list the archived back catalogue, find entries by title, and read one entry. The site is public, so there is no sign-in and no login view to visit.

```sh
export TYPESAFE_API_KEY='your-key'
bin/site-mcp up depletionmode   # prints the claude / codex / grok add lines for http://127.0.0.1:8768/mcp
```

## What the site looks like

The front page is the whole index: a two-column table of contents whose long left column holds every `talks · articles · publications` entry, and whose shorter right column holds `poc`, then `tools`, then `patents`. An `about me` block and the footer span the full width at the bottom. Entries are grouped by year, newest first, and numbered `0x01` upwards — that number is decoration, so tools identify an entry by its title. `depletionmode.com/archive/` holds the older back catalogue, roughly 2010 to 2015, reached from `Archive: the old stuff` at the foot of the left column.

An entry marked with a trailing arrow links off the site. Those are followed: `domains` covers `originhq.com`, `cloudblogs.microsoft.com`, `github.com`, `patents.google.com`, `pagedout.institute` and `exchange.xforce.ibmcloud.com`.

## Tool examples

```json
{"tool": "depletionmode_list_index",   "arguments": {"section": "patents"}}
{"tool": "depletionmode_list_index",   "arguments": {"section": "articles", "year_from": 2019, "limit": 30}}
{"tool": "depletionmode_list_archive", "arguments": {"year_from": 2013}}
{"tool": "depletionmode_find",         "arguments": {"query": "Themida", "include_archive": false}}
{"tool": "depletionmode_read_post",    "arguments": {"title": "Unpacking Themida #1"}}
```

`section` is one of `all`, `articles`, `poc`, `tools`, `patents`, `about`. `year_from`/`year_to` are inclusive and validated as a range. `depletionmode_read_post` takes the entry's exact title as printed on the index or archive — not a slug, URL or `0x` number — and stops rather than guessing if two entries share it.

Results are captured screens, not a normalised export: a listing walks the page and returns what each screen showed. Because both listings run newest first, giving `year_from` lets a call stop as soon as older entries appear instead of walking to the footer.

## Known limitations

- **No PDF download.** Each post page has a `Download PDF` button, but it calls `window.print()` against a print stylesheet rather than fetching a file, so headless Chromium can never complete it. There is no downloadable artifact on the site, so the server has no file-store tools. To get a PDF, open the post URL in a real browser and print it there.
- **Off-site entries give shallower evidence.** Destinations have their own layouts and modal overlays; the article body is captured, but less cleanly than on depletionmode.com. Entries whose destination is a PDF or PowerPoint (`poc||gtfo`, Paged Out!, conference slides) are reported as a URL and not read, because the browser's document viewer exposes no text.
- **No search.** The site has no search box, so `depletionmode_find` reads the index (and optionally the archive) and reports the entries whose titles match. It matches titles, not body text.
- **Listings normally finish `unverified`.** See [verification.md](verification.md); the coverage is complete and reproducible, but the framework's completion check cannot confirm a multi-screen walk of a single URL.

See [verification.md](verification.md) for what has actually been exercised against the live site.
