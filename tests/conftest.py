"""Wait for asynchronous lifecycle work in tests that inspect settled state."""

import threading
import time

import pytest


@pytest.fixture
def wait_for_tasks():
    def wait(node):
        deadline = time.monotonic() + 3
        pause = threading.Event()
        while node._tasks.busy and time.monotonic() < deadline:
            pause.wait(0.002)
        assert not node._tasks.busy, "lifecycle worker did not finish"

    return wait


@pytest.fixture
def hold_speed_finalization(monkeypatch):
    """Hold a completed speed operation before LifecycleTasks clears its slot."""
    finished, release = threading.Event(), threading.Event()

    def hold(node):
        original_run = node._tasks._run

        def controlled_run(task, operation, interrupted):
            def held_operation(cancel):
                result = operation(cancel)
                finished.set()
                if not release.wait(3):
                    raise TimeoutError("test did not release speed worker finalization")
                return result

            original_run(
                task, held_operation if task.kind == "speed" else operation, interrupted
            )

        monkeypatch.setattr(node._tasks, "_run", controlled_run)
        return finished, release

    try:
        yield hold
    finally:
        release.set()
