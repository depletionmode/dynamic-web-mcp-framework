from __future__ import annotations

import asyncio
import hashlib
import json
import os
from uuid import uuid4

from .browser import StaleObservation
from .spec import Task

# Guardrails against burning model calls without getting anywhere. Every stop still returns
# the page evidence and history so the caller can retry with a narrower goal.
NO_PROGRESS_STEPS = 4  # consecutive unchanged observations
LOOP_REPEATS = 3  # identical executed action on an identical page
CONFIDENCE_WINDOW = 5
MIN_MEAN_CONFIDENCE = 0.4
DEFAULT_TIMEOUT = "120"


def fingerprint(observation):
    """Stable digest of what the page shows: URL, text, control names and values."""
    digest = hashlib.sha256()
    digest.update(observation["url"].encode())
    for frame in observation["frames"]:
        digest.update(frame["text"].encode())
    for control in observation["controls"]:
        digest.update(json.dumps([control["name"], control.get("value")]).encode())
    return digest.hexdigest()


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
            last_fingerprint, unchanged = None, 0
            repeats, confidences = {}, []
            try:
                async with asyncio.timeout(float(os.getenv("TASK_TIMEOUT", DEFAULT_TIMEOUT))):
                    for _ in range(task.max_steps):
                        observation = await self.browser.observe()
                        observation["downloads"] = self.browser.downloads[first_download:]
                        if self.browser.needs_login():
                            status = "login_required"
                            break
                        current = fingerprint(observation)
                        unchanged = unchanged + 1 if current == last_fingerprint else 0
                        last_fingerprint = current
                        if unchanged >= NO_PROGRESS_STEPS:
                            status = "no_progress"
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
                            # A capture happens; the policy is told only executed actions took
                            # effect, so an unexecuted one reads as failed and gets retried.
                            entry["executed"] = True
                            entry["captured_page"] = len(captures)
                            if len(captures) >= 25:
                                status = "capture_limit"
                                break
                            continue
                        confidences.append(decision.confidence)
                        recent = confidences[-CONFIDENCE_WINDOW:]
                        if (
                            len(recent) >= CONFIDENCE_WINDOW
                            and sum(recent) / len(recent) < MIN_MEAN_CONFIDENCE
                        ):
                            status = "low_confidence"
                            break
                        # Waiting on an unchanged page is the no-progress case, not a loop.
                        repeat_key = (decision.action, decision.target, decision.value, current)
                        if (
                            decision.action != "wait"
                            and repeats.get(repeat_key, 0) >= LOOP_REPEATS - 1
                        ):
                            status = "looping"
                            break
                        try:
                            await self.browser.act(decision.action, decision.target, decision.value)
                            entry["executed"] = True
                            repeats[repeat_key] = repeats.get(repeat_key, 0) + 1
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
            self.browser.touch()  # idle time counts from the end of a run, not its start
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
