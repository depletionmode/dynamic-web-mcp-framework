from website_mcp.browser import Browser
from website_mcp.policy import Decision
from website_mcp.runner import Runner
from website_mcp.spec import Site, Task


class Scripted:
    """Policy stub: returns the next scripted decision; verify is never reached."""

    def __init__(self, decide):
        self.calls = 0
        self._decide = decide

    async def decide(self, task, observation, history, guidance):
        self.calls += 1
        return self._decide(self.calls, observation)

    async def close(self):
        pass


def control(observation, name):
    return next(c["id"] for c in observation["controls"] if c["name"] == name)


async def run(website, tmp_path, decide, goal="Do the thing"):
    browser = Browser(Site("fixture", website, ("127.0.0.1",), ()), tmp_path)
    policy = Scripted(decide)
    try:
        result = await Runner(browser, policy).run(Task(goal, {"x": "1"}, max_steps=40))
    finally:
        await browser.close()
    return result, policy


async def test_unchanged_page_stops_before_more_model_calls(website, tmp_path):
    result, policy = await run(website, tmp_path, lambda n, o: Decision("wait"))
    assert result["status"] == "no_progress"
    # Four unchanged observations after the first; the fifth stops before asking the model.
    assert policy.calls == 4


async def test_same_action_on_same_page_stops(website, tmp_path):
    result, policy = await run(
        website, tmp_path, lambda n, o: Decision("click", control(o, "Save draft"))
    )
    assert result["status"] == "looping"
    executed = [s for s in result["steps"] if s.get("executed")]
    assert len(executed) == 3  # first click changed the page; two more on the unchanged page


async def test_persistently_low_confidence_stops(website, tmp_path):
    # Each fill changes a field value, so the page keeps changing and no other guard fires.
    result, policy = await run(
        website,
        tmp_path,
        lambda n, o: Decision("fill", control(o, "Recipient"), str(n), confidence=0.3),
    )
    assert result["status"] == "low_confidence"
    assert policy.calls == 5


async def test_capture_is_recorded_as_executed(website, tmp_path):
    """A capture takes effect; the policy is told only executed actions did, so an
    unexecuted one reads as failed and the model retries it until no_progress."""
    # Captures alone never change the page, so the no-progress guard ends the run.
    result, _ = await run(website, tmp_path, lambda n, o: Decision("capture"))
    assert result["status"] == "no_progress"
    captures = [step for step in result["steps"] if step.get("action") == "capture"]
    assert [step["captured_page"] for step in captures] == [1, 2, 3, 4]
    assert all(step["executed"] for step in captures)


async def test_home_returns_to_the_sites_start_page(website, tmp_path):
    """Following an outbound link can strand the browser; home is always the way back."""
    browser = Browser(Site("fixture", website, ("127.0.0.1", "example.org"), ()), tmp_path)
    try:
        await browser.start()
        await browser.page.goto(website + "frame")
        assert browser.page.url.endswith("/frame")
        await browser.act("home")
        assert browser.page.url == website
    finally:
        await browser.close()


async def test_read_page_records_the_whole_document_not_the_viewport(website, tmp_path):
    """Reading an article must not depend on how far the model happened to scroll."""
    browser = Browser(Site("fixture", website, ("127.0.0.1",), ()), tmp_path)
    try:
        await browser.start()
        await browser.page.goto(website + "long")
        clipped = (await browser.observe())["frames"][0]["text"]
        whole = await browser.page_text()
        assert "Paragraph 1 of" in clipped and "Paragraph 200 of" not in clipped
        assert "Top of the article" in whole["text"] and "Paragraph 200 of" in whole["text"]
        assert not whole["text_truncated"]
    finally:
        await browser.close()


async def test_read_page_is_captured_with_its_full_text(website, tmp_path):
    scripted = [Decision("read_page"), Decision("wait")]
    result, _ = await run(website, tmp_path, lambda n, o: scripted[min(n, 2) - 1])
    read = next(s for s in result["steps"] if s.get("action") == "read_page")
    assert read["executed"] and read["captured_page"] == 1
