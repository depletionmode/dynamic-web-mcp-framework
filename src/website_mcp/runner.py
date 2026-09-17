from __future__ import annotations

import asyncio
import os
from uuid import uuid4

from .browser import StaleObservation
from .spec import Task


class Runner:
    def __init__(self, browser, policy):
        self.browser, self.policy = browser, policy

    async def run(self, task: Task):
        async with self.browser.lock:
            await self.browser.start()
            run_id = uuid4().hex
            history, captures = [], []
            first_download = len(self.browser.downloads)
            observation = None
            status = "step_limit"
            verification = None
            stale_attempts = 0
            try:
                async with asyncio.timeout(float(os.getenv("TASK_TIMEOUT", "240"))):
                    for _ in range(task.max_steps):
                        observation = await self.browser.observe()
                        observation["downloads"] = self.browser.downloads[first_download:]
                        if self.browser.needs_login():
                            status = "login_required"
                            break
                        decision = await self.policy.decide(
                            task, observation, history, self.browser.site.guidance
                        )
                        entry = {
                            "action": decision.action,
                            "target": decision.target,
                            "confidence": decision.confidence,
                            "executed": False,
                        }
                        if decision.value is not None:
                            entry["value"] = decision.value
                        if decision.target:
                            entry["control"] = next(
                                (
                                    c["name"]
                                    for c in observation["controls"]
                                    if c["id"] == decision.target
                                ),
                                "",
                            )
                        history.append(entry)
                        if decision.action in {"blocked", "uncertain"}:
                            status = decision.action
                            break
                        if decision.action == "done":
                            await self.browser.flush_downloads()
                            observation = await self.browser.observe()
                            observation["downloads"] = self.browser.downloads[first_download:]
                            if task.verifier:
                                verification = {
                                    "kind": "deterministic",
                                    "passed": bool(await task.verifier(self.browser)),
                                }
                                status = "verified" if verification["passed"] else "unverified"
                            else:
                                probability = await self.policy.verify(
                                    task, observation, history, captures
                                )
                                verification = {"kind": "model", "probability": probability}
                                status = "model_complete" if probability >= 0.9 else "unverified"
                            break
                        if decision.action == "capture":
                            captures.append(
                                {"url": observation["url"], "frames": observation["frames"]}
                            )
                            entry["captured_page"] = len(captures)
                            if len(captures) >= 25:
                                status = "capture_limit"
                                break
                            continue
                        try:
                            await self.browser.act(decision.action, decision.target, decision.value)
                            entry["executed"] = True
                            stale_attempts = 0
                        except StaleObservation:
                            entry["error"] = "observation_changed_no_action_dispatched"
                            stale_attempts += 1
                            if stale_attempts >= 3:
                                status = "unstable_page"
                                break
                            continue
                        except Exception as exc:
                            # Never retry a possibly committed mutation blindly. Re-observe and let the caller reconcile.
                            entry["error"] = type(exc).__name__
                            status = "action_error"
                            break
            except TimeoutError:
                status = "timeout"
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                status = "context_limit" if "max_tokens_exceeded" in str(exc) else "error"
                history.append({"error": type(exc).__name__})
            try:
                observation = await self.browser.observe()
                await asyncio.wait_for(self.browser.flush_downloads(), timeout=15)
            except Exception:
                pass
            return {
                "run_id": run_id,
                "status": status,
                "verification": verification,
                "page": observation,
                "captured_pages": captures,
                "downloads": self.browser.downloads[first_download:],
                "steps": history,
                "note": "Model completion is probabilistic. Inspect page evidence before retrying mutations; a timeout/error may follow a committed action.",
            }
