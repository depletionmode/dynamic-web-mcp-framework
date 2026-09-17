import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

HTML = b"""<!doctype html><title>Test mailbox</title>
<label>Search mail <input id="query" aria-label="Search mail"></label>
<button onclick="document.querySelector('#results').textContent='Found: Invoice 42 from Ada on 2026-09-01';">Search</button>
<div id="results"></div>
<label>Recipient <input id="to"></label><label>Subject <input id="subject"></label>
<label>Body <textarea id="body"></textarea></label>
<label>Priority <select id="priority"><option value="normal">Normal</option><option value="high">High</option></select></label>
<input type="file" aria-label="Attachment" onchange="document.querySelector('#uploaded').textContent=this.files[0].name"><div id="uploaded"></div>
<button id="save" onclick="document.querySelector('#saved').textContent='Draft saved: '+document.querySelector('#subject').value;localStorage.setItem('saved',document.querySelector('#subject').value)">Save draft</button><div id="saved"></div>
<a href="/attachment" download="invoice.txt">Download invoice</a>
<a href="https://example.org/forbidden">Outside domain</a>
<iframe src="/frame"></iframe><div id="shadow"></div>
<script>document.querySelector('#shadow').attachShadow({mode:'open'}).innerHTML='<button>Shadow action</button>';</script>
"""


@pytest.fixture(scope="session")
def website():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            if self.path == "/strict":
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Security-Policy", "script-src 'self'")
                content = b"<label>Strict field <input></label><button>Continue</button>"
            elif self.path == "/attachment":
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", 'attachment; filename="invoice.txt"')
                content = b"Invoice 42: total 123.45 ILS"
            elif self.path == "/long":
                self.send_header("Content-Type", "text/html")
                body = b"".join(
                    b"<p>Paragraph %d of the article body.</p>" % i for i in range(1, 201)
                )
                content = b"<title>Long article</title><h1>Top of the article</h1>" + body
            elif self.path == "/frame":
                self.send_header("Content-Type", "text/html")
                content = b"<button>Frame action</button>"
            else:
                self.send_header("Content-Type", "text/html")
                content = HTML
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()
    server.server_close()
