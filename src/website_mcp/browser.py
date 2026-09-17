from __future__ import annotations

import asyncio
import fcntl
import hashlib
import os
import uuid
from pathlib import Path

from playwright.async_api import async_playwright

from .spec import Site, contained_file

SNAPSHOT = Path(__file__).with_name("snapshot.js").read_text()


class StaleObservation(RuntimeError):
    """The DOM changed before any browser input was dispatched."""


class Browser:
    """One persistent Chromium process/profile per site and account; never shares a user profile."""

    def __init__(self, site: Site, state_dir: Path, account: str = "default", headless=True):
        if not account or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for c in account
        ):
            raise ValueError("Account must contain only letters, digits, '_' or '-'")
        if not site.name or any(
            c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in site.name
        ):
            raise ValueError("Invalid site name")
        self.site = site
        self.root = state_dir.resolve() / site.name / account
        self.profile = self.root / "profile"
        self.files = self.root / "files"
        self.headless = headless
        self.lock = asyncio.Lock()
        self.context = None
        self.pw = None
        self.page = None
        self.downloads = []
        self.pending_downloads = set()
        self._profile_lock = None
        self.handles = []
        self.targets = {}
        self.blocked_navigation = None

    async def start(self):
        if self.context:
            return
        for path in (self.root, self.profile, self.files):
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.chmod(0o700)
        self._profile_lock = (self.root / ".lock").open("a")
        try:
            fcntl.flock(self._profile_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._profile_lock.close()
            self._profile_lock = None
            raise RuntimeError(
                "Profile is already in use; stop its MCP/login process first"
            ) from None
        try:
            self.pw = await async_playwright().start()
            self.context = await self.pw.chromium.launch_persistent_context(
                str(self.profile),
                headless=self.headless,
                executable_path=os.getenv("CHROMIUM_EXECUTABLE") or None,
                viewport={"width": 1440, "height": 1000},
                accept_downloads=True,
                chromium_sandbox=os.getenv("CHROMIUM_SANDBOX", "1") != "0",
                locale="en-US",
                service_workers="block",
            )
            self.context.set_default_timeout(8000)
            await self.context.route("**/*", self._route)
            self.context.on("page", self._new_page)
            for page in self.context.pages:
                self._new_page(page)
            self.page = (
                self.context.pages[0] if self.context.pages else await self.context.new_page()
            )
            await self.page.goto(self.site.start_url, wait_until="domcontentloaded")
            # Locator reads use Playwright's isolated utility world and respect strict CSP.
            await self.page.locator("body").wait_for(state="attached", timeout=20000)
            for _ in range(100):
                if (await self.page.locator("body").inner_text()).strip():
                    break
                await asyncio.sleep(0.1)
        except BaseException:
            await self.close()
            raise

    def needs_login(self):
        """True when the current page is a login/logged-out page of this site."""
        return (
            bool(self.page) and not self.page.is_closed() and self.site.is_login_url(self.page.url)
        )

    async def _route(self, route):
        req = route.request
        if req.is_navigation_request() and not self.site.permits(req.url):
            self.blocked_navigation = req.url.split("?")[0]
            await route.abort()
        else:
            await route.continue_()

    def _new_page(self, page):
        self.page = page
        page.on("download", self._download)
        page.on("dialog", lambda dialog: dialog.dismiss())

    def _download(self, download):
        task = asyncio.create_task(self._save_download(download))
        self.pending_downloads.add(task)
        task.add_done_callback(self.pending_downloads.discard)

    async def _save_download(self, download):
        name = uuid.uuid4().hex[:12] + "-" + Path(download.suggested_filename).name
        path = self.files / name
        try:
            await download.save_as(path)
            path.chmod(0o600)
            digest = await asyncio.to_thread(lambda: hashlib.sha256(path.read_bytes()).hexdigest())
            self.downloads.append({"name": name, "size": path.stat().st_size, "sha256": digest})
        except Exception:
            self.downloads.append({"name": name, "error": "download failed"})

    async def flush_downloads(self):
        if self.pending_downloads:
            await asyncio.gather(*list(self.pending_downloads))

    async def observe(self):
        for handle in self.handles:
            try:
                await handle.dispose()
            except Exception:
                pass
        self.handles = []
        self.targets = {}
        if self.page.is_closed():
            pages = [p for p in self.context.pages if not p.is_closed()]
            if not pages:
                self.page = await self.context.new_page()
                await self.page.goto(self.site.start_url)
            else:
                self.page = pages[-1]
        frames, controls = [], []
        for frame in self.page.frames:
            if not self.site.permits(frame.url) and frame.url != "about:blank":
                continue
            try:
                handle = await frame.evaluate_handle(SNAPSHOT)
                self.handles.append(handle)
                data = await handle.evaluate(
                    "s => ({data:s.data,text:s.text,url:s.url,truncated:s.truncated,text_truncated:s.text_truncated})"
                )
                frames.append(
                    {
                        "url": data["url"],
                        "text": data["text"],
                        "controls_truncated": data["truncated"],
                        "text_truncated": data["text_truncated"],
                    }
                )
                for index, item in enumerate(data["data"]):
                    key = str(len(controls))
                    self.targets[key] = (handle, index, item, frame)
                    controls.append({"id": key, **item})
            except Exception:
                if frame == self.page.main_frame:
                    raise
        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "frames": frames,
            "controls": controls,
            "blocked_navigation": self.blocked_navigation,
        }

    async def act(self, action, target=None, value=None):
        if action == "wait":
            await asyncio.sleep(0.5)
            return
        if action in {"scroll_down", "scroll_up"} and target is None:
            await self.page.mouse.move(1000, 700)
            await self.page.mouse.wheel(0, 700 if action == "scroll_down" else -700)
            await asyncio.sleep(0.15)
            return
        if target not in self.targets:
            raise ValueError("Unobserved target")
        handle, index, expected, frame = self.targets[target]
        try:
            fresh = await handle.evaluate("(s,a) => s.matches(a[0],a[1])", [index, expected])
            node = (await handle.evaluate_handle("(s,i) => s.nodes[i]", index)).as_element()
        except Exception as exc:
            raise StaleObservation("Stale document; no input dispatched") from exc
        if not fresh:
            await node.dispose()
            raise StaleObservation("Stale target; no input dispatched")
        try:
            if action == "click":
                await node.click()
            elif action == "fill":
                if not expected["editable"]:
                    raise ValueError("Target is not editable")
                await node.fill(value)
            elif action == "select":
                await node.select_option(value=value)
            elif action == "upload":
                if not expected["file"]:
                    raise ValueError("Target is not a file input")
                await node.set_input_files(str(contained_file(self.files, value)))
            elif action == "press":
                if value not in {"Enter", "Tab", "Escape", "ArrowDown", "ArrowUp", "Space"}:
                    raise ValueError("Unsupported key")
                await node.press(value)
            elif action in {"scroll_down", "scroll_up"}:
                await node.hover()
                await self.page.mouse.wheel(0, 700 if action == "scroll_down" else -700)
            else:
                raise ValueError("Unsupported action")
        finally:
            await node.dispose()
        await asyncio.sleep(0.15)

    async def close(self):
        try:
            await self.flush_downloads()
            if self.context:
                await self.context.close()
        finally:
            self.context = None
            if self.pw:
                await self.pw.stop()
                self.pw = None
            if self._profile_lock:
                self._profile_lock.close()
                self._profile_lock = None
